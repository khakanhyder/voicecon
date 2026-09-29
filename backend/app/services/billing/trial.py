"""Granting a free trial — the no-card-required path onto the platform.

Shared by the billing endpoint (a user explicitly clicking "Start trial") and
by code paths that grant one on someone's behalf: accepting a team invite
creates the invitee's *own* workspace (the personal one every account gets)
but sends them straight to accepting the invite rather than through
onboarding, so that workspace never passes through the only place a trial
otherwise gets started. "Create new workspace" has the same gap. Both call
:func:`grant_trial` so a freshly created workspace is never left in the
subscription-less state that the entitlement resolver reads as "expired".
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.subscription import (
    SOURCE_TRIAL,
    STATUS_TRIALING,
    Subscription,
    SubscriptionPlan,
    TrialGrant,
)
from app.services.billing import catalog, events
from app.services.billing.conversion import mark_onboarding_done
from app.services.billing.entitlements import get_entitlement_service

logger = logging.getLogger(__name__)

#: Refuse a trial when another account at the same email domain has already had
#: one. Off by default, and deliberately so: a second team signing up at a large
#: company is a real and common case, and refusing them turns an anti-abuse
#: measure into lost revenue. Domain collisions are logged instead, so the
#: decision to tighten this can be made from evidence rather than a guess.
BLOCK_REPEAT_TRIALS_BY_DOMAIN = False

#: Domains where a shared suffix implies nothing about a shared company.
CONSUMER_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "icloud.com",
        "me.com",
        "proton.me",
        "protonmail.com",
        "aol.com",
        "gmx.com",
        "mail.com",
        "yandex.com",
        "zoho.com",
    }
)


class TrialUnavailable(Exception):
    """Why :func:`grant_trial` declined — never a bug, just a "not this time".

    Callers that granted the trial on the user's behalf (invite acceptance,
    workspace creation) catch this and skip silently; the one caller that
    granted it because the user explicitly asked (``POST /billing/trial``)
    catches it and turns it into the matching HTTP response.
    """

    def __init__(self, reason: str, detail: str):
        self.reason = reason
        self.detail = detail
        super().__init__(detail)


def email_domain(email: str) -> str:
    return (email or "").split("@")[-1].strip().lower()


async def existing_live_subscription(
    db: AsyncSession, org_id: uuid.UUID
) -> Optional[Subscription]:
    return await get_entitlement_service().live_subscription(db, org_id)


async def trial_already_used(
    db: AsyncSession, user: User, organization_id: uuid.UUID
) -> Optional[str]:
    """Why this caller may not start a free trial, or ``None`` if they may.

    A free trial is once, and "once" has to be pinned to more than one thing —
    each arm below closes a different way of asking for a second one:

    * **This workspace has had one.** The trial belongs to the organization, not
      to whoever clicked the button. Without this arm a second owner or admin
      simply starts the trial again the day the first one's expires, forever.
    * **This person has had one**, in any workspace. Otherwise deleting the
      workspace and creating a new one resets the clock.
    * **This email domain has had one** — advisory only, because it cannot tell
      "the same person came back with a new address" apart from "a different
      team at the same company signed up". See
      :data:`BLOCK_REPEAT_TRIALS_BY_DOMAIN`.

    Returns a short machine-ish reason for the log; the caller turns it into a
    409. Cheap: every arm is a single indexed lookup with ``LIMIT 1``.
    """
    result = await db.execute(
        select(TrialGrant.id)
        .where(TrialGrant.organization_id == organization_id)
        .limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return "organization_already_trialed"

    # Belt and braces for rows the grant ledger never saw: a trial created
    # before ``trial_grants`` existed and missed by the backfill, or one whose
    # grant insert was rolled back. The subscription row itself is then the only
    # evidence the workspace has already had its trial, and it is enough.
    result = await db.execute(
        select(Subscription.id)
        .where(
            Subscription.organization_id == organization_id,
            Subscription.source == SOURCE_TRIAL,
        )
        .limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return "organization_has_prior_trial_subscription"

    result = await db.execute(
        select(TrialGrant.id).where(TrialGrant.user_id == user.id).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return "user_already_trialed"

    domain = email_domain(user.email)
    if not domain or domain in CONSUMER_EMAIL_DOMAINS:
        # A shared consumer domain says nothing about who the company is, so
        # matching on it would refuse every second gmail.com signup.
        return None

    result = await db.execute(
        select(TrialGrant).where(TrialGrant.email_domain == domain).limit(1)
    )
    domain_grant = result.scalar_one_or_none()
    if domain_grant is None:
        return None

    logger.info(
        "Trial domain collision: %s shares a domain with an earlier trial "
        "(grant %s, org %s). %s",
        user.email,
        domain_grant.id,
        domain_grant.organization_id,
        "Refusing." if BLOCK_REPEAT_TRIALS_BY_DOMAIN else "Allowing — see BLOCK_REPEAT_TRIALS_BY_DOMAIN.",
    )
    return "domain_already_trialed" if BLOCK_REPEAT_TRIALS_BY_DOMAIN else None


async def get_trial_plan(
    db: AsyncSession, plan_id: Optional[uuid.UUID]
) -> Optional[SubscriptionPlan]:
    """The plan a free trial is attached to, or ``None`` if the catalog is empty.

    Defaults to the *highest* trialable tier, not the cheapest plan. Trials
    convert on feature discovery: someone who never sees lead scoring or
    campaigns has no reason to choose the expensive plan, so trialling the cheap
    one caps our own conversion. Consumption is what actually costs us money,
    and ``catalog.TRIAL_ENTITLEMENTS`` caps that hard regardless of plan.
    """
    if plan_id is not None:
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        # A plan the operator marked non-trialable (or retired) is not something
        # a client gets to trial by naming its id. Fall through to the default
        # rather than erroring — the customer asked for a trial, and there is a
        # perfectly good plan to give them.
        if plan and plan.is_active and plan.is_trialable:
            return plan
        if plan is not None:
            logger.info(
                "Ignoring requested trial plan %s (active=%s, trialable=%s)",
                plan_id,
                plan.is_active,
                plan.is_trialable,
            )

    result = await db.execute(
        select(SubscriptionPlan)
        .where(
            SubscriptionPlan.is_active == True,  # noqa: E712 — SQL expression
            SubscriptionPlan.is_trialable == True,  # noqa: E712
        )
        .order_by(SubscriptionPlan.tier.desc(), SubscriptionPlan.price_monthly.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if plan:
        return plan

    # No plan is flagged trialable (a database seeded before that column
    # existed). Fall back to the highest tier rather than refusing the trial.
    result = await db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.is_active == True)  # noqa: E712
        .order_by(SubscriptionPlan.tier.desc(), SubscriptionPlan.price_monthly.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def grant_trial(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user: User,
    plan_id: Optional[uuid.UUID] = None,
    billing_period: str = "monthly",
    signup_ip: Optional[str] = None,
) -> Subscription:
    """Start a card-free trial for ``organization_id``, or raise :class:`TrialUnavailable`.

    Added to ``db`` and flushed, but **not committed** — same contract as
    :func:`app.services.billing.events.record_event`: the caller owns the
    transaction, so the trial and whatever else it's bundled with (a new
    membership, a new workspace) land together or not at all. The caller is
    also responsible for calling
    ``invalidate_entitlements(organization_id)`` once that commit succeeds.
    """
    if await existing_live_subscription(db, organization_id):
        raise TrialUnavailable(
            "already_subscribed",
            "This workspace already has an active subscription or trial",
        )

    reason = await trial_already_used(db, user, organization_id)
    if reason is not None:
        logger.info(
            "Declined a trial grant for user %s in org %s (%s)",
            user.id,
            organization_id,
            reason,
        )
        raise TrialUnavailable(
            reason,
            "A free trial has already been used for this account. "
            "Choose a plan to continue.",
        )

    plan = await get_trial_plan(db, plan_id)
    if plan is None:
        raise TrialUnavailable("no_plan_available", "No subscription plans are available")

    trial_days = plan.trial_days or catalog.DEFAULT_TRIAL_DAYS
    now = datetime.utcnow()
    trial_end = now + timedelta(days=trial_days)

    subscription = Subscription(
        organization_id=organization_id,
        plan_id=plan.id,
        stripe_subscription_id=None,
        stripe_customer_id=None,
        status=STATUS_TRIALING,
        source=SOURCE_TRIAL,
        billing_period=billing_period,
        current_period_start=now,
        current_period_end=trial_end,
        trial_start=now,
        trial_end=trial_end,
        stripe_metadata={"source": "free_trial"},
    )
    db.add(subscription)
    await db.flush()

    db.add(
        TrialGrant(
            organization_id=organization_id,
            user_id=user.id,
            email_domain=email_domain(user.email),
            signup_ip=signup_ip,
            granted_at=now,
            expires_at=trial_end,
        )
    )
    await events.record_event(
        db,
        organization_id=organization_id,
        event_type=events.TRIAL_STARTED,
        subscription=subscription,
        to_status=STATUS_TRIALING,
        to_plan_id=plan.id,
        actor_type=events.ACTOR_USER,
        actor_id=user.id,
        payload={"trial_days": trial_days, "trial_end": trial_end.isoformat()},
    )

    await mark_onboarding_done(db, organization_id)

    return subscription
