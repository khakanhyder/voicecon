"""
The subscription reconciler — persists lifecycle transitions and their side
effects.

Access control does *not* depend on this running: the entitlement resolver
derives expiry from ``trial_end`` on every request, so a trial stops working the
moment it ends even if this process is down. What the reconciler owns is
everything derivation cannot do — sending the "your trial ended" email, writing
the audit row, releasing pooled phone numbers, pausing scheduled workflows, and
keeping the persisted ``status`` honest so reporting and support see the truth.

Two rules shape the transitions:

* **Fail closed for trials.** A trial past its end date loses runtime.
* **Fail open for payers.** An ``active`` subscription past its period end is
  *not* expired on this process's say-so — the provider (Stripe or Polar) is
  the source of truth for paid subscriptions, and a dropped webhook must never
  lock out a paying customer. The provider is asked for its current state and
  that is applied; if it cannot be reached the row stays live and is logged.

Every pass is idempotent: running it twice in a row changes nothing the second
time.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.notification import Notification
from app.models.subscription import (
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_EXPIRED,
    STATUS_GRACE,
    STATUS_PAST_DUE,
    STATUS_TRIALING,
    SOURCE_POLAR,
    SOURCE_STRIPE,
    SOURCE_TRIAL,
    Subscription,
    SubscriptionPlan,
)
from app.models.user import Organization, OrganizationMember, User
from app.services.billing import events
from app.services.billing.entitlements import (
    EXPIRING_SOON_DAYS,
    TRIAL_GRACE_DAYS,
    invalidate_entitlements,
)

logger = logging.getLogger(__name__)

#: Notices sent during the trial, keyed by "days left at or below".
TRIAL_NOTICE_DAYS = (3, 1)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _billing_url() -> str:
    base = (settings.FRONTEND_URL or "").rstrip("/")
    return f"{base}/dashboard/settings/billing"


class ReconcileReport:
    """What one pass did. Returned so the caller can log a one-line summary."""

    def __init__(self) -> None:
        self.trials_to_grace = 0
        self.grace_to_expired = 0
        self.past_due_to_expired = 0
        self.canceled_to_expired = 0
        self.notices_sent = 0
        self.plan_changes_applied = 0
        self.stale_active = 0
        self.resynced = 0

    @property
    def changed(self) -> int:
        return (
            self.trials_to_grace
            + self.grace_to_expired
            + self.past_due_to_expired
            + self.canceled_to_expired
            + self.plan_changes_applied
            + self.resynced
        )

    def __str__(self) -> str:
        return (
            f"trial→grace={self.trials_to_grace} grace→expired={self.grace_to_expired} "
            f"past_due→expired={self.past_due_to_expired} "
            f"canceled→expired={self.canceled_to_expired} "
            f"plan_changes={self.plan_changes_applied} notices={self.notices_sent} "
            f"stale_active={self.stale_active} resynced={self.resynced}"
        )


async def reconcile_subscriptions(db: AsyncSession, *, now: Optional[datetime] = None) -> ReconcileReport:
    """Run one reconciliation pass over every subscription that needs one."""
    now = now or _utcnow()
    report = ReconcileReport()

    await _expire_trials(db, now, report)
    await _end_grace_periods(db, now, report)
    await _expire_dunning(db, now, report)
    await _expire_canceled(db, now, report)
    await _apply_scheduled_plan_changes(db, now, report)
    await _flag_stale_active(db, now, report)
    await _send_trial_notices(db, now, report)

    await db.commit()
    if report.changed or report.notices_sent:
        logger.info(f"Subscription reconcile: {report}")
    return report


# ---- Transitions ----


async def _expire_trials(db: AsyncSession, now: datetime, report: ReconcileReport) -> None:
    """``trialing`` past ``trial_end`` → ``grace``.

    Runtime continues through grace on purpose. Cutting a phone line the minute
    a trial lapses turns a Friday afternoon into a support emergency, and the
    few extra hours of usage cost far less than the churn.
    """
    result = await db.execute(
        select(Subscription).where(
            Subscription.status == STATUS_TRIALING,
            Subscription.trial_end.is_not(None),
            Subscription.trial_end <= now,
        )
    )
    for subscription in result.scalars().all():
        grace_end = (subscription.trial_end or now) + timedelta(days=TRIAL_GRACE_DAYS)
        subscription.status = STATUS_GRACE
        subscription.grace_period_end = grace_end
        await events.record_event(
            db,
            organization_id=subscription.organization_id,
            event_type=events.TRIAL_EXPIRED,
            subscription=subscription,
            from_status=STATUS_TRIALING,
            to_status=STATUS_GRACE,
            payload={"grace_period_end": grace_end.isoformat()},
        )
        invalidate_entitlements(subscription.organization_id)
        report.trials_to_grace += 1

        await _notify(
            db,
            subscription,
            subject="Your free trial has ended",
            heading="Your free trial has ended",
            intro=(
                f"Your agents keep running for {TRIAL_GRACE_DAYS} more days while "
                "you choose a plan. After that the workspace becomes read-only "
                "until you subscribe — nothing is deleted."
            ),
            bullets=[
                f"You have {TRIAL_GRACE_DAYS} days before your agents pause and your phone number is released.",
                "Your agents, workflows and call history are kept for 60 days.",
                "You can still sign in, review your data and export it at any time.",
            ],
            closing="Questions about which plan fits? Just reply to this email.",
            notification_title="Your free trial has ended",
            notification_body=f"Your agents keep running for {TRIAL_GRACE_DAYS} more days. Choose a plan to keep them on.",
        )


async def _end_grace_periods(db: AsyncSession, now: datetime, report: ReconcileReport) -> None:
    """``grace`` past ``grace_period_end`` → ``expired``, and reclaim resources."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.status == STATUS_GRACE,
            Subscription.grace_period_end.is_not(None),
            Subscription.grace_period_end <= now,
        )
    )
    for subscription in result.scalars().all():
        subscription.status = STATUS_EXPIRED
        subscription.expired_at = now
        await events.record_event(
            db,
            organization_id=subscription.organization_id,
            event_type=events.GRACE_ENDED,
            subscription=subscription,
            from_status=STATUS_GRACE,
            to_status=STATUS_EXPIRED,
        )
        invalidate_entitlements(subscription.organization_id)
        report.grace_to_expired += 1

        await _pause_scheduled_workflows(db, subscription.organization_id)
        await _release_pooled_numbers(db, subscription)

        await _notify(
            db,
            subscription,
            subject="Your workspace is now read-only",
            heading="Your agents have been paused",
            intro=(
                "Your grace period has ended, so your agents, calls and workflows "
                "are paused. Everything you built is still here — choose a plan "
                "and it all switches back on."
            ),
            bullets=[
                "You can still sign in, review your data and export it at any time.",
            ],
            notification_title="Your agents have been paused",
            notification_body="Your grace period has ended. Choose a plan to switch everything back on.",
        )


async def _expire_dunning(db: AsyncSession, now: datetime, report: ReconcileReport) -> None:
    """``past_due`` whose dunning window has closed → ``expired``.

    Only fires once ``grace_period_end`` has been set by the payment-failed
    webhook, so a ``past_due`` row we have not started counting on is left alone.
    """
    result = await db.execute(
        select(Subscription).where(
            Subscription.status == STATUS_PAST_DUE,
            Subscription.grace_period_end.is_not(None),
            Subscription.grace_period_end <= now,
        )
    )
    for subscription in result.scalars().all():
        subscription.status = STATUS_EXPIRED
        subscription.expired_at = now
        await events.record_event(
            db,
            organization_id=subscription.organization_id,
            event_type=events.PAYMENT_FAILED,
            subscription=subscription,
            from_status=STATUS_PAST_DUE,
            to_status=STATUS_EXPIRED,
            payload={"reason": "dunning_exhausted"},
        )
        invalidate_entitlements(subscription.organization_id)
        report.past_due_to_expired += 1

        await _notify(
            db,
            subscription,
            subject="Your subscription has been paused",
            heading="We couldn't process your payment",
            intro=(
                "After several attempts we weren't able to charge your card, so "
                "your subscription is paused. Update your payment details to "
                "switch everything back on."
            ),
            action_label="Update payment method",
            notification_title="Subscription paused",
            notification_body="We couldn't process your payment. Update your card to resume.",
        )


async def _expire_canceled(db: AsyncSession, now: datetime, report: ReconcileReport) -> None:
    """``canceled`` past the paid period → ``expired``.

    They keep everything they paid for until the period genuinely runs out.
    """
    result = await db.execute(
        select(Subscription).where(
            Subscription.status == STATUS_CANCELED,
            Subscription.current_period_end <= now,
            Subscription.expired_at.is_(None),
        )
    )
    for subscription in result.scalars().all():
        subscription.status = STATUS_EXPIRED
        subscription.expired_at = now
        await events.record_event(
            db,
            organization_id=subscription.organization_id,
            event_type=events.GRACE_ENDED,
            subscription=subscription,
            from_status=STATUS_CANCELED,
            to_status=STATUS_EXPIRED,
        )
        invalidate_entitlements(subscription.organization_id)
        report.canceled_to_expired += 1
        await _pause_scheduled_workflows(db, subscription.organization_id)

        if subscription.source == SOURCE_TRIAL:
            continue  # the user ended their own trial; nothing paid has run out
        await _notify(
            db,
            subscription,
            subject="Your subscription has ended",
            heading="Your subscription has ended",
            intro=(
                "Your paid period is over, so your agents, calls and workflows are "
                "paused. Everything you built is still here — subscribe again and "
                "it all switches back on."
            ),
            notification_title="Your subscription has ended",
            notification_body="Your agents are paused. Choose a plan to switch everything back on.",
        )


async def _apply_scheduled_plan_changes(
    db: AsyncSession, now: datetime, report: ReconcileReport
) -> None:
    """Apply downgrades that were deferred to the end of the paid period."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.scheduled_plan_id.is_not(None),
            Subscription.current_period_end <= now,
            Subscription.status.in_((STATUS_ACTIVE, STATUS_PAST_DUE)),
        )
    )
    for subscription in result.scalars().all():
        previous_plan_id = subscription.plan_id
        subscription.plan_id = subscription.scheduled_plan_id
        subscription.scheduled_plan_id = None
        await events.record_event(
            db,
            organization_id=subscription.organization_id,
            event_type=events.PLAN_CHANGED,
            subscription=subscription,
            from_plan_id=previous_plan_id,
            to_plan_id=subscription.plan_id,
            payload={"trigger": "scheduled_downgrade"},
        )
        invalidate_entitlements(subscription.organization_id)
        report.plan_changes_applied += 1


#: How overdue a paid subscription must be before the provider is asked about
#: it. Renewal webhooks normally land within minutes; this leaves room for
#: Stripe's hour-long invoice finalisation and a slow retry.
STALE_ACTIVE_AFTER = timedelta(hours=6)

#: Provider look-ups per pass, so a backlog never turns one sweep into
#: hundreds of API calls.
MAX_PROVIDER_RESYNCS_PER_PASS = 50


async def _flag_stale_active(
    db: AsyncSession, now: datetime, report: ReconcileReport
) -> None:
    """Re-sync paid subscriptions that look overdue from their provider.

    An ``active`` row past ``current_period_end`` almost always means a missed
    webhook, not a customer who stopped paying — so this never expires anything
    on its own say-so. It asks the provider instead and applies the answer: a
    renewal moves the period forward, a cancellation or revocation ends access.
    Without this, one lost ``subscription.deleted``/``revoked`` delivery was
    free service forever. If the provider cannot be reached the row is left
    live, as before, and logged.
    """
    result = await db.execute(
        select(Subscription).where(
            Subscription.status.in_((STATUS_ACTIVE, STATUS_PAST_DUE)),
            Subscription.source.in_((SOURCE_STRIPE, SOURCE_POLAR)),
            Subscription.current_period_end < now - STALE_ACTIVE_AFTER,
        )
    )
    stale = result.scalars().all()
    for index, subscription in enumerate(stale):
        resynced = False
        if index < MAX_PROVIDER_RESYNCS_PER_PASS:
            resynced = await _resync_from_provider(db, subscription)
        if resynced:
            invalidate_entitlements(subscription.organization_id)
            report.resynced += 1
        if subscription.current_period_end < now - STALE_ACTIVE_AFTER and subscription.status in (
            STATUS_ACTIVE,
            STATUS_PAST_DUE,
        ):
            report.stale_active += 1
            logger.warning(
                "Subscription %s (org %s, %s) is %s but its period ended at %s and "
                "the provider %s. Left live deliberately; check it in the %s dashboard.",
                subscription.id,
                subscription.organization_id,
                subscription.source,
                subscription.status,
                subscription.current_period_end,
                "agrees it is still running" if resynced else "could not be asked",
                subscription.source.capitalize(),
            )


async def _resync_from_provider(db: AsyncSession, subscription: Subscription) -> bool:
    """Apply the provider's current view of ``subscription``. ``True`` on success."""
    try:
        if subscription.source == SOURCE_STRIPE and subscription.stripe_subscription_id:
            if not settings.stripe_configured:
                return False
            import asyncio

            import stripe

            from app.services.billing.stripe_service import (
                apply_stripe_subscription,
                get_stripe_service,
            )

            await get_stripe_service()  # points the SDK at the current key
            remote = await asyncio.to_thread(
                stripe.Subscription.retrieve, subscription.stripe_subscription_id
            )
            await apply_stripe_subscription(db, subscription, remote)
            return True

        if subscription.source == SOURCE_POLAR and subscription.polar_subscription_id:
            if not settings.polar_configured:
                return False
            from app.services.billing import polar_service

            remote = await polar_service.get_polar_client().get_subscription(
                subscription.polar_subscription_id
            )
            await polar_service.sync_subscription(
                db, remote, polar_service.WebhookOutcome(), event_type="reconciler.resync"
            )
            return True
    except Exception as exc:  # noqa: BLE001 — a provider outage must not stop the sweep
        logger.warning(
            "Could not re-sync subscription %s from %s: %s",
            subscription.id,
            subscription.source,
            exc,
        )
    return False


# ---- Notices ----


async def _send_trial_notices(
    db: AsyncSession, now: datetime, report: ReconcileReport
) -> None:
    """Remind trial users before the trial ends. Each notice sends exactly once."""
    horizon = now + timedelta(days=max(TRIAL_NOTICE_DAYS))
    result = await db.execute(
        select(Subscription).where(
            Subscription.status == STATUS_TRIALING,
            Subscription.trial_end.is_not(None),
            Subscription.trial_end > now,
            Subscription.trial_end <= horizon,
        )
    )
    for subscription in result.scalars().all():
        days_left = max(
            0, int((subscription.trial_end - now).total_seconds() // 86400) + 1
        )
        # The tightest threshold that applies: with one day left that is the
        # T-1 notice, not the T-3 one already sent.
        threshold = min((d for d in TRIAL_NOTICE_DAYS if days_left <= d), default=None)
        if threshold is None:
            continue

        notice = f"trial_t_minus_{threshold}"
        if await events.has_event(
            db, subscription.id, events.NOTICE_SENT, notice=notice
        ):
            continue

        when = "tomorrow" if days_left <= 1 else f"in {days_left} days"
        await _notify(
            db,
            subscription,
            subject=f"Your free trial ends {when}",
            heading=f"Your free trial ends {when}",
            intro=(
                "Add a payment method to keep your phone number, your agents and "
                "everything you've built running without interruption."
            ),
            bullets=[
                "Nothing is deleted if the trial lapses — the account goes read-only.",
                "You can upgrade in under a minute and pick up where you left off.",
            ],
            notification_title=f"Your trial ends {when}",
            notification_body="Choose a plan to keep your agents running.",
        )
        await events.record_event(
            db,
            organization_id=subscription.organization_id,
            event_type=events.NOTICE_SENT,
            subscription=subscription,
            payload={"notice": notice, "days_left": days_left},
        )
        report.notices_sent += 1


async def _notify(
    db: AsyncSession,
    subscription: Subscription,
    *,
    subject: str,
    heading: str,
    intro: str,
    bullets: Optional[Sequence[str]] = None,
    closing: str = "",
    action_label: str = "Choose a plan",
    notification_title: str = "",
    notification_body: str = "",
) -> None:
    """Email the owners and drop an in-app notification.

    Failures are swallowed: a dead mail server must never roll back the state
    transition that triggered the notice.
    """
    try:
        owners = await _owners(db, subscription.organization_id)
        for owner in owners:
            db.add(
                Notification(
                    user_id=owner.id,
                    type="billing",
                    title=notification_title or heading,
                    body=notification_body or intro,
                    data={
                        "subscription_id": str(subscription.id),
                        "status": subscription.status,
                        "action_url": "/dashboard/settings/billing",
                    },
                )
            )

        from app.services.email.service import email_service

        for owner in owners:
            await email_service.send_billing_notice(
                to_email=owner.email,
                subject=subject,
                heading=heading,
                intro=intro,
                bullets=list(bullets or []),
                closing=closing,
                action_url=_billing_url(),
                action_label=action_label,
            )
    except Exception as exc:  # noqa: BLE001 — notices must not break reconciliation
        logger.error(
            f"Failed to send billing notice for subscription {subscription.id}: {exc}"
        )


async def _owners(db: AsyncSession, organization_id: uuid.UUID) -> list[User]:
    """The people who can actually act on a billing notice."""
    result = await db.execute(
        select(User)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.role.in_(("owner", "admin")),
            User.is_active.is_(True),
        )
    )
    return list(result.scalars().unique().all())


# ---- Side effects at expiry ----


async def _pause_scheduled_workflows(
    db: AsyncSession, organization_id: uuid.UUID
) -> None:
    """Stop scheduled workflows from firing for an expired organization.

    The scheduler also checks entitlements before each run, so this is belt and
    braces — but it means the UI shows them as paused rather than silently
    failing every few minutes.
    """
    try:
        from app.models.integration import Workflow

        result = await db.execute(
            select(Workflow).where(
                Workflow.organization_id == organization_id,
                Workflow.is_active.is_(True),
            )
        )
        for workflow in result.scalars().all():
            trigger = (workflow.trigger_type or "").lower()
            if trigger in ("schedule", "scheduled", "cron"):
                workflow.is_active = False
                logger.info(
                    f"Paused scheduled workflow {workflow.id} — subscription expired"
                )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Could not pause workflows for org {organization_id}: {exc}")


async def _release_pooled_numbers(db: AsyncSession, subscription: Subscription) -> None:
    """Give back phone numbers we provided, once grace has run out.

    Only numbers bought on Voicecon's own carrier account are released — a
    number on the customer's own Twilio is theirs and is never touched.
    """
    try:
        from app.models.call import PhoneNumber

        result = await db.execute(
            select(PhoneNumber).where(
                PhoneNumber.organization_id == subscription.organization_id
            )
        )
        numbers = result.scalars().all()
        if not numbers:
            return

        # No carrier integration of their own → the number sits on Voicecon's
        # shared account and is ours to reclaim.
        pooled = [
            n
            for n in numbers
            if n.integration_connection_id is None and n.status == "active"
        ]
        if pooled:
            logger.info(
                "Subscription %s expired: %d platform-provided number(s) are "
                "eligible for release for org %s",
                subscription.id,
                len(pooled),
                subscription.organization_id,
            )
            # Deliberately not deleting the carrier resource here. Releasing a
            # number is irreversible — the customer cannot get that number back
            # if they upgrade an hour later — so it stays flagged for an
            # operator to action rather than being destroyed by a background
            # job. The number is unusable meanwhile: runtime is already off.
            for number in pooled:
                number.status = "suspended"
    except Exception as exc:  # noqa: BLE001
        logger.error(
            f"Could not evaluate pooled numbers for subscription {subscription.id}: {exc}"
        )


# ---- Period counter reset ----


async def reset_expired_period_counters(
    db: AsyncSession, *, now: Optional[datetime] = None
) -> int:
    """Roll usage counters for trials and manual subscriptions.

    Stripe- and Polar-backed subscriptions reset on the provider's renewal
    webhook (``invoice.paid`` / ``order.paid``), which is the only moment that
    genuinely starts a new billing period. This covers the rows no provider
    ever sends a renewal for.
    """
    now = now or _utcnow()
    result = await db.execute(
        select(Subscription).where(
            Subscription.source.notin_(("stripe", "polar")),
            Subscription.status.in_((STATUS_ACTIVE,)),
            Subscription.current_period_end <= now,
        )
    )
    from app.services.billing.stripe_service import apply_scheduled_plan_on_rollover

    rolled = 0
    for subscription in result.scalars().all():
        span = subscription.current_period_end - subscription.current_period_start
        # A downgrade queued for this period end takes effect with the new
        # period, whichever of this job and the reconciler gets there first.
        apply_scheduled_plan_on_rollover(db, subscription, subscription.current_period_end)
        subscription.current_period_start = subscription.current_period_end
        subscription.current_period_end = subscription.current_period_end + (
            span or timedelta(days=30)
        )
        subscription.current_period_minutes = 0
        subscription.current_period_calls = 0
        subscription.current_period_sms = 0
        subscription.current_period_emails = 0
        invalidate_entitlements(subscription.organization_id)
        rolled += 1

    if rolled:
        await db.commit()
        logger.info(f"Rolled usage counters for {rolled} subscription(s)")
    return rolled
