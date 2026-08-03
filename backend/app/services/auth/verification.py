"""
Issuing and checking the one-time codes emailed during sign-up and password
reset.

A 6-digit code is only 10^6 possibilities, so the guarantees come from the rules
around it rather than from the code itself:

- it expires (10 minutes) and can be used once;
- a code dies after 5 wrong guesses;
- issuing is rate limited per address, both a short cooldown and an hourly cap,
  so the endpoint cannot be used to spam someone's inbox;
- only an HMAC of the code is stored, keyed by the app secret, so a database
  leak does not hand out working codes.
"""
import hmac
import logging
import secrets
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.verification import (
    PURPOSE_EMAIL_VERIFICATION,
    PURPOSE_PASSWORD_RESET,
    VerificationCode,
)

logger = logging.getLogger(__name__)

CODE_LENGTH = 6
CODE_TTL_MINUTES = 10
MAX_ATTEMPTS = 5
#: Wait between two sends to the same address, so "Resend" cannot be hammered.
RESEND_COOLDOWN_SECONDS = 60
#: Ceiling per address per hour, so the endpoint is not an email cannon.
MAX_SENDS_PER_HOUR = 5

__all__ = [
    "PURPOSE_EMAIL_VERIFICATION",
    "PURPOSE_PASSWORD_RESET",
    "CODE_TTL_MINUTES",
    "VerificationError",
    "RateLimited",
    "issue_code",
    "confirm_code",
    "normalize_email",
]


class VerificationError(Exception):
    """A code could not be issued or accepted. The message is user-facing."""


class RateLimited(VerificationError):
    """Too many codes requested for this address."""

    def __init__(self, message: str, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)


def normalize_email(email: str) -> str:
    """Codes are keyed by address, so casing must not create a second bucket."""
    return email.strip().lower()


def _hash_code(email: str, purpose: str, code: str) -> str:
    """
    HMAC the code with the app secret.

    The address and purpose are part of the message, so a code issued for one
    address or flow cannot be replayed against another.
    """
    payload = f"{normalize_email(email)}:{purpose}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), payload, sha256).hexdigest()


def _generate_code() -> str:
    """A zero-padded numeric code — typable on a phone keypad."""
    return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"


async def issue_code(
    db: AsyncSession,
    email: str,
    purpose: str,
) -> Tuple[str, datetime]:
    """
    Create a fresh code for `email`, retiring any earlier one.

    Returns:
        (code, expires_at) — the plaintext code, to be emailed and then
        forgotten; it is never stored or returned again.

    Raises:
        RateLimited: the cooldown or the hourly cap was hit.
    """
    email = normalize_email(email)
    now = datetime.utcnow()

    last = await db.execute(
        select(VerificationCode)
        .where(VerificationCode.email == email, VerificationCode.purpose == purpose)
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    latest: Optional[VerificationCode] = last.scalar_one_or_none()

    if latest:
        elapsed = (now - latest.created_at).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            wait = int(RESEND_COOLDOWN_SECONDS - elapsed) or 1
            raise RateLimited(
                f"A code was just sent. Please wait {wait} seconds before "
                f"requesting another.",
                retry_after_seconds=wait,
            )

    recent = await db.execute(
        select(func.count(VerificationCode.id)).where(
            VerificationCode.email == email,
            VerificationCode.purpose == purpose,
            VerificationCode.created_at > now - timedelta(hours=1),
        )
    )
    if (recent.scalar() or 0) >= MAX_SENDS_PER_HOUR:
        raise RateLimited(
            "Too many codes requested for this email. Please try again in an hour.",
            retry_after_seconds=3600,
        )

    # Retire outstanding codes: only the newest one should ever work.
    await db.execute(
        update(VerificationCode)
        .where(
            VerificationCode.email == email,
            VerificationCode.purpose == purpose,
            VerificationCode.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )

    code = _generate_code()
    expires_at = now + timedelta(minutes=CODE_TTL_MINUTES)

    db.add(
        VerificationCode(
            email=email,
            purpose=purpose,
            code_hash=_hash_code(email, purpose, code),
            expires_at=expires_at,
            created_at=now,
        )
    )
    await db.commit()

    logger.info(f"Issued {purpose} code for {email} (expires {expires_at.isoformat()})")
    return code, expires_at


async def confirm_code(
    db: AsyncSession,
    email: str,
    purpose: str,
    code: str,
) -> None:
    """
    Check a submitted code and consume it.

    Raises:
        VerificationError: no live code, wrong code, expired, or out of attempts.
            The message is deliberately vague about which, so the endpoint does
            not confirm whether an address has a code outstanding.
    """
    email = normalize_email(email)
    now = datetime.utcnow()

    result = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.email == email,
            VerificationCode.purpose == purpose,
            VerificationCode.consumed_at.is_(None),
        )
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    record: Optional[VerificationCode] = result.scalar_one_or_none()

    if record is None:
        raise VerificationError(
            "That code is not valid. Request a new one and try again."
        )

    if record.expires_at <= now:
        record.consumed_at = now
        await db.commit()
        raise VerificationError("That code has expired. Request a new one.")

    if record.attempts >= MAX_ATTEMPTS:
        record.consumed_at = now
        await db.commit()
        raise VerificationError(
            "Too many incorrect attempts. Request a new code and try again."
        )

    expected = record.code_hash
    submitted = _hash_code(email, purpose, (code or "").strip())

    if not hmac.compare_digest(expected, submitted):
        record.attempts += 1
        await db.commit()
        remaining = MAX_ATTEMPTS - record.attempts
        if remaining <= 0:
            raise VerificationError(
                "Too many incorrect attempts. Request a new code and try again."
            )
        raise VerificationError(
            f"That code is not correct. {remaining} attempt"
            f"{'s' if remaining != 1 else ''} left."
        )

    record.consumed_at = now
    await db.commit()
    logger.info(f"Confirmed {purpose} code for {email}")
