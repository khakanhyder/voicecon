"""
Chat widget endpoints.

Two surfaces:

* Public (no auth, keyed by the widget's public_key) — what the embedded widget
  on a customer site calls: fetch config, send a message. These must be CORS
  open because they run on arbitrary origins.
* Dashboard (JWT auth) — the Chatbot section: create chatbots, link each to
  the agent that answers it, brand them, and read their conversations.

A chatbot (``ChatWidget``) is its own object. ``/chatbots`` is the API for it;
the older ``/agents/{agent_id}/widget`` routes still work for API clients and
address the agent's first chatbot.
"""
import asyncio
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response,
    WebSocket, WebSocketDisconnect, status,
)
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_current_org_id
from app.core.urls import public_base_url
from app.database import get_db
from app.models.agent import Agent
from app.models.chat import ChatMessage, ChatSession, ChatWidget
from app.models.user import User
from app.core.time import utc_iso
from app.services.chat.events import chat_events

logger = logging.getLogger(__name__)

router = APIRouter()

#: Routes that must stay reachable without a workspace context — carrier and
#: payment-provider webhooks, and the public embed surfaces. They live on their
#: own router so the authenticated router can carry a blanket permission guard
#: (see app.api.v1.api) without accidentally locking these out.
public_router = APIRouter()

#: The live inbox socket. Authenticates from a ``token`` query param inside the
#: handler (a WebSocket can't carry the dashboard's headers), so it sits
#: outside the guarded router.
ws_router = APIRouter()


DEFAULT_WIDGET_CONFIG = {
    "title": "Chat with us",
    "subtitle": "We usually reply in a few seconds",
    "greeting": "Hi! How can I help you today?",
    "accent_color": "#4f46e5",
    "position": "bottom-right",
    "launcher_text": "Chat",
}

# History we send to the model per turn. The full transcript is still stored.
HISTORY_TURNS = 12


# ============================================================================
# Public widget surface (unauthenticated, keyed by public_key)
# ============================================================================


async def _load_enabled_widget(db: AsyncSession, public_key: str) -> ChatWidget:
    widget = (
        await db.execute(
            select(ChatWidget).where(ChatWidget.public_key == public_key)
        )
    ).scalar_one_or_none()

    # A chatbot with no agent linked has nobody to answer; the embed treats a
    # 404 as "don't show the launcher", so the site simply shows no chat.
    if not widget or not widget.enabled or widget.agent_id is None:
        raise HTTPException(status_code=404, detail="Chat widget not found")
    return widget


@public_router.get("/public/{public_key}/config")
async def get_widget_config(public_key: str, db: AsyncSession = Depends(get_db)):
    """Branding the embed script needs to render itself. No auth."""
    widget = await _load_enabled_widget(db, public_key)
    config = {**DEFAULT_WIDGET_CONFIG, **(widget.config or {})}
    return {"public_key": public_key, "config": config}


@public_router.post("/public/{public_key}/message")
async def send_widget_message(
    public_key: str,
    payload: dict,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a visitor message and get the agent's reply.

    Body: ``{"session_id"?: str, "visitor_id"?: str, "message": str,
             "source_url"?: str}``. Omit session_id to start a conversation;
    the returned id continues it.

    While a team member has taken the conversation over (``mode: "human"``)
    the agent stays quiet: the message is stored, the team is notified, and
    ``reply`` is null — the person's answer reaches the widget through
    ``GET /public/{key}/sessions/{id}/messages``.
    """
    from app.services.chat.agent_chat_service import get_agent_chat_service

    widget = await _load_enabled_widget(db, public_key)

    message = (payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if len(message) > 4000:
        raise HTTPException(status_code=400, detail="message is too long")

    agent = await db.get(Agent, widget.agent_id)
    if not agent or not agent.is_active:
        raise HTTPException(status_code=404, detail="This chat isn't available right now.")

    # Resume or open a session.
    session = await _resolve_session(db, widget, agent, payload, request)
    new_conversation = not (session.message_count or 0)

    # Load recent history for context (before this turn is added).
    history_rows = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(desc(ChatMessage.created_at))
            .limit(HISTORY_TURNS)
        )
    ).scalars().all()
    history = [
        {"role": _model_role(m.role), "content": m.content} for m in reversed(history_rows)
    ]

    # Commit the visitor's message before the agent runs, so the team's inbox
    # (and phones) see it straight away and a failed turn still leaves it.
    visitor_msg = ChatMessage(id=uuid.uuid4(), session_id=session.id, role="user", content=message)
    db.add(visitor_msg)
    _record_activity(session, visitor_msg)
    session.unread_count = (session.unread_count or 0) + 1
    await db.commit()

    _publish_message(session, visitor_msg, widget=widget)
    _publish_session(session, "session.created" if new_conversation else "session.updated", widget=widget)
    background_tasks.add_task(_push_visitor_message, session.id, visitor_msg.id, new_conversation)

    if session.mode == "human":
        return {
            "session_id": str(session.id),
            "reply": None,
            "mode": "human",
            "message_id": str(visitor_msg.id),
        }

    try:
        result = await get_agent_chat_service(db).respond(agent, history, message)
        reply = result.reply or "Sorry, I didn't catch that. Could you rephrase?"
        tool_name = result.tool_name
    except Exception as e:
        logger.error(f"Chat turn failed: {e}", exc_info=True)
        reply = "Sorry, something went wrong on our end. Please try again."
        tool_name = None

    # A team member may have taken over while the agent was thinking; their
    # takeover wins, so the agent's late answer is dropped.
    await db.refresh(session, ["mode"])
    if session.mode == "human":
        return {
            "session_id": str(session.id),
            "reply": None,
            "mode": "human",
            "message_id": str(visitor_msg.id),
        }

    reply_msg = ChatMessage(
        id=uuid.uuid4(), session_id=session.id, role="assistant", content=reply, tool_name=tool_name
    )
    db.add(reply_msg)
    _record_activity(session, reply_msg)
    await db.commit()

    _publish_message(session, reply_msg, widget=widget)
    _publish_session(session, "session.updated", widget=widget)

    return {
        "session_id": str(session.id),
        "reply": reply,
        "mode": "ai",
        "message_id": str(visitor_msg.id),
        "reply_message_id": str(reply_msg.id),
    }


@public_router.get("/public/{public_key}/sessions/{session_id}/messages")
async def get_visitor_messages(
    public_key: str,
    session_id: str,
    visitor_id: Optional[str] = None,
    after: Annotated[Optional[str], Query(description="ISO timestamp; only newer messages")] = None,
    db: AsyncSession = Depends(get_db),
):
    """The visitor's own conversation, for the embed: history on reopen, and
    polling for replies a team member sends from the dashboard or the app.

    Keyed by the unguessable session id plus the visitor id the widget sent
    when the session started, so one visitor can't read another's chat.
    """
    widget = await _load_enabled_widget(db, public_key)
    session = await _visitor_session(db, widget, session_id, visitor_id)

    query = select(ChatMessage).where(ChatMessage.session_id == session.id)
    after_dt = _parse_after(after)
    if after_dt is not None:
        query = query.where(ChatMessage.created_at > after_dt)
    rows = (await db.execute(query.order_by(ChatMessage.created_at).limit(200))).scalars().all()

    senders = await _sender_names(db, rows)
    return {
        "session_id": str(session.id),
        "mode": session.mode or "ai",
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                # First name only: the visitor sees who answered, not the
                # team member's full identity.
                "sender_name": (senders.get(m.sender_user_id) or "").split(" ")[0] or None
                if m.role == "human" else None,
                "created_at": utc_iso(m.created_at),
            }
            for m in rows
        ],
    }


async def _visitor_session(db: AsyncSession, widget: ChatWidget, session_id: str, visitor_id: Optional[str]) -> ChatSession:
    try:
        session_uuid = uuid.UUID(str(session_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    session = (
        await db.execute(
            select(ChatSession).where(
                and_(ChatSession.id == session_uuid, ChatSession.widget_id == widget.id)
            )
        )
    ).scalar_one_or_none()
    if session is None or (session.visitor_id and session.visitor_id != (visitor_id or "")):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return session


def _model_role(role: str) -> str:
    """What the LLM sees: a team member's reply is the business speaking."""
    return "assistant" if role == "human" else role


def _record_activity(session: ChatSession, message: ChatMessage) -> None:
    session.message_count = (session.message_count or 0) + 1
    session.last_activity_at = datetime.utcnow()
    session.last_message_preview = message.content[:300]
    session.last_message_role = message.role


def _parse_after(after: Optional[str]) -> Optional[datetime]:
    """An ``after`` cursor as naive UTC (how the DB stores time), or None."""
    if not after:
        return None
    try:
        value = datetime.fromisoformat(after.strip().replace("Z", "+00:00").replace(" ", "+"))
    except ValueError:
        raise HTTPException(status_code=400, detail="after must be an ISO 8601 timestamp")
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


async def _sender_names(db: AsyncSession, rows) -> Dict[uuid.UUID, str]:
    ids = {m.sender_user_id for m in rows if m.sender_user_id}
    if not ids:
        return {}
    users = (await db.execute(select(User.id, User.full_name, User.email).where(User.id.in_(ids)))).all()
    return {uid: (name or email or "Team member") for uid, name, email in users}


async def _push_visitor_message(session_id: uuid.UUID, message_id: uuid.UUID, new_conversation: bool) -> None:
    from app.services.chat.push import notify_visitor_message

    await notify_visitor_message(session_id, message_id, new_conversation)


def _publish_message(session: ChatSession, message: ChatMessage, widget: Optional[ChatWidget] = None,
                     sender: Optional[User] = None) -> None:
    chat_events.publish(session.organization_id, "message.created", {
        "session_id": str(session.id),
        "chatbot_id": str(session.widget_id),
        "message": _message_dict(message, {sender.id: sender.full_name or sender.email} if sender else {}),
    })


def _publish_session(session: ChatSession, event: str, widget: Optional[ChatWidget] = None) -> None:
    chat_events.publish(session.organization_id, event, {"session": _session_dict(session, widget)})


async def _resolve_session(
    db: AsyncSession,
    widget: ChatWidget,
    agent: Agent,
    payload: dict,
    request: Request,
) -> ChatSession:
    """Continue the given session, or open a new one."""
    session_id = payload.get("session_id")
    if session_id:
        try:
            existing = (
                await db.execute(
                    select(ChatSession).where(
                        and_(
                            ChatSession.id == uuid.UUID(str(session_id)),
                            ChatSession.widget_id == widget.id,
                        )
                    )
                )
            ).scalar_one_or_none()
            if existing:
                return existing
        except (ValueError, TypeError):
            pass

    session = ChatSession(
        widget_id=widget.id,
        agent_id=agent.id,
        organization_id=widget.organization_id,
        visitor_id=(payload.get("visitor_id") or "")[:128] or None,
        source_url=(payload.get("source_url") or "")[:2000] or None,
        user_agent=(request.headers.get("user-agent") or "")[:2000] or None,
    )
    db.add(session)
    await db.flush()
    return session


# ============================================================================
# Dashboard surface (authenticated)
# ============================================================================


def _embed_snippet(public_key: str, request: Request) -> str:
    base = public_base_url(request)
    return (
        f'<script src="{base}/api/v1/chat/widget.js" '
        f'data-voicecon-key="{public_key}" async></script>'
    )


def _chatbot_dict(
    widget: ChatWidget,
    request: Request,
    agent: Optional[Agent] = None,
    stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """A chatbot as the dashboard sees it."""
    return {
        "id": str(widget.id),
        "name": widget.name or (f"{agent.name} chatbot" if agent else "Website chatbot"),
        "enabled": widget.enabled,
        "agent_id": str(widget.agent_id) if widget.agent_id else None,
        "agent": {"id": str(agent.id), "name": agent.name, "is_active": agent.is_active} if agent else None,
        # Live on customer sites: enabled and answered by an active agent.
        "live": bool(widget.enabled and agent is not None and agent.is_active),
        "public_key": widget.public_key,
        "config": {**DEFAULT_WIDGET_CONFIG, **(widget.config or {})},
        "embed_snippet": _embed_snippet(widget.public_key, request),
        "session_count": (stats or {}).get("session_count", 0),
        # Unread visitor messages across this chatbot's conversations, and how
        # many conversations have any — the badge on the mobile chatbot list.
        "unread_count": (stats or {}).get("unread_count", 0),
        "unread_sessions": (stats or {}).get("unread_sessions", 0),
        "last_activity_at": (stats or {}).get("last_activity_at"),
        "created_at": utc_iso(widget.created_at),
        "updated_at": utc_iso(widget.updated_at),
    }


class ChatbotCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    agent_id: Optional[uuid.UUID] = None
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)


class ChatbotUpdate(BaseModel):
    """Partial update. Send ``agent_id: null`` to unlink the agent."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    agent_id: Optional[uuid.UUID] = None
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


def _clean_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Keep branding to known keys and plain values, so the public config
    endpoint never serves arbitrary nested data."""
    allowed = set(DEFAULT_WIDGET_CONFIG) | {"avatar_url"}
    cleaned: Dict[str, Any] = {}
    for key, value in (config or {}).items():
        if key not in allowed or not isinstance(value, (str, int, float, bool)) or value is None:
            continue
        cleaned[key] = value[:500] if isinstance(value, str) else value
    if "position" in cleaned and cleaned["position"] not in ("bottom-right", "bottom-left"):
        cleaned.pop("position")
    return cleaned


async def _workspace_agent(db: AsyncSession, agent_id: uuid.UUID, org_id: uuid.UUID) -> Agent:
    agent = (
        await db.execute(
            select(Agent).where(and_(Agent.id == agent_id, Agent.organization_id == org_id))
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=400, detail="Choose an agent from this workspace.")
    return agent


async def _owned_chatbot(db: AsyncSession, chatbot_id: str, org_id: uuid.UUID) -> ChatWidget:
    try:
        chatbot_uuid = uuid.UUID(chatbot_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    widget = (
        await db.execute(
            select(ChatWidget).where(
                and_(ChatWidget.id == chatbot_uuid, ChatWidget.organization_id == org_id)
            )
        )
    ).scalar_one_or_none()
    if not widget:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    return widget


async def _session_stats(db: AsyncSession, widget_ids: list) -> Dict[uuid.UUID, Dict[str, Any]]:
    if not widget_ids:
        return {}
    rows = (
        await db.execute(
            select(
                ChatSession.widget_id,
                func.count(ChatSession.id),
                func.max(ChatSession.last_activity_at),
                func.coalesce(func.sum(ChatSession.unread_count), 0),
                func.count(ChatSession.id).filter(ChatSession.unread_count > 0),
            )
            .where(ChatSession.widget_id.in_(widget_ids))
            .group_by(ChatSession.widget_id)
        )
    ).all()
    return {
        widget_id: {
            "session_count": count,
            "last_activity_at": utc_iso(last),
            "unread_count": int(unread or 0),
            "unread_sessions": int(unread_sessions or 0),
        }
        for widget_id, count, last, unread, unread_sessions in rows
    }


async def _chatbot_response(db: AsyncSession, widget: ChatWidget, request: Request) -> Dict[str, Any]:
    agent = await db.get(Agent, widget.agent_id) if widget.agent_id else None
    stats = (await _session_stats(db, [widget.id])).get(widget.id)
    return _chatbot_dict(widget, request, agent, stats)


@router.get("/chatbots")
async def list_chatbots(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Every chatbot in the workspace, newest first."""
    rows = (
        await db.execute(
            select(ChatWidget, Agent)
            .outerjoin(Agent, Agent.id == ChatWidget.agent_id)
            .where(ChatWidget.organization_id == org_id)
            .order_by(desc(ChatWidget.created_at))
        )
    ).all()
    stats = await _session_stats(db, [widget.id for widget, _ in rows])
    return {
        "chatbots": [
            _chatbot_dict(widget, request, agent, stats.get(widget.id)) for widget, agent in rows
        ]
    }


@router.post("/chatbots", status_code=status.HTTP_201_CREATED)
async def create_chatbot(
    payload: ChatbotCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Create a chatbot, optionally linked to the agent that will answer it."""
    if payload.agent_id:
        await _workspace_agent(db, payload.agent_id, org_id)
    widget = ChatWidget(
        name=payload.name.strip(),
        agent_id=payload.agent_id,
        organization_id=org_id,
        public_key=secrets.token_urlsafe(24),
        enabled=payload.enabled,
        config=_clean_config(payload.config),
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return await _chatbot_response(db, widget, request)


@router.get("/chatbots/{chatbot_id}")
async def get_chatbot(
    chatbot_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    widget = await _owned_chatbot(db, chatbot_id, org_id)
    return await _chatbot_response(db, widget, request)


@router.patch("/chatbots/{chatbot_id}")
async def update_chatbot(
    chatbot_id: str,
    payload: ChatbotUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Rename, relink, enable/disable or rebrand a chatbot.

    The public key never changes here, so the embed already on a customer's
    site keeps working through every edit.
    """
    widget = await _owned_chatbot(db, chatbot_id, org_id)
    fields = payload.model_fields_set

    if "name" in fields and payload.name is not None:
        widget.name = payload.name.strip()
    if "agent_id" in fields:
        if payload.agent_id is not None:
            await _workspace_agent(db, payload.agent_id, org_id)
        widget.agent_id = payload.agent_id
    if "enabled" in fields and payload.enabled is not None:
        widget.enabled = payload.enabled
    if "config" in fields and payload.config is not None:
        # Merge so a partial update doesn't wipe other branding fields.
        widget.config = {**(widget.config or {}), **_clean_config(payload.config)}

    await db.commit()
    await db.refresh(widget)
    return await _chatbot_response(db, widget, request)


@router.delete("/chatbots/{chatbot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chatbot(
    chatbot_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Delete a chatbot and its conversations. Its embed stops showing."""
    widget = await _owned_chatbot(db, chatbot_id, org_id)
    await db.delete(widget)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/chatbots/{chatbot_id}/sessions")
async def list_chatbot_sessions(
    chatbot_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Annotated[Optional[str], Query(max_length=200)] = None,
    mode: Annotated[Optional[str], Query(pattern="^(ai|human)$")] = None,
    unread: Optional[bool] = None,
    date_from: Annotated[Optional[str], Query(alias="from")] = None,
    date_to: Annotated[Optional[str], Query(alias="to")] = None,
    sort: Annotated[str, Query(pattern="^(started|recent)$")] = "started",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """A chatbot's conversations, newest first — whichever agent answered them.

    Takes the same search and filters as ``GET /chat/sessions``.
    """
    widget = await _owned_chatbot(db, chatbot_id, org_id)
    conditions = [ChatSession.widget_id == widget.id] + _session_filters(q, mode, unread, date_from, date_to)
    return await _sessions_page(db, and_(*conditions), page, page_size, sort=sort)


@router.get("/sessions")
async def list_inbox(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    chatbot_id: Optional[uuid.UUID] = None,
    q: Annotated[Optional[str], Query(max_length=200)] = None,
    mode: Annotated[Optional[str], Query(pattern="^(ai|human)$")] = None,
    unread: Optional[bool] = None,
    date_from: Annotated[Optional[str], Query(alias="from")] = None,
    date_to: Annotated[Optional[str], Query(alias="to")] = None,
    sort: Annotated[str, Query(pattern="^(started|recent)$")] = "recent",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Every chatbot's conversations in one inbox — the mobile app's home.

    ``q`` searches message text, the page URL the chat started on and the
    visitor id. ``sort=recent`` (default) puts the latest activity first.
    """
    conditions = [ChatSession.organization_id == org_id]
    if chatbot_id is not None:
        conditions.append(ChatSession.widget_id == chatbot_id)
    conditions += _session_filters(q, mode, unread, date_from, date_to)
    return await _sessions_page(db, and_(*conditions), page, page_size, sort=sort)


@router.get("/sessions/unread-count")
async def inbox_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Badge numbers for the app icon / inbox tab."""
    unread, sessions = (
        await db.execute(
            select(
                func.coalesce(func.sum(ChatSession.unread_count), 0),
                func.count(ChatSession.id).filter(ChatSession.unread_count > 0),
            ).where(ChatSession.organization_id == org_id)
        )
    ).one()
    return {"unread_count": int(unread or 0), "unread_sessions": int(sessions or 0)}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """One conversation's header: chatbot, agent, visitor, mode, unread."""
    session = await _owned_session(db, session_id, org_id)
    widget = await db.get(ChatWidget, session.widget_id)
    agent = await db.get(Agent, session.agent_id) if session.agent_id else None
    data = _session_dict(session, widget)
    data["user_agent"] = session.user_agent
    data["agent_name"] = agent.name if agent else None
    return data


class HumanReply(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


@router.post("/sessions/{session_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_human_reply(
    session_id: str,
    payload: HumanReply,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """A team member answers the visitor (from the dashboard or the mobile app).

    Takes the conversation over: the agent stops answering it until someone
    calls ``/release``. The widget shows the reply on its next poll.
    """
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Write a message first.")
    session = await _owned_session(db, session_id, org_id)

    message = ChatMessage(
        id=uuid.uuid4(), session_id=session.id, role="human", content=content,
        sender_user_id=current_user.id,
    )
    db.add(message)
    _record_activity(session, message)
    session.mode = "human"
    session.unread_count = 0  # answering it means it has been read
    await db.commit()

    widget = await db.get(ChatWidget, session.widget_id)
    _publish_message(session, message, widget=widget, sender=current_user)
    _publish_session(session, "session.updated", widget=widget)
    return {
        "message": _message_dict(message, {current_user.id: current_user.full_name or current_user.email}),
        "session": _session_dict(session, widget),
    }


@router.post("/sessions/{session_id}/takeover")
async def take_over_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Stop the agent answering this conversation; a person will reply."""
    return await _set_mode(db, session_id, org_id, "human")


@router.post("/sessions/{session_id}/release")
async def release_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Hand the conversation back to the agent; it answers the next message."""
    return await _set_mode(db, session_id, org_id, "ai")


@router.post("/sessions/{session_id}/read")
async def mark_session_read(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Clear the conversation's unread count (opening it in the app)."""
    session = await _owned_session(db, session_id, org_id)
    widget = await db.get(ChatWidget, session.widget_id)
    if session.unread_count:
        session.unread_count = 0
        await db.commit()
        _publish_session(session, "session.updated", widget=widget)
    return _session_dict(session, widget)


async def _set_mode(db: AsyncSession, session_id: str, org_id: uuid.UUID, mode: str) -> Dict[str, Any]:
    session = await _owned_session(db, session_id, org_id)
    widget = await db.get(ChatWidget, session.widget_id)
    if session.mode != mode:
        session.mode = mode
        await db.commit()
        _publish_session(session, "session.updated", widget=widget)
    return _session_dict(session, widget)


async def _owned_session(db: AsyncSession, session_id: str, org_id: uuid.UUID) -> ChatSession:
    """The conversation, if it belongs to the caller's current workspace.

    Ownership is by workspace: the agent that answered may since have been
    deleted or unlinked, but the conversation still belongs to the chatbot.
    """
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")
    session = (
        await db.execute(
            select(ChatSession).where(
                and_(ChatSession.id == session_uuid, ChatSession.organization_id == org_id)
            )
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _session_filters(q, mode, unread, date_from, date_to) -> list:
    conditions = []
    text = (q or "").strip()
    if text:
        pattern = f"%{text}%"
        conditions.append(
            or_(
                ChatSession.visitor_id.ilike(pattern),
                ChatSession.source_url.ilike(pattern),
                exists().where(
                    and_(ChatMessage.session_id == ChatSession.id, ChatMessage.content.ilike(pattern))
                ),
            )
        )
    if mode:
        conditions.append(ChatSession.mode == mode)
    if unread is True:
        conditions.append(ChatSession.unread_count > 0)
    elif unread is False:
        conditions.append(ChatSession.unread_count == 0)
    start, end = _parse_after(date_from), _parse_after(date_to)
    if start is not None:
        conditions.append(ChatSession.last_activity_at >= start)
    if end is not None:
        conditions.append(ChatSession.started_at <= end)
    return conditions


# ---- Per-agent routes (older API; kept for existing API clients) -----------


async def _first_chatbot_for_agent(db: AsyncSession, agent: Agent) -> Optional[ChatWidget]:
    return (
        await db.execute(
            select(ChatWidget)
            .where(ChatWidget.agent_id == agent.id)
            .order_by(ChatWidget.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()


@router.get("/agents/{agent_id}/widget")
async def get_agent_widget(
    agent_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """The agent's first chatbot (config + embed), or ``exists: false``.

    Kept for API clients from before chatbots were standalone; the dashboard
    uses ``/chatbots``.
    """
    agent = await _owned_agent(db, agent_id, current_user, org_id)
    widget = await _first_chatbot_for_agent(db, agent)
    if not widget:
        return {"exists": False}

    return {
        "exists": True,
        "id": str(widget.id),
        "enabled": widget.enabled,
        "public_key": widget.public_key,
        "config": {**DEFAULT_WIDGET_CONFIG, **(widget.config or {})},
        "embed_snippet": _embed_snippet(widget.public_key, request),
    }


@router.put("/agents/{agent_id}/widget")
async def upsert_agent_widget(
    agent_id: str,
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Create or update the agent's first chatbot (older API; see above)."""
    agent = await _owned_agent(db, agent_id, current_user, org_id)
    widget = await _first_chatbot_for_agent(db, agent)

    incoming_config = _clean_config(payload.get("config") or {})
    enabled = payload.get("enabled", True)

    if widget is None:
        widget = ChatWidget(
            name=f"{agent.name} chatbot"[:255],
            agent_id=agent.id,
            organization_id=org_id,
            public_key=secrets.token_urlsafe(24),
            enabled=bool(enabled),
            config=incoming_config,
        )
        db.add(widget)
    else:
        widget.enabled = bool(enabled)
        widget.config = {**(widget.config or {}), **incoming_config}

    await db.commit()
    await db.refresh(widget)

    return {
        "id": str(widget.id),
        "enabled": widget.enabled,
        "public_key": widget.public_key,
        "config": {**DEFAULT_WIDGET_CONFIG, **(widget.config or {})},
        "embed_snippet": _embed_snippet(widget.public_key, request),
    }


@router.get("/agents/{agent_id}/sessions")
async def list_chat_sessions(
    agent_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Chat sessions for reporting — the text-channel equivalent of calls."""
    agent = await _owned_agent(db, agent_id, current_user, org_id)
    return await _sessions_page(db, ChatSession.agent_id == agent.id, page, page_size)


async def _sessions_page(db: AsyncSession, condition, page: int, page_size: int, sort: str = "started") -> Dict[str, Any]:
    base = select(ChatSession).where(condition)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    order = ChatSession.last_activity_at if sort == "recent" else ChatSession.started_at
    rows = (
        await db.execute(
            base.order_by(desc(order), desc(ChatSession.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    widget_ids = {s.widget_id for s in rows}
    widgets = {
        w.id: w for w in (
            await db.execute(select(ChatWidget).where(ChatWidget.id.in_(widget_ids)))
        ).scalars().all()
    } if widget_ids else {}

    return {
        "sessions": [_session_dict(s, widgets.get(s.widget_id)) for s in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < total,
    }


def _visitor_label(visitor_id: Optional[str]) -> str:
    """A short stable name for an anonymous visitor ("Visitor 4F2A")."""
    if not visitor_id:
        return "Visitor"
    tail = "".join(ch for ch in visitor_id if ch.isalnum())[-4:].upper()
    return f"Visitor {tail}" if tail else "Visitor"


def _session_dict(s: ChatSession, widget: Optional[ChatWidget] = None) -> Dict[str, Any]:
    return {
        "id": str(s.id),
        "chatbot_id": str(s.widget_id),
        "chatbot_name": (widget.name if widget else None) or "Website chatbot",
        "agent_id": str(s.agent_id) if s.agent_id else None,
        "visitor_id": s.visitor_id,
        "visitor_label": _visitor_label(s.visitor_id),
        "status": s.status,
        "mode": s.mode or "ai",
        "unread_count": s.unread_count or 0,
        "message_count": s.message_count,
        "last_message_preview": s.last_message_preview,
        "last_message_role": s.last_message_role,
        "source_url": s.source_url,
        "started_at": utc_iso(s.started_at),
        "last_activity_at": utc_iso(s.last_activity_at),
    }


def _message_dict(m: ChatMessage, senders: Optional[Dict[uuid.UUID, str]] = None) -> Dict[str, Any]:
    sender = None
    if m.sender_user_id:
        sender = {"id": str(m.sender_user_id), "name": (senders or {}).get(m.sender_user_id) or "Team member"}
    return {
        "id": str(m.id),
        "role": m.role,
        "content": m.content,
        "tool_name": m.tool_name,
        "sender": sender,
        "created_at": utc_iso(m.created_at),
    }


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    after: Annotated[Optional[str], Query(description="ISO timestamp; only newer messages")] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """A conversation's transcript, oldest first. ``after`` returns only newer
    messages (for polling when the live socket isn't connected)."""
    session = await _owned_session(db, session_id, org_id)

    query = select(ChatMessage).where(ChatMessage.session_id == session.id)
    after_dt = _parse_after(after)
    if after_dt is not None:
        query = query.where(ChatMessage.created_at > after_dt)
    rows = (await db.execute(query.order_by(ChatMessage.created_at))).scalars().all()

    senders = await _sender_names(db, rows)
    return {
        "session_id": session_id,
        "mode": session.mode or "ai",
        "messages": [_message_dict(m, senders) for m in rows],
    }


# ============================================================================
# Live inbox socket
# ============================================================================

#: Seconds between server keep-alive frames; proxies drop idle sockets.
WS_HEARTBEAT_SECONDS = 25


@ws_router.websocket("/ws")
async def chat_inbox_socket(
    websocket: WebSocket,
    token: str = Query(default=""),
    organization_id: Optional[str] = Query(default=None),
):
    """Live inbox events for one workspace.

    Connect with ``?token=<access token>&organization_id=<workspace id>``.
    Server → client frames are JSON ``{"event", "organization_id", "data"}``:
    ``message.created``, ``session.created``, ``session.updated``, plus
    ``ready`` once subscribed and ``ping`` every 25 s. Send ``"ping"`` (text)
    to get ``{"event": "pong"}``. Close codes: 4001 bad/expired token, 4003 no
    access to that workspace.
    """
    from app.core import permissions as perms
    from app.core.dependencies import user_for_socket_token
    from app.core.security import SCOPE_APP
    from app.core.workspace import resolve_workspace
    from app.database import AsyncSessionLocal

    await websocket.accept()

    # Authenticate and resolve the workspace, then let go of the DB session —
    # the socket may stay open for hours and must not hold a connection.
    async with AsyncSessionLocal() as db:
        user = await user_for_socket_token(db, token, SCOPE_APP)
        if not user:
            await websocket.close(code=4001)
            return
        try:
            requested = uuid.UUID(organization_id) if organization_id else None
            workspace = await resolve_workspace(db, user, requested)
            workspace.require(perms.AGENTS_READ)
        except (ValueError, HTTPException):
            await websocket.close(code=4003)
            return
        org_id = workspace.organization_id

    queue = chat_events.subscribe(org_id)

    async def pump_events():
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=WS_HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                message = {"event": "ping"}
            if message is None:  # dropped as too slow; the client resyncs
                await websocket.close(code=4008)
                return
            await websocket.send_json(message)

    async def read_client():
        while True:
            text = await websocket.receive_text()
            if text.strip().lower() == "ping":
                await websocket.send_json({"event": "pong"})

    try:
        await websocket.send_json({"event": "ready", "organization_id": str(org_id)})
        tasks = [asyncio.create_task(pump_events()), asyncio.create_task(read_client())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                logger.debug(f"Chat socket closed: {exc}")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"Chat socket error: {e}")
    finally:
        chat_events.unsubscribe(org_id, queue)


# ============================================================================
# Embed script
# ============================================================================


@public_router.get("/widget.js")
async def widget_script(request: Request):
    """
    The embeddable loader.

    A customer pastes one <script> tag with data-voicecon-key. This script reads
    the key, fetches the widget config, and renders a floating launcher + chat
    panel that talks to the public message endpoint. Self-contained (no
    framework, no external CSS) so it drops onto any site.
    """
    from fastapi.responses import Response

    base = public_base_url(request)
    js = _WIDGET_JS.replace("__API_BASE__", base)
    return Response(
        content=js,
        media_type="application/javascript; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )


async def _owned_agent(
    db: AsyncSession, agent_id: str, user: User, org_id: uuid.UUID
) -> Agent:
    """The agent, if it belongs to the caller's current workspace.

    Scoped to the workspace rather than the creator so a teammate can manage
    the chat widget of an agent they didn't personally create.
    """
    try:
        agent_uuid = uuid.UUID(agent_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = (
        await db.execute(
            select(Agent).where(
                and_(Agent.id == agent_uuid, Agent.organization_id == org_id)
            )
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ============================================================================
# The embed script (served by /widget.js). Vanilla JS, no dependencies.
# ============================================================================

_WIDGET_JS = r"""
(function () {
  var API = "__API_BASE__";
  var scriptEl = document.currentScript;
  var KEY = scriptEl && scriptEl.getAttribute("data-voicecon-key");
  if (!KEY) { console.error("[Voicecon] missing data-voicecon-key"); return; }

  var LS_SESSION = "voicecon_chat_session_" + KEY;
  var LS_VISITOR = "voicecon_chat_visitor";
  var visitorId = localStorage.getItem(LS_VISITOR);
  if (!visitorId) {
    visitorId = "v_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem(LS_VISITOR, visitorId);
  }
  var sessionId = localStorage.getItem(LS_SESSION) || null;

  var cfg = {
    title: "Chat with us", subtitle: "", greeting: "Hi! How can I help?",
    accent_color: "#4f46e5", position: "bottom-right", launcher_text: "Chat"
  };
  var opened = false, greeted = false;

  function el(tag, style, text) {
    var e = document.createElement(tag);
    if (style) e.setAttribute("style", style);
    if (text != null) e.textContent = text;
    return e;
  }

  fetch(API + "/api/v1/chat/public/" + KEY + "/config")
    .then(function (r) { if (!r.ok) throw 0; return r.json(); })
    .then(function (data) { cfg = Object.assign(cfg, data.config || {}); render(); })
    .catch(function () { /* widget stays hidden if not enabled */ });

  function render() {
    var side = cfg.position === "bottom-left" ? "left:24px;" : "right:24px;";
    var accent = cfg.accent_color || "#4f46e5";

    // Launcher button
    var launcher = el("button", "position:fixed;bottom:24px;" + side +
      "z-index:2147483000;width:60px;height:60px;border-radius:50%;border:none;cursor:pointer;" +
      "background:" + accent + ";color:#fff;box-shadow:0 6px 24px rgba(0,0,0,.24);" +
      "font-size:26px;display:flex;align-items:center;justify-content:center;transition:transform .15s;");
    launcher.innerHTML = "&#128172;";
    launcher.onmouseenter = function () { launcher.style.transform = "scale(1.06)"; };
    launcher.onmouseleave = function () { launcher.style.transform = "scale(1)"; };

    // Panel
    var panel = el("div", "position:fixed;bottom:96px;" + side +
      "z-index:2147483000;width:360px;max-width:calc(100vw - 32px);height:520px;max-height:calc(100vh - 130px);" +
      "background:#fff;border-radius:16px;box-shadow:0 12px 48px rgba(0,0,0,.28);display:none;flex-direction:column;overflow:hidden;" +
      "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;");

    var header = el("div", "background:" + accent + ";color:#fff;padding:16px 14px 16px 18px;" +
      "display:flex;align-items:flex-start;gap:12px;");
    var heading = el("div", "flex:1;min-width:0;");
    heading.appendChild(el("div", "font-weight:600;font-size:15px;", cfg.title));
    if (cfg.subtitle) heading.appendChild(el("div", "font-size:12px;opacity:.85;margin-top:2px;", cfg.subtitle));
    header.appendChild(heading);

    // Close button. The launcher closes the panel too, but on a phone the
    // panel can cover it, and people look for an X in the corner first.
    var closeBtn = el("button", "flex-shrink:0;width:32px;height:32px;margin:-4px 0 0;padding:0;border:none;" +
      "border-radius:8px;background:transparent;color:#fff;cursor:pointer;display:flex;" +
      "align-items:center;justify-content:center;transition:background .15s;");
    closeBtn.type = "button";
    closeBtn.setAttribute("aria-label", "Close chat");
    closeBtn.title = "Close";
    closeBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2.25" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
    closeBtn.onmouseenter = function () { closeBtn.style.background = "rgba(255,255,255,.18)"; };
    closeBtn.onmouseleave = function () { closeBtn.style.background = "transparent"; };
    header.appendChild(closeBtn);

    var body = el("div", "flex:1;overflow-y:auto;padding:16px;background:#f8fafc;display:flex;flex-direction:column;gap:10px;");

    var footer = el("div", "display:flex;gap:8px;padding:12px;border-top:1px solid #eef2f7;background:#fff;align-items:flex-end;");
    // A textarea (not input) so long messages wrap and Shift+Enter adds a line.
    // It auto-grows up to a cap, then scrolls — never pushing outside the panel.
    var input = el("textarea",
      "flex:1;min-width:0;box-sizing:border-box;resize:none;border:1px solid #e2e8f0;border-radius:10px;" +
      "padding:9px 12px;font-size:14px;line-height:1.4;outline:none;max-height:120px;overflow-y:auto;" +
      "font-family:inherit;");
    input.setAttribute("rows", "1");
    input.setAttribute("placeholder", "Type a message…");
    var send = el("button",
      "flex:0 0 auto;border:none;border-radius:10px;height:38px;padding:0 16px;cursor:pointer;" +
      "background:" + accent + ";color:#fff;font-size:14px;");
    send.textContent = "Send";
    footer.appendChild(input); footer.appendChild(send);

    function autoGrow() {
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 120) + "px";
    }
    input.addEventListener("input", autoGrow);

    panel.appendChild(header); panel.appendChild(body); panel.appendChild(footer);
    document.body.appendChild(panel); document.body.appendChild(launcher);

    // Keyframes cannot live in a style attribute, so the two animations get one
    // <style> tag. Names are prefixed so they cannot collide with the host page.
    // With reduced motion the dots pulse in place instead of bouncing.
    var css = el("style");
    css.textContent =
      "@keyframes voicecon-typing{0%,60%,100%{transform:translateY(0);opacity:.35}30%{transform:translateY(-5px);opacity:1}}" +
      "@keyframes voicecon-pulse{0%,60%,100%{opacity:.3}30%{opacity:1}}" +
      "@keyframes voicecon-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}" +
      ".voicecon-msg{animation:voicecon-in .22s ease-out both}" +
      ".voicecon-dot{animation:voicecon-typing 1.2s ease-in-out infinite}" +
      "@media (prefers-reduced-motion:reduce){.voicecon-msg{animation:none}.voicecon-dot{animation-name:voicecon-pulse}}";
    document.head.appendChild(css);

    function bubble(role, text) {
      var mine = role === "user";
      var wrap = el("div", "display:flex;" + (mine ? "justify-content:flex-end;" : "justify-content:flex-start;"));
      var b = el("div",
        "max-width:80%;padding:9px 13px;border-radius:14px;font-size:14px;line-height:1.4;white-space:pre-wrap;word-wrap:break-word;" +
        (mine ? "background:" + accent + ";color:#fff;border-bottom-right-radius:4px;"
              : "background:#fff;color:#0f172a;border:1px solid #eef2f7;border-bottom-left-radius:4px;"), text);
      wrap.className = "voicecon-msg";
      wrap.appendChild(b); body.appendChild(wrap); body.scrollTop = body.scrollHeight;
      return b;
    }

    // Three bouncing dots in an assistant bubble while the reply is on its way.
    // A static "…" looked like a finished (and empty) answer.
    function typingBubble() {
      var b = bubble("assistant", "");
      b.style.padding = "13px 14px";
      b.style.lineHeight = "0";
      b.setAttribute("role", "status");
      b.setAttribute("aria-label", "Typing a reply");
      for (var i = 0; i < 3; i++) {
        var dot = el("span", "display:inline-block;width:7px;height:7px;border-radius:50%;background:#94a3b8;" +
          "margin:0 2px;animation-delay:" + (i * 0.16) + "s;");
        dot.className = "voicecon-dot";
        b.appendChild(dot);
      }
      body.scrollTop = body.scrollHeight;
      return b.parentNode;
    }

    // Unread dot on the launcher for replies that arrive while it is closed.
    var dot = el("span", "position:absolute;top:4px;right:4px;width:14px;height:14px;border-radius:50%;" +
      "background:#ef4444;border:2px solid #fff;display:none;");
    launcher.style.position = "fixed";
    launcher.appendChild(dot);

    // ---- Conversation sync -------------------------------------------------
    // A team member can answer from the dashboard or the mobile app, so the
    // widget fetches the conversation (on load) and polls for new messages
    // (every few seconds while open, slowly while closed).
    // sends counts submits: a poll that was in flight across a submit may
    // already hold the visitor's own message, so its result is discarded.
    var seen = {}, lastTs = null, lastPoll = 0, polling = false, busy = false, sends = 0;
    var POLL_OPEN_MS = 4000, POLL_CLOSED_MS = 30000;

    function messagesUrl() {
      var u = API + "/api/v1/chat/public/" + KEY + "/sessions/" + encodeURIComponent(sessionId) +
        "/messages?visitor_id=" + encodeURIComponent(visitorId);
      if (lastTs) u += "&after=" + encodeURIComponent(lastTs);
      return u;
    }

    function sync(initial) {
      if (!sessionId || polling) return;
      polling = true; lastPoll = Date.now();
      var at = sends;
      fetch(messagesUrl())
        .then(function (r) {
          if (r.status === 404) { sessionId = null; localStorage.removeItem(LS_SESSION); throw 0; }
          if (!r.ok) throw 0;
          return r.json();
        })
        .then(function (data) {
          if (at !== sends || busy) return;
          var fresh = false;
          (data.messages || []).forEach(function (m) {
            lastTs = m.created_at || lastTs;
            if (seen[m.id]) return;
            seen[m.id] = true;
            if (initial) greeted = true;  // an ongoing chat needs no greeting
            bubble(m.role === "user" ? "user" : "assistant", m.content);
            if (m.role !== "user") fresh = true;
          });
          if (fresh && !opened && !initial) dot.style.display = "block";
        })
        .catch(function () {})
        .finally(function () { polling = false; });
    }
    sync(true);
    setInterval(function () {
      if (busy) return;  // the reply is on its way in the POST response
      if (Date.now() - lastPoll >= (opened ? POLL_OPEN_MS : POLL_CLOSED_MS)) sync(false);
    }, 1000);

    function toggle() {
      opened = !opened;
      panel.style.display = opened ? "flex" : "none";
      if (opened) {
        dot.style.display = "none";
        if (!greeted) { greeted = true; if (cfg.greeting) bubble("assistant", cfg.greeting); }
        // History loaded while the panel was hidden couldn't scroll; land on
        // the newest message.
        body.scrollTop = body.scrollHeight;
        input.focus();
        sync(false);
      }
    }
    launcher.onclick = toggle;
    // Closing keeps the conversation: opening again shows it where it was left.
    closeBtn.onclick = function () { if (opened) { toggle(); launcher.focus(); } };
    panel.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && opened) { toggle(); launcher.focus(); }
    });

    function submit() {
      var text = input.value.trim();
      if (!text || busy) return;
      input.value = "";
      input.style.height = "auto";  // reset the auto-grown height
      bubble("user", text);
      busy = true; sends++; send.disabled = true;
      var typing = typingBubble();
      // The dots give way to the reply as a fresh bubble, so it animates in.
      // No reply text means a person has the conversation; theirs arrives by sync.
      function answer(text) { body.removeChild(typing); if (text) bubble("assistant", text); }

      fetch(API + "/api/v1/chat/public/" + KEY + "/message", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text, session_id: sessionId, visitor_id: visitorId,
          source_url: location.href
        })
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.message_id) seen[data.message_id] = true;
          if (data.reply_message_id) seen[data.reply_message_id] = true;
          answer(data.mode === "human" ? null : (data.reply || "Sorry, I didn't catch that. Could you rephrase?"));
          if (data.session_id) { sessionId = data.session_id; localStorage.setItem(LS_SESSION, sessionId); }
        })
        .catch(function () { answer("Sorry, I couldn't reach the server."); })
        .finally(function () { busy = false; send.disabled = false; input.focus(); });
    }
    send.onclick = submit;
    // Enter sends; Shift+Enter inserts a newline (the standard chat behaviour).
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
    });
  }
})();
"""
