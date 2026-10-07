"""
Chat widget models.

The chat widget is a text delivery channel for an existing agent — same brain,
different mouth. These tables add the channel on top of the agent without
touching the agent itself:

  ChatWidget   one per agent that's exposed as a widget; holds the public embed
               key and branding.
  ChatSession  one visitor conversation.
  ChatMessage  the turns within a session.
  DeviceToken  a signed-in phone that receives push notifications for the
               chat inbox (the mobile app).

All three are new tables, so a fresh deploy picks them up via create_all and
production via the accompanying Alembic migration.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChatWidget(Base):
    """A chatbot: a public, embeddable text channel answered by an agent.

    A first-class workspace object (Dashboard → Chatbot), not a setting of an
    agent. It is linked to the agent that answers it, and that link can be
    changed — or be empty, in which case the embed stays installed but hides
    itself until an agent is chosen. Deleting the agent leaves the chatbot,
    its embed key and its history in place.
    """

    __tablename__ = "chat_widgets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"),
        index=True, nullable=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)

    # Public token embedded on customer sites. Unguessable; the only credential
    # the widget uses, so the dashboard JWT never leaves the app.
    public_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Branding the customer controls: title, subtitle, greeting, accent colour,
    # position, launcher label, avatar. Free-form so new options need no
    # migration.
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    sessions: Mapped[List["ChatSession"]] = relationship(
        "ChatSession", back_populates="widget", cascade="all, delete-orphan"
    )


class ChatSession(Base):
    """One visitor's conversation with the widget."""

    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    widget_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chat_widgets.id", ondelete="CASCADE"),
        index=True,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)

    # Anonymous visitor identifier the widget stores in the browser, so a
    # returning visitor keeps continuity without any login.
    visitor_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)

    status: Mapped[str] = mapped_column(String(20), default="active")
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    # Who answers the visitor: "ai" (the linked agent) or "human" (a team
    # member replying from the dashboard or the mobile app). A human reply
    # switches the conversation to "human" so the agent and the person never
    # answer the same message; "release" hands it back to the agent.
    mode: Mapped[str] = mapped_column(String(10), default="ai", server_default="ai")

    # Visitor messages nobody on the team has opened yet. Shared by the whole
    # workspace (it is one inbox), reset when anyone opens or answers it.
    unread_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # The newest message, so the inbox list needs no per-row transcript query.
    last_message_preview: Mapped[Optional[str]] = mapped_column(String(300))
    last_message_role: Mapped[Optional[str]] = mapped_column(String(20))

    # Reporting parity with calls: page the widget was opened on, referrer, UA.
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)

    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    widget: Mapped["ChatWidget"] = relationship("ChatWidget", back_populates="sessions")
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    """A single turn in a chat session."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        index=True,
    )

    # user = the website visitor, assistant = the agent, human = a team member.
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)

    # The team member who wrote a "human" message; NULL for the other roles.
    sender_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Which tool the assistant used this turn, if any — the chat equivalent of
    # a call's action log, and what makes tool→workflow visible in reporting.
    tool_name: Mapped[Optional[str]] = mapped_column(String(128))

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    session: Mapped["ChatSession"] = relationship(
        "ChatSession", back_populates="messages"
    )


class DeviceToken(Base):
    """A phone signed in to the mobile app, reachable by push (FCM).

    Keyed by the FCM registration token, which identifies an app install; when
    a different account signs in on the same phone the row moves to that user.
    ``token_version`` is the user's session version at registration: signing
    out everywhere or resetting the password bumps the user's version, and a
    stale row is then skipped (and removed) instead of pushing chat contents to
    a phone that is no longer signed in.
    """

    __tablename__ = "device_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(20), default="android")  # android | ios
    device_name: Mapped[Optional[str]] = mapped_column(String(255))
    app_version: Mapped[Optional[str]] = mapped_column(String(50))
    token_version: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
