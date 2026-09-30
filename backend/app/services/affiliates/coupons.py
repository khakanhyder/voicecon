"""Affiliate coupon codes: who may use one, and the provider objects behind it.

The discount itself is applied by the payment provider — a Stripe coupon on the
subscription, or a Polar discount on the hosted checkout — so the invoice the
customer pays, and the commission computed from it, are already net of it.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.affiliate import (
    AFFILIATE_EARNING_STATUSES,
    DISCOUNT_ALL_PLANS,
    DISCOUNT_REPEATING,
    Affiliate,
)
from app.services.affiliates import attribution
from app.services.affiliates.program import get_program, normalize_coupon_code

logger = logging.getLogger(__name__)


class CouponError(Exception):
    """A code the customer cannot use. ``public_message`` is safe to show them."""

    @property
    def public_message(self) -> str:
        return str(self)


@dataclass
class CouponQuote:
    affiliate: Affiliate
    code: str
    percent_off: Decimal
    duration: str
    duration_in_months: Optional[int]
    applies_to: str

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "percent_off": float(self.percent_off),
            "duration": self.duration,
            "duration_in_months": self.duration_in_months,
            "applies_to": self.applies_to,
            "description": describe(self.percent_off, self.duration, self.duration_in_months),
        }


def describe(percent: Decimal, duration: str, months: Optional[int]) -> str:
    pct = f"{float(percent):g}% off"
    if duration == "forever":
        return f"{pct} every payment"
    if duration == DISCOUNT_REPEATING and months:
        return f"{pct} for {months} month{'s' if months != 1 else ''}"
    return f"{pct} your first payment"


def has_discount(affiliate: Affiliate) -> bool:
    return bool(affiliate.coupon_code) and Decimal(affiliate.discount_percent or 0) > 0


async def quote(
    db: AsyncSession,
    code: Optional[str],
    *,
    organization_id: uuid.UUID,
    user_id: Optional[uuid.UUID],
    billing_period: str,
) -> CouponQuote:
    """Check ``code`` for this workspace and checkout, or raise :class:`CouponError`."""
    normalized = normalize_coupon_code(code)
    if not normalized:
        raise CouponError("Enter a coupon code.")
    affiliate = await attribution.usable_affiliate(db, normalized)
    if affiliate is None or affiliate.coupon_code != normalized or not has_discount(affiliate):
        raise CouponError("That coupon code isn't valid.")
    if user_id is not None and user_id == affiliate.user_id:
        raise CouponError("You can't use your own partner coupon.")
    if affiliate.discount_applies_to != DISCOUNT_ALL_PLANS and billing_period != "yearly":
        raise CouponError("This coupon only applies to annual plans. Switch to yearly billing to use it.")
    if await attribution.is_existing_customer(db, organization_id):
        raise CouponError("This coupon is for new customers only.")
    return CouponQuote(
        affiliate=affiliate,
        code=normalized,
        percent_off=Decimal(affiliate.discount_percent),
        duration=affiliate.discount_duration,
        duration_in_months=affiliate.discount_duration_months if affiliate.discount_duration == DISCOUNT_REPEATING else None,
        applies_to=affiliate.discount_applies_to,
    )


async def apply(
    db: AsyncSession,
    code: Optional[str],
    *,
    organization_id: uuid.UUID,
    user_id: Optional[uuid.UUID],
    billing_period: str,
) -> CouponQuote:
    """Validate, and credit the workspace to the coupon's affiliate if it has no referral yet."""
    result = await quote(
        db, code, organization_id=organization_id, user_id=user_id, billing_period=billing_period
    )
    await attribution.attribute(
        db,
        affiliate=result.affiliate,
        organization_id=organization_id,
        user_id=user_id,
        source=attribution.SOURCE_COUPON,
    )
    return result


async def suggested_code(db: AsyncSession, organization_id: uuid.UUID) -> Optional[str]:
    """The coupon of the affiliate this workspace was referred by, to prefill checkout."""
    referral = await attribution.referral_for(db, organization_id)
    if referral is None:
        return None
    affiliate = await db.get(Affiliate, referral.affiliate_id)
    if affiliate is None or affiliate.status not in AFFILIATE_EARNING_STATUSES or not has_discount(affiliate):
        return None
    return affiliate.coupon_code


# ---- Provider objects ----


def _terms(affiliate: Affiliate) -> str:
    months = affiliate.discount_duration_months if affiliate.discount_duration == DISCOUNT_REPEATING else 0
    return f"{Decimal(affiliate.discount_percent):.2f}:{affiliate.discount_duration}:{months or 0}"


def _account_tag(secret: Optional[str]) -> str:
    # A coupon lives in one Stripe account and mode; a switched key needs a new one.
    return hashlib.sha256((secret or "").encode()).hexdigest()[:10]


async def stripe_coupon_id(affiliate: Affiliate) -> str:
    """A Stripe coupon with the affiliate's current terms. The caller commits."""
    import stripe

    key = f"{_terms(affiliate)}:{_account_tag(settings.stripe_secret_key)}"
    if affiliate.stripe_coupon_id and affiliate.stripe_coupon_key == key:
        return affiliate.stripe_coupon_id

    params = {
        "percent_off": float(affiliate.discount_percent),
        "duration": affiliate.discount_duration,
        "name": f"Partner {affiliate.coupon_code}"[:40],
        "metadata": {"affiliate_id": str(affiliate.id), "coupon_code": affiliate.coupon_code or ""},
    }
    if affiliate.discount_duration == DISCOUNT_REPEATING:
        params["duration_in_months"] = int(affiliate.discount_duration_months or 1)
    coupon = await asyncio.to_thread(stripe.Coupon.create, **params)
    affiliate.stripe_coupon_id = coupon.id
    affiliate.stripe_coupon_key = key
    return coupon.id


async def polar_discount_id(affiliate: Affiliate) -> str:
    """A Polar discount with the affiliate's current terms. The caller commits."""
    from app.services.billing import polar_service

    key = f"{_terms(affiliate)}:{settings.polar_api_base}"
    if affiliate.polar_discount_id and affiliate.polar_discount_key == key:
        return affiliate.polar_discount_id

    body = {
        "name": f"Partner {affiliate.coupon_code}"[:64],
        "type": "percentage",
        "basis_points": int(Decimal(affiliate.discount_percent) * 100),
        "duration": affiliate.discount_duration,
        "metadata": {"affiliate_id": str(affiliate.id)},
    }
    if affiliate.discount_duration == DISCOUNT_REPEATING:
        body["duration_in_months"] = int(affiliate.discount_duration_months or 1)
    discount = await polar_service.get_polar_client().create_discount(body)
    if not discount.get("id"):
        raise polar_service.PolarError("The payment provider did not create the discount.")
    affiliate.polar_discount_id = discount["id"]
    affiliate.polar_discount_key = key
    return discount["id"]
