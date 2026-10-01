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
import logging
import secrets
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_current_org_id
from app.core.urls import public_base_url
from app.database import get_db
from app.models.agent import Agent
from app.models.chat import ChatMessage, ChatSession, ChatWidget
from app.models.user import User
from app.core.time import utc_iso

logger = logging.getLogger(__name__)

router = APIRouter()

#: Routes that must stay reachable without a workspace context — carrier and
#: payment-provider webhooks, and the public embed surfaces. They live on their
#: own router so the authenticated router can carry a blanket permission guard
#: (see app.api.v1.api) without accidentally locking these out.
public_router = APIRouter()


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
    db: AsyncSession = Depends(get_db),
):
    """
    Send a visitor message and get the agent's reply.

    Body: ``{"session_id"?: str, "visitor_id"?: str, "message": str,
             "source_url"?: str}``. Omit session_id to start a conversation;
    the returned id continues it.
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

    # Load recent history for context.
    history_rows = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(desc(ChatMessage.created_at))
            .limit(HISTORY_TURNS)
        )
    ).scalars().all()
    history = [
        {"role": m.role, "content": m.content} for m in reversed(history_rows)
    ]

    # Persist the visitor's message before running, so a failure mid-turn still
    # leaves a record.
    db.add(ChatMessage(session_id=session.id, role="user", content=message))

    try:
        result = await get_agent_chat_service(db).respond(agent, history, message)
        reply = result.reply or "Sorry, I didn't catch that. Could you rephrase?"
        tool_name = result.tool_name
    except Exception as e:
        logger.error(f"Chat turn failed: {e}", exc_info=True)
        reply = "Sorry, something went wrong on our end. Please try again."
        tool_name = None

    db.add(
        ChatMessage(
            session_id=session.id, role="assistant", content=reply, tool_name=tool_name
        )
    )
    session.message_count += 2
    session.last_activity_at = datetime.utcnow()
    await db.commit()

    return {"session_id": str(session.id), "reply": reply}


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
            )
            .where(ChatSession.widget_id.in_(widget_ids))
            .group_by(ChatSession.widget_id)
        )
    ).all()
    return {
        widget_id: {
            "session_count": count,
            "last_activity_at": utc_iso(last),
        }
        for widget_id, count, last in rows
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """A chatbot's conversations, newest first — whichever agent answered them."""
    widget = await _owned_chatbot(db, chatbot_id, org_id)
    return await _sessions_page(db, ChatSession.widget_id == widget.id, page, page_size)


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


async def _sessions_page(db: AsyncSession, condition, page: int, page_size: int) -> Dict[str, Any]:
    base = select(ChatSession).where(condition)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    rows = (
        await db.execute(
            base.order_by(desc(ChatSession.started_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return {
        "sessions": [
            {
                "id": str(s.id),
                "chatbot_id": str(s.widget_id),
                "agent_id": str(s.agent_id) if s.agent_id else None,
                "visitor_id": s.visitor_id,
                "status": s.status,
                "message_count": s.message_count,
                "source_url": s.source_url,
                "started_at": utc_iso(s.started_at),
                "last_activity_at": utc_iso(s.last_activity_at),
            }
            for s in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Full transcript of one chat session (for reporting drill-down)."""
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")

    session = (
        await db.execute(select(ChatSession).where(ChatSession.id == session_uuid))
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Ownership by workspace: the agent that answered may since have been
    # deleted or unlinked, but the conversation still belongs to the chatbot.
    if session.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Session not found")

    rows = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_uuid)
            .order_by(ChatMessage.created_at)
        )
    ).scalars().all()

    return {
        "session_id": session_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "tool_name": m.tool_name,
                "created_at": utc_iso(m.created_at),
            }
            for m in rows
        ],
    }


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

    var header = el("div", "background:" + accent + ";color:#fff;padding:16px 18px;");
    header.appendChild(el("div", "font-weight:600;font-size:15px;", cfg.title));
    if (cfg.subtitle) header.appendChild(el("div", "font-size:12px;opacity:.85;margin-top:2px;", cfg.subtitle));

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

    function toggle() {
      opened = !opened;
      panel.style.display = opened ? "flex" : "none";
      if (opened) {
        if (!greeted) { greeted = true; if (cfg.greeting) bubble("assistant", cfg.greeting); }
        input.focus();
      }
    }
    launcher.onclick = toggle;

    var busy = false;
    function submit() {
      var text = input.value.trim();
      if (!text || busy) return;
      input.value = "";
      input.style.height = "auto";  // reset the auto-grown height
      bubble("user", text);
      busy = true; send.disabled = true;
      var typing = typingBubble();
      // The dots give way to the reply as a fresh bubble, so it animates in.
      function answer(text) { body.removeChild(typing); bubble("assistant", text); }

      fetch(API + "/api/v1/chat/public/" + KEY + "/message", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text, session_id: sessionId, visitor_id: visitorId,
          source_url: location.href
        })
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          answer(data.reply || "Sorry, I didn't catch that. Could you rephrase?");
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
