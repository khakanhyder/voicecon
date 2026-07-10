"""
Company profile model — stores onboarding company information collected
right after sign-up (Figma "Company Information" screen).

One row per organization (one-to-one). Kept as a dedicated table so it is
created automatically by ``Base.metadata.create_all`` in development without
altering existing tables.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CompanyProfile(Base):
    """Company / assistant details captured during onboarding."""

    __tablename__ = "company_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Company information
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry_type: Mapped[Optional[str]] = mapped_column(String(100))
    company_size: Mapped[Optional[str]] = mapped_column(String(50))
    company_url: Mapped[Optional[str]] = mapped_column(String(255))

    # Assistant configuration
    assistant_name: Mapped[Optional[str]] = mapped_column(String(255))
    preferred_language: Mapped[str] = mapped_column(String(50), default="English")
    assistant_instructions: Mapped[Optional[str]] = mapped_column(Text)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50))

    # Onboarding progress
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_step: Mapped[str] = mapped_column(
        String(20), default="company"
    )  # company | pricing | billing | done

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<CompanyProfile(org={self.organization_id}, company={self.company_name})>"


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import Organization, User
