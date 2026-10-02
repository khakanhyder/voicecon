"""
Moving a workspace onto the prepaid (Pay As You Go) plan, and what that plan
charges for besides call minutes.

A prepaid workspace still has a :class:`Subscription` row — it occupies the
organization's one live-subscription slot like any other plan, which is what
keeps entitlements, plan cards and the admin console working unchanged. What
differs is its ``source``: ``wallet``. No payment provider holds anything for
it, it never renews and it never lapses on its own; its usage period simply
rolls every 30 days (``reconciler.reset_expired_period_counters``) so "minutes
this month" has a month to refer to.

Three ways in:

* **A first top-up** from a trial, a lapsed account or a new workspace — the
  existing subscription row is converted in place, exactly as a card checkout
  converts a trial (:func:`activate`).
* **From a paid subscription**, at the end of the period already paid for:
  the provider subscription is cancelled at period end and the plan is queued
  in ``scheduled_plan_id``; when the provider reports the subscription over,
  the row becomes a wallet subscription (:func:`convert_if_scheduled`).
* **Staff** granting the plan from the admin console. That is an ordinary
  manual grant: what makes a plan prepaid is its entitlement document, not the
  subscription's ``source``, so a granted workspace is metered from its wallet
  like any other.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import (
    PROVIDER_SOURCES,
    SOURCE_POLAR,
    SOURCE_WALLET,
    STATUS_ACTIVE,
    STATUS_PAST_DUE,
    Subscription,
    SubscriptionPlan,
    TrialGrant,
)
from app.models.wallet import TXN_NUMBER_FEE
from app.services.billing import events
from app.services.billing import wallet as wallet_service
from app.services.billing.conversion import apply_paid_conversion, mark_onboarding_done

logger = logging.getLogger(__name__)

#: A wallet subscription has no billing cycle; this is only the span its usage
#: counters cover before they roll.
USAGE_PERIOD = timedelta(days=30)

#: ``PhoneNumber.provider_metadata`` key recording how far a Voicecon number's
#: rent has been paid from the wallet: ``{"paid_through": "<iso datetime>"}``.
NUMBER_FEE_KEY = "wallet_fee"
#: How long one payment of the number fee covers.
NUMBER_FEE_PERIOD = timedelta(days=30)


def is_provider_billed(subscription: Optional[Subscription]) -> bool:
    """Is a payment provider charging for this subscription right now?"""
    if subscription is None or subscription.source not in PROVIDER_SOURCES:
        return False
    if subscription.status not in (STATUS_ACTIVE, STATUS_PAST_DUE):
        return False
    if subscription.source == SOURCE_POLAR:
        return bool(subscription.polar_subscription_id)
    return bool(subscription.stripe_subscription_id)


async def current_subscription(db: AsyncSession, organization_id: uuid.UUID) -> Optional[Subscription]:
    """The live subscription, else the most recent one of any status."""
    from app.services.billing.entitlements import get_entitlement_service

    live = await get_entitlement_service().live_subscription(db, organization_id)
    if live is not None:
        return live
    result = await db.execute(
        select(Subscription)
        .where(Subscription.organization_id == organization_id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _convert(subscription: Subscription, plan: SubscriptionPlan, now: datetime) -> bool:
    """Turn ``subscription`` into a wallet subscription on ``plan``, in place.

    Returns ``True`` when what was converted was a free trial.
    """
    return apply_paid_conversion(
        subscription,
        plan,
        stripe_status=STATUS_ACTIVE,
        billing_period="monthly",
        period_start=now,
        period_end=now + USAGE_PERIOD,
        now=now,
        source=SOURCE_WALLET,
    )


async def activate(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    plan: Optional[SubscriptionPlan] = None,
    actor_type: str = events.ACTOR_SYSTEM,
    actor_id: Optional[uuid.UUID] = None,
    event_key: Optional[str] = None,
) -> Optional[Subscription]:
    """Put the organization on the prepaid plan now. Caller commits.

    Does nothing — returns ``None`` — when a provider is billing the workspace
    for a subscription: that plan was paid for and runs to the end of its
    period (see :func:`convert_if_scheduled`). Calling it for a workspace
    already on the plan returns that subscription unchanged, so a payment
    confirmed twice activates once.
    """
    plan = plan or await wallet_service.prepaid_plan(db)
    if plan is None or not wallet_service.plan_is_prepaid(plan):
        return None

    existing = await current_subscription(db, organization_id)
    if is_provider_billed(existing):
        return None
    if (
        existing is not None
        and existing.source == SOURCE_WALLET
        and existing.status == STATUS_ACTIVE
        and existing.plan_id == plan.id
    ):
        return existing

    now = datetime.utcnow()
    if existing is not None:
        previous_status = existing.status
        previous_plan = existing.plan_id
        converting_trial = _convert(existing, plan, now)
        subscription = existing
        await events.record_event(
            db,
            organization_id=organization_id,
            event_type=events.TRIAL_CONVERTED if converting_trial else events.ACTIVATED,
            subscription=subscription,
            from_status=previous_status,
            to_status=subscription.status,
            from_plan_id=previous_plan,
            to_plan_id=plan.id,
            actor_type=actor_type,
            actor_id=actor_id,
            stripe_event_id=event_key,
            payload={"billing": "prepaid"},
        )
        if converting_trial:
            grants = await db.execute(
                select(TrialGrant).where(TrialGrant.organization_id == organization_id)
            )
            for grant in grants.scalars().all():
                grant.converted = True
    else:
        subscription = Subscription(
            organization_id=organization_id,
            plan_id=plan.id,
            status=STATUS_ACTIVE,
            source=SOURCE_WALLET,
            billing_period="monthly",
            current_period_start=now,
            current_period_end=now + USAGE_PERIOD,
        )
        db.add(subscription)
        await db.flush()
        await events.record_event(
            db,
            organization_id=organization_id,
            event_type=events.ACTIVATED,
            subscription=subscription,
            to_status=subscription.status,
            to_plan_id=plan.id,
            actor_type=actor_type,
            actor_id=actor_id,
            stripe_event_id=event_key,
            payload={"billing": "prepaid"},
        )

    await mark_onboarding_done(db, organization_id)
    await db.flush()
    logger.info(f"Org {organization_id} is now on prepaid plan {plan.slug}")
    return subscription


async def scheduled_prepaid_plan(
    db: AsyncSession, subscription: Optional[Subscription]
) -> Optional[SubscriptionPlan]:
    """The prepaid plan queued on this subscription, if that is what is queued."""
    if subscription is None or subscription.scheduled_plan_id is None:
        return None
    plan = await db.get(SubscriptionPlan, subscription.scheduled_plan_id)
    return plan if wallet_service.plan_is_prepaid(plan) else None


async def convert_if_scheduled(
    db: AsyncSession,
    subscription: Subscription,
    *,
    actor_type: str = events.ACTOR_SYSTEM,
    event_key: Optional[str] = None,
) -> bool:
    """A subscription that was due to become Pay As You Go has ended: switch it.

    Called at the moment the provider reports the paid subscription over, so
    the workspace goes straight from its paid plan to the wallet without a
    read-only gap in between. Caller commits. Returns whether it converted.
    """
    plan = await scheduled_prepaid_plan(db, subscription)
    if plan is None or not plan.is_active:
        return False

    previous_status = subscription.status
    previous_plan = subscription.plan_id
    _convert(subscription, plan, datetime.utcnow())
    subscription.ended_at = None
    await events.record_event(
        db,
        organization_id=subscription.organization_id,
        event_type=events.PLAN_CHANGED,
        subscription=subscription,
        from_status=previous_status,
        to_status=subscription.status,
        from_plan_id=previous_plan,
        to_plan_id=plan.id,
        actor_type=actor_type,
        stripe_event_id=event_key,
        payload={"trigger": "scheduled_prepaid", "billing": "prepaid"},
    )
    logger.info(
        f"Subscription {subscription.id} (org {subscription.organization_id}) "
        f"moved to prepaid plan {plan.slug} at the end of its paid period"
    )
    return True


async def announce(db: AsyncSession, organization_id: uuid.UUID) -> None:
    """Tell the owners their workspace is now on the prepaid plan, and what
    their balance is. For the scheduled switch, where nobody is at a screen to
    see it happen. Call after the conversion has committed. Never raises."""
    from app.services.billing import wallet_notices

    try:
        subscription = await current_subscription(db, organization_id)
        plan = await db.get(SubscriptionPlan, subscription.plan_id) if subscription else None
        if plan is None:
            return
        wallet = await wallet_service.get_wallet(db, organization_id)
        await wallet_notices.plan_started(
            db,
            organization_id,
            plan_name=plan.name,
            balance_cents=int(wallet.balance_cents) if wallet else 0,
            currency=(wallet.currency if wallet else None) or "usd",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Could not announce the prepaid plan to org {organization_id}: {exc}")


# ---------------------------------------------------------------------------
# Phone number rent
# ---------------------------------------------------------------------------
#
# A subscription's monthly fee covers the numbers the plan includes. Pay As You
# Go has no monthly fee, so each Voicecon number is paid for from the wallet,
# one period at a time. A number whose rent cannot be paid is not covered, and
# ``number_reclaim`` then holds it and later releases it — the same path a
# lapsed subscription takes.


def _parse(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def number_paid_through(number) -> Optional[datetime]:
    return _parse(((number.provider_metadata or {}).get(NUMBER_FEE_KEY) or {}).get("paid_through"))


def number_fee_cents(billing: Dict[str, Any]) -> int:
    return max(0, wallet_service.to_cents(billing.get("number_monthly_fee") or 0))


async def settle_number_fees(
    db: AsyncSession,
    organization_id: uuid.UUID,
    numbers: Sequence,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Charge any rent that is due on ``numbers``; say whether all are covered.

    ``numbers`` are the workspace's Voicecon numbers (the caller decides which
    those are). Returns ``True`` for a workspace that is not on a prepaid plan
    — its subscription covers its numbers.

    With no fee set, a number is covered for as long as the wallet holds any
    credit: a workspace that has spent everything is not paying for it.

    Commits after each charge, so a later failure cannot undo a rent payment
    that has already been taken.
    """
    from app.services.billing import wallet_notices
    from app.services.billing.entitlements import resolve_entitlements

    now = now or datetime.utcnow()
    ent = await resolve_entitlements(db, organization_id, fresh=True)
    if not ent.is_prepaid:
        return True
    if not numbers:
        return True

    fee = number_fee_cents(ent.billing)
    if fee <= 0:
        return await wallet_service.balance_cents(db, organization_id) > 0

    covered = True
    low_balance = wallet_service.to_cents(ent.billing.get("low_balance") or 0)
    for number in numbers:
        paid_through = number_paid_through(number)
        if paid_through is not None and paid_through > now:
            continue
        if await wallet_service.available_cents(db, organization_id) < fee:
            covered = False
            continue

        phone_number = number.phone_number
        new_paid_through = now + NUMBER_FEE_PERIOD
        movement = await wallet_service.apply(
            db,
            organization_id,
            amount_cents=-fee,
            type=TXN_NUMBER_FEE,
            # One charge per number per day at most; ``paid_through`` is what
            # normally stops a second one, this is the backstop.
            idempotency_key=f"number_fee:{number.id}:{now:%Y%m%d}",
            description=f"Phone number {phone_number}, 30 days",
            reference_type="phone_number",
            reference_id=str(number.id),
            details={
                "phone_number": phone_number,
                "period_start": now.isoformat(),
                "period_end": new_paid_through.isoformat(),
            },
            low_balance_cents=low_balance,
        )
        # JSON column: reassign, do not mutate in place.
        number.provider_metadata = {
            **(number.provider_metadata or {}),
            NUMBER_FEE_KEY: {"paid_through": new_paid_through.isoformat()},
        }
        await db.commit()
        await wallet_notices.after_movement(db, movement)
    return covered


async def numbers_covered(
    db: AsyncSession,
    organization_id: uuid.UUID,
    numbers: Sequence,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Are these Voicecon numbers paid for? Never raises: an error here must
    not hold (and eventually release) a number its owner is paying for."""
    try:
        return await settle_number_fees(db, organization_id, numbers, now=now)
    except Exception as exc:  # noqa: BLE001
        try:
            await db.rollback()
        except Exception:  # pragma: no cover - defensive
            pass
        logger.error(
            f"Could not settle phone number fees for org {organization_id}: {exc}", exc_info=True
        )
        return True


__all__ = [
    "NUMBER_FEE_KEY",
    "USAGE_PERIOD",
    "activate",
    "announce",
    "convert_if_scheduled",
    "current_subscription",
    "is_provider_billed",
    "number_fee_cents",
    "number_paid_through",
    "numbers_covered",
    "scheduled_prepaid_plan",
    "settle_number_fees",
]
