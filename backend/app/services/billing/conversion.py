"""Turning a trial (or a lapsed subscription) into a paid one.

Shared by the Stripe checkout endpoint and the Polar webhook, so a trial
converts identically whichever provider took the money.
"""
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import CompanyProfile
from app.models.subscription import (
    SOURCE_POLAR,
    SOURCE_STRIPE,
    SOURCE_TRIAL,
    Subscription,
    SubscriptionPlan,
)


async def mark_onboarding_done(db: AsyncSession, organization_id: uuid.UUID) -> None:
    """Flag the organization's onboarding as completed once a plan/trial is active."""
    result = await db.execute(
        select(CompanyProfile).where(
            CompanyProfile.organization_id == organization_id
        )
    )
    profile = result.scalar_one_or_none()
    if profile:
        profile.onboarding_completed = True
        profile.onboarding_step = "done"
        await db.flush()



def apply_paid_conversion(
    subscription: Subscription,
    plan: SubscriptionPlan,
    *,
    stripe_subscription_id: Optional[str] = None,
    stripe_customer_id: Optional[str] = None,
    stripe_status: str,
    billing_period: str,
    period_start: datetime,
    period_end: datetime,
    now: datetime,
    source: str = SOURCE_STRIPE,
    polar_subscription_id: Optional[str] = None,
    polar_customer_id: Optional[str] = None,
) -> bool:
    """Turn a trial — or a lapsed subscription — into the paid plan, in place.

    Returns ``True`` when what was converted was a trial.

    ``source`` says which provider now bills the row (``stripe`` or ``polar``);
    the other provider's ids are cleared so no code path can act on a stale one.

    The trial is *ended*, not merely overwritten. ``status`` and ``source`` both
    leave their trial values, and ``trial_end`` is pulled back to ``now`` so no
    code path anywhere can still see a trial running into the future. That last
    part is what makes the switchover total: the entitlement resolver picks the
    trial's restrictive limits purely on ``status == trialing``, so a paying
    customer with a future-dated ``trial_end`` sitting in the row is one status
    write away from being handed 1-agent trial limits again. Clearing it means
    there is nothing left to go back to.

    What the trial *would* have run to is kept in ``stripe_metadata`` — the
    customer gave up those days by paying early, and conversion reporting should
    be able to see that rather than having it silently overwritten.
    """
    converting_trial = subscription.source == SOURCE_TRIAL

    subscription.plan_id = plan.id
    if source == SOURCE_POLAR:
        subscription.polar_subscription_id = polar_subscription_id
        subscription.polar_customer_id = polar_customer_id
        subscription.stripe_subscription_id = None
        subscription.stripe_customer_id = None
    else:
        subscription.stripe_subscription_id = stripe_subscription_id
        subscription.stripe_customer_id = stripe_customer_id
        subscription.polar_subscription_id = None
        subscription.polar_customer_id = None
    subscription.status = stripe_status
    subscription.source = source
    subscription.billing_period = billing_period
    subscription.current_period_start = period_start
    subscription.current_period_end = period_end
    subscription.cancel_at_period_end = False
    subscription.canceled_at = None
    subscription.expired_at = None
    subscription.grace_period_end = None
    #: Any downgrade the old subscription had queued is void — the customer has
    #: just chosen a plan explicitly, and that choice wins.
    subscription.scheduled_plan_id = None

    if converting_trial:
        if subscription.trial_converted_at is None:
            subscription.trial_converted_at = now
        scheduled_end = subscription.trial_end
        if scheduled_end is not None and scheduled_end > now:
            metadata = dict(subscription.stripe_metadata or {})
            metadata["trial_end_forfeited"] = scheduled_end.isoformat()
            subscription.stripe_metadata = metadata
        subscription.trial_end = now

    # A converted trial starts its paid allowance clean rather than inheriting
    # the trial's consumption.
    subscription.current_period_minutes = 0
    subscription.current_period_calls = 0
    subscription.current_period_sms = 0
    subscription.current_period_emails = 0

    return converting_trial
