"""Tie a new customer's organization to the affiliate who brought them.

One referral per organization, and the first one wins. Only new customers can
be attributed: an organization that has ever been billed (Stripe, Polar or a
staff comp) is an existing customer, and a code found later changes nothing.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate import (
    AFFILIATE_EARNING_STATUSES,
    Affiliate,
    AffiliateClick,
    AffiliateReferral,
)
from app.models.subscription import SOURCE_MANUAL, SOURCE_POLAR, SOURCE_STRIPE, Subscription
from app.services.affiliates.program import find_by_code, get_program

logger = logging.getLogger(__name__)

SOURCE_LINK = "link"
SOURCE_COUPON = "coupon"


async def usable_affiliate(db: AsyncSession, code: Optional[str]) -> Optional[Affiliate]:
    """The affiliate behind ``code`` if the program is on and they may earn."""
    affiliate = await find_by_code(db, code)
    if affiliate is None or affiliate.status not in AFFILIATE_EARNING_STATUSES:
        return None
    program = await get_program(db)
    if not program.enabled:
        return None
    return affiliate


async def record_click(
    db: AsyncSession, code: str, *, landing_path: Optional[str], referrer: Optional[str]
) -> Optional[Affiliate]:
    affiliate = await usable_affiliate(db, code)
    if affiliate is None:
        return None
    db.add(
        AffiliateClick(
            affiliate_id=affiliate.id,
            landing_path=(landing_path or "")[:500] or None,
            referrer=(referrer or "")[:500] or None,
        )
    )
    return affiliate


async def referral_for(db: AsyncSession, organization_id: uuid.UUID) -> Optional[AffiliateReferral]:
    return await db.scalar(
        select(AffiliateReferral).where(AffiliateReferral.organization_id == organization_id)
    )


async def is_existing_customer(db: AsyncSession, organization_id: uuid.UUID) -> bool:
    """Has this organization ever been billed? Trials do not count."""
    found = await db.scalar(
        select(Subscription.id)
        .where(
            Subscription.organization_id == organization_id,
            Subscription.source.in_((SOURCE_STRIPE, SOURCE_POLAR, SOURCE_MANUAL)),
        )
        .limit(1)
    )
    return found is not None


async def attribute(
    db: AsyncSession,
    *,
    affiliate: Affiliate,
    organization_id: uuid.UUID,
    user_id: Optional[uuid.UUID],
    source: str,
) -> Optional[AffiliateReferral]:
    """Record the referral unless the organization already has one.

    Refuses self-referral (the affiliate's own login) and existing customers.
    Runs in a savepoint so a lost race on the unique organization id leaves the
    caller's transaction intact.
    """
    if user_id is not None and user_id == affiliate.user_id:
        return None
    existing = await referral_for(db, organization_id)
    if existing is not None:
        return existing
    if await is_existing_customer(db, organization_id):
        return None

    referral = AffiliateReferral(
        affiliate_id=affiliate.id,
        organization_id=organization_id,
        user_id=user_id,
        source=source,
    )
    try:
        async with db.begin_nested():
            db.add(referral)
    except IntegrityError:
        return await referral_for(db, organization_id)
    logger.info("Organization %s referred by affiliate %s via %s", organization_id, affiliate.referral_code, source)
    return referral


async def attribute_signup(
    db: AsyncSession, *, code: Optional[str], organization_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Called when a new account and its workspace are created. Never raises."""
    if not code:
        return
    try:
        affiliate = await usable_affiliate(db, code)
        if affiliate is not None:
            await attribute(
                db,
                affiliate=affiliate,
                organization_id=organization_id,
                user_id=user_id,
                source=SOURCE_LINK,
            )
    except Exception as exc:  # noqa: BLE001 — a referral must never block a sign-up
        logger.error("Could not attribute sign-up to referral code %r: %s", code, exc, exc_info=True)
