"""Program-wide rules, codes and the small helpers every affiliate module shares."""
from __future__ import annotations

import re
import secrets
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate import Affiliate, AffiliateProgram

#: The one rule staff cannot change: only yearly payments earn commission.
COMMISSION_BILLING_PERIOD = "yearly"

#: Invoices that pay for a new year of service. A proration from a mid-year
#: upgrade (``subscription_update``) earns only while a commissioned year runs.
BASE_BILLING_REASONS = frozenset({"subscription_create", "subscription_cycle"})
PRORATION_BILLING_REASONS = frozenset({"subscription_update"})

CENT = Decimal("0.01")

_REFERRAL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")
_COUPON_RE = re.compile(r"^[A-Z0-9](?:[A-Z0-9_-]{1,38}[A-Z0-9])$")


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def cents_to_money(cents) -> Decimal:
    return money(Decimal(int(cents or 0)) / 100)


def utcnow() -> datetime:
    return datetime.utcnow()


async def get_program(db: AsyncSession) -> AffiliateProgram:
    """The program row, created with defaults the first time it is read."""
    program = await db.get(AffiliateProgram, 1)
    if program is None:
        program = AffiliateProgram(
            id=1,
            enabled=True,
            default_commission_percent=Decimal("20.00"),
            hold_days=30,
            min_payout_amount=Decimal("50.00"),
            cookie_days=60,
            referral_window_days=365,
            max_commission_payments=1,
            eligible_plan_slugs=[],
        )
        db.add(program)
        await db.flush()
    return program


def max_payments_for(affiliate: Affiliate, program: AffiliateProgram) -> Optional[int]:
    """How many yearly payments per customer earn this affiliate commission (None: all)."""
    if affiliate.custom_max_payments:
        return affiliate.max_commission_payments
    return program.max_commission_payments


# ---- Codes ----


def normalize_referral_code(raw: Optional[str]) -> str:
    return (raw or "").strip().lower()


def normalize_coupon_code(raw: Optional[str]) -> str:
    return (raw or "").strip().upper()


def referral_code_problem(code: str) -> Optional[str]:
    if not _REFERRAL_RE.match(code):
        return "Referral codes are 3-40 characters: lowercase letters, numbers and hyphens."
    return None


def coupon_code_problem(code: str) -> Optional[str]:
    if not _COUPON_RE.match(code):
        return "Coupon codes are 3-40 characters: letters, numbers, hyphens and underscores."
    return None


def suggest_referral_code(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:24] or "partner"
    return f"{base}-{secrets.token_hex(2)}"


async def unique_referral_code(db: AsyncSession, name: str) -> str:
    for _ in range(20):
        code = suggest_referral_code(name)
        taken = await db.scalar(select(Affiliate.id).where(Affiliate.referral_code == code))
        if taken is None:
            return code
    return f"partner-{secrets.token_hex(6)}"


async def unique_coupon_code(db: AsyncSession, referral_code: str) -> str:
    """A free coupon code derived from a referral code (``pat-smith`` -> ``PATSMITH``)."""
    base = re.sub(r"[^A-Z0-9]", "", (referral_code or "").upper())[:30]
    candidates = [base] if len(base) >= 3 else []
    candidates += [f"{base}{secrets.token_hex(2).upper()}" for _ in range(20)]
    for code in candidates:
        if coupon_code_problem(code):
            continue
        taken = await db.scalar(
            select(Affiliate.id).where(
                or_(Affiliate.coupon_code == code, Affiliate.referral_code == normalize_referral_code(code))
            )
        )
        if taken is None:
            return code
    return f"PARTNER{secrets.token_hex(4).upper()}"


async def find_by_code(db: AsyncSession, raw: Optional[str]) -> Optional[Affiliate]:
    """The affiliate a ``?ref=`` value or coupon code belongs to, if any."""
    if not raw or len(raw) > 60:
        return None
    affiliate = await db.scalar(
        select(Affiliate).where(Affiliate.referral_code == normalize_referral_code(raw))
    )
    if affiliate is None:
        affiliate = await db.scalar(
            select(Affiliate).where(Affiliate.coupon_code == normalize_coupon_code(raw))
        )
    return affiliate


def mask_email(email: Optional[str]) -> str:
    """``jo***@gmail.com`` — enough for an affiliate to recognise a referral."""
    if not email or "@" not in email:
        return "—"
    local, domain = email.split("@", 1)
    if domain.endswith("deleted.invalid"):
        return "Deleted account"
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}***@{domain}"
