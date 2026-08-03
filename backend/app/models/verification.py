"""
One-time codes emailed to a user to prove they control an address.

Used by two flows:

- ``email_verification`` — proving the address at sign-up, before the account
  exists (so the row is keyed by email, not by user id).
- ``password_reset`` — proving the address before setting a new password.

Only the HMAC of the code is stored, so a database leak does not hand out
working codes. Rows are single-use (``consumed_at``), expire, and count failed
attempts so a 6-digit code cannot be brute-forced.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: What a code authorises. Kept as plain strings to avoid a DB enum migration.
PURPOSE_EMAIL_VERIFICATION = "email_verification"
PURPOSE_PASSWORD_RESET = "password_reset"


class VerificationCode(Base):
    """A single one-time code sent to an email address."""

    __tablename__ = "verification_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Lower-cased address the code was sent to. Not a foreign key: sign-up
    # verification happens before the user row exists.
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)

    # HMAC-SHA256 of the code, keyed by the app secret.
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        # Every lookup is "the live code for this address and purpose".
        Index("ix_verification_codes_email_purpose", "email", "purpose"),
    )

    def __repr__(self) -> str:
        return (
            f"<VerificationCode(email={self.email}, purpose={self.purpose}, "
            f"consumed={self.consumed_at is not None})>"
        )
