"""Shared clean-up for a deleted account.

Used by self-service deletion (``DELETE /users/me``) and by the admin console
(``DELETE /admin/users/{id}``), so both stop billing the same way.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import LIVE_STATUSES, STATUS_CANCELED, Subscription
from app.models.user import Organization, User
from app.services.billing import get_stripe_service

logger = logging.getLogger(__name__)


async def deactivate_owned_workspaces(db: AsyncSession, user: User, now: datetime) -> list[Organization]:
    """Deactivate every workspace ``user`` owns and cancel its live subscriptions.

    Workspaces are soft-deactivated, not dropped, so calls, recordings and
    invoices stay attributable. Nothing is committed here.
    """
    organizations = (
        await db.execute(select(Organization).where(Organization.owner_id == user.id))
    ).scalars().all()

    for org in organizations:
        org.is_active = False
        org.updated_at = now

        subscriptions = (
            await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.organization_id == org.id,
                        Subscription.status.in_(LIVE_STATUSES),
                    )
                )
            )
        ).scalars().all()
        for subscription in subscriptions:
            trial_without_stripe = not (
                subscription.stripe_subscription_id or subscription.polar_subscription_id
            )
            if trial_without_stripe:
                subscription.status = STATUS_CANCELED
                subscription.canceled_at = now
                subscription.ended_at = now
                subscription.current_period_end = min(subscription.current_period_end, now)
            elif subscription.polar_subscription_id:
                try:
                    from app.services.billing import polar_service

                    await polar_service.cancel(subscription, immediate=True)
                    subscription.status = STATUS_CANCELED
                    subscription.canceled_at = subscription.canceled_at or now
                    subscription.ended_at = now
                    subscription.current_period_end = min(subscription.current_period_end, now)
                    subscription.cancel_at_period_end = False
                except Exception as e:
                    logger.error("Failed to revoke Polar subscription %s for org %s: %s", subscription.id, org.id, e)
            else:
                try:
                    stripe_service = await get_stripe_service()
                    await stripe_service.cancel_subscription(
                        db=db, subscription_id=subscription.id, immediate=True
                    )
                    await db.refresh(subscription)
                    subscription.canceled_at = subscription.canceled_at or now
                    subscription.cancel_at_period_end = False
                except Exception as e:
                    logger.error("Failed to cancel Stripe subscription %s for org %s: %s", subscription.id, org.id, e)

    return list(organizations)
