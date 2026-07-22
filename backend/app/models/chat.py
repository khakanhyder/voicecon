"""
Chat widget models.

The chat widget is a text delivery channel for an existing agent — same brain,
different mouth. These tables add the channel on top of the agent without
touching the agent itself:

  ChatWidget   one per agent that's exposed as a widget; holds the public embed
               key and branding.
  ChatSession  one visitor conversation.
  ChatMessage  the turns within a session.

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
    """A public, embeddable text channel for an agent."""

    __tablename__ = "chat_widgets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"),
        unique=True, index=True, nullable=False,
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

    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)

    # Which tool the assistant used this turn, if any — the chat equivalent of
    # a call's action log, and what makes tool→workflow visible in reporting.
    tool_name: Mapped[Optional[str]] = mapped_column(String(128))

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    session: Mapped["ChatSession"] = relationship(
        "ChatSession", back_populates="messages"
    )
