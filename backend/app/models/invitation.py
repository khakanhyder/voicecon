"""
Team invitation model.

An Invitation is a *pending* offer for someone to join an organization. A
membership (OrganizationMember) is only created when the invite is accepted, so
pending invites never pollute the member list. Invites are addressed by email
and carry a secure random ``token`` used by the email Accept/Reject links.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text, ForeignKey, Uuid
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


class Invitation(Base):
    """A pending invitation for a user to join an organization."""

    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), default="member", nullable=False)

    # Secure, URL-safe token used in the email Accept/Reject links.
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)

    # pending | accepted | rejected | canceled | expired
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)

    # Who sent it, and the existing user it targets (if the email already has an account).
    invited_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    invited_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", foreign_keys=[organization_id])
    inviter: Mapped[Optional["User"]] = relationship("User", foreign_keys=[invited_by])

    @property
    def is_pending(self) -> bool:
        return self.status == "pending" and self.expires_at > datetime.utcnow()

    def __repr__(self) -> str:
        return f"<Invitation(email={self.email}, org={self.organization_id}, status={self.status})>"


# Forward references
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User, Organization
