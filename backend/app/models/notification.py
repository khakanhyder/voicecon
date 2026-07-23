"""
In-app notification model.

A Notification is a message delivered to a single user, surfaced by the header
bell. Some notifications are *actionable* (e.g. a team invitation with
Accept/Reject); their ``data`` payload carries what the frontend needs to act
(such as the invitation token), and ``is_actioned`` records that a decision was
made so the action buttons collapse.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, ForeignKey, JSON, Uuid
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


# Notification type constants
NOTIFY_TEAM_INVITATION = "team_invitation"


class Notification(Base):
    """A single in-app notification for a user."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    type: Mapped[str] = mapped_column(String(50), nullable=False, default="info")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")

    # Arbitrary structured payload (e.g. {"invitation_token": "...", "organization_name": "..."}).
    data: Mapped[dict] = mapped_column(JSON, default=dict)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    # True once an actionable notification (like an invite) has been decided.
    is_actioned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<Notification(user={self.user_id}, type={self.type}, read={self.is_read})>"


# Forward references
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User
