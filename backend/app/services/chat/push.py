"""
Push notifications for the chat inbox (mobile app), via Firebase Cloud
Messaging's HTTP v1 API.

When a website visitor writes to any chatbot, every member of that workspace
who can read chatbots gets a push on each phone they are signed in on. Pushes
are collapsed per conversation (Android ``tag`` / iOS ``apns-collapse-id``), so
a chatty visitor updates one notification instead of stacking twenty.

Off unless ``FIREBASE_SERVICE_ACCOUNT_JSON`` is set — the rest of the mobile
API (inbox, replies, the socket) works without it.

Runs after the HTTP response (FastAPI background task), so it opens its own DB
session: the request's session is closed by then (see the 2026-09-18 pool leak).
"""
import asyncio
import base64
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import delete, select

from app.core import permissions as perms
from app.core.config import settings

logger = logging.getLogger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_SEND_URL = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"

#: Android notification channel the app must create (see the mobile guide).
ANDROID_CHANNEL_ID = "chat_messages"

_credentials = None
_project_id: Optional[str] = None


def _service_account_info() -> Optional[dict]:
    raw = (settings.FIREBASE_SERVICE_ACCOUNT_JSON or "").strip()
    if not raw:
        return None
    try:
        if raw.startswith("{"):
            return json.loads(raw)
        if os.path.isfile(raw):
            with open(raw) as f:
                return json.load(f)
        return json.loads(base64.b64decode(raw).decode())
    except Exception as e:
        logger.error(f"FIREBASE_SERVICE_ACCOUNT_JSON is not valid service-account JSON: {e}")
        return None


def push_configured() -> bool:
    return _service_account_info() is not None


async def _access_token() -> Optional[str]:
    """A short-lived OAuth token for FCM, refreshed when it expires."""
    global _credentials, _project_id
    if _credentials is None:
        info = _service_account_info()
        if info is None:
            return None
        from google.oauth2 import service_account

        _credentials = service_account.Credentials.from_service_account_info(info, scopes=[FCM_SCOPE])
        _project_id = info.get("project_id")

    if not _credentials.valid:
        from google.auth.transport.requests import Request

        # google-auth refreshes synchronously; keep it off the event loop.
        await asyncio.to_thread(_credentials.refresh, Request())
    return _credentials.token


def _fcm_message(token: str, title: str, body: str, data: Dict[str, str], collapse: str) -> dict:
    return {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
            # FCM data values must be strings.
            "data": {k: str(v) for k, v in data.items() if v is not None},
            "android": {
                "priority": "high",
                "collapse_key": collapse,
                "notification": {"tag": collapse, "channel_id": ANDROID_CHANNEL_ID},
            },
            "apns": {
                "headers": {"apns-collapse-id": collapse[:64], "apns-priority": "10"},
                "payload": {"aps": {"sound": "default", "thread-id": collapse}},
            },
        }
    }


def _is_dead_token(resp: httpx.Response) -> bool:
    """FCM's answer for an uninstalled app or a malformed/foreign token."""
    if resp.status_code not in (400, 404):
        return False
    try:
        details = resp.json().get("error", {}).get("details", [])
    except Exception:
        return False
    codes = {d.get("errorCode") for d in details if isinstance(d, dict)}
    return bool(codes & {"UNREGISTERED", "INVALID_ARGUMENT", "SENDER_ID_MISMATCH"})


async def send_push(tokens: List[str], title: str, body: str, data: Dict[str, Any], collapse: str) -> List[str]:
    """Send one notification to each token. Returns the tokens FCM says are dead."""
    if not tokens:
        return []
    try:
        access = await _access_token()
    except Exception as e:
        logger.error(f"Could not get an FCM access token: {e}")
        return []
    if not access or not _project_id:
        return []

    dead: List[str] = []
    url = FCM_SEND_URL.format(project=_project_id)
    headers = {"Authorization": f"Bearer {access}"}
    async with httpx.AsyncClient(timeout=10) as client:
        for token in tokens:
            try:
                resp = await client.post(url, headers=headers, json=_fcm_message(token, title, body, data, collapse))
            except httpx.HTTPError as e:
                logger.warning(f"FCM send failed (transport): {e}")
                continue
            if resp.status_code == 200:
                continue
            if _is_dead_token(resp):
                dead.append(token)
            else:
                logger.warning(f"FCM send failed ({resp.status_code}): {resp.text[:300]}")
    return dead


async def recipient_tokens(db, organization_id: uuid.UUID) -> List[str]:
    """FCM tokens of every still-signed-in phone of a member who can read chats.

    Rows registered under an older session version (the user signed out
    everywhere or reset their password since) are removed here.
    """
    from app.models.chat import DeviceToken
    from app.models.user import OrganizationMember, User

    rows = (
        await db.execute(
            select(DeviceToken, User.token_version, OrganizationMember.role)
            .join(User, User.id == DeviceToken.user_id)
            .join(OrganizationMember, OrganizationMember.user_id == DeviceToken.user_id)
            .where(OrganizationMember.organization_id == organization_id, User.is_active.is_(True))
        )
    ).all()

    tokens, stale = [], []
    for device, user_version, role in rows:
        if (device.token_version or 0) != (user_version or 0):
            stale.append(device.id)
        elif perms.has_permission(role, perms.AGENTS_READ):
            tokens.append(device.token)
    if stale:
        await db.execute(delete(DeviceToken).where(DeviceToken.id.in_(stale)))
        await db.commit()
    return tokens


async def notify_visitor_message(session_id: uuid.UUID, message_id: uuid.UUID, new_conversation: bool) -> None:
    """Push "a visitor wrote" to the workspace's phones. Never raises."""
    if not push_configured():
        return
    from app.database import AsyncSessionLocal
    from app.models.chat import ChatMessage, ChatSession, ChatWidget, DeviceToken

    try:
        async with AsyncSessionLocal() as db:
            session = await db.get(ChatSession, session_id)
            message = await db.get(ChatMessage, message_id)
            if session is None or message is None:
                return
            widget = await db.get(ChatWidget, session.widget_id)
            tokens = await recipient_tokens(db, session.organization_id)
            if not tokens:
                return

            chatbot_name = (widget.name if widget else None) or "Website chat"
            title = f"New conversation · {chatbot_name}" if new_conversation else chatbot_name
            text = message.content.strip()
            body = text if len(text) <= 180 else text[:177] + "…"
            data = {
                "type": "chat_message",
                "organization_id": str(session.organization_id),
                "chatbot_id": str(session.widget_id),
                "session_id": str(session.id),
                "message_id": str(message.id),
                "new_conversation": "true" if new_conversation else "false",
                "mode": session.mode or "ai",
            }
            dead = await send_push(tokens, title, body, data, collapse=str(session.id))
            if dead:
                await db.execute(delete(DeviceToken).where(DeviceToken.token.in_(dead)))
                await db.commit()
    except Exception as e:
        logger.error(f"Chat push notification failed: {e}", exc_info=True)
