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
  *not* expired here — Stripe is the source of truth for paid subscriptions, and
  a dropped webhook must never lock out a paying customer. It is logged for
  investigation instead.

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

    @property
    def changed(self) -> int:
        return (
            self.trials_to_grace
            + self.grace_to_expired
            + self.past_due_to_expired
            + self.canceled_to_expired
            + self.plan_changes_applied
        )

    def __str__(self) -> str:
        return (
            f"trial→grace={self.trials_to_grace} grace→expired={self.grace_to_expired} "
            f"past_due→expired={self.past_due_to_expired} "
            f"canceled→expired={self.canceled_to_expired} "
            f"plan_changes={self.plan_changes_applied} notices={self.notices_sent} "
            f"stale_active={self.stale_active}"
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
                "Your agents are paused, but nothing has been deleted. Choose a "
                "plan and everything picks up exactly where you left off."
            ),
            bullets=[
                f"You have {TRIAL_GRACE_DAYS} days before your phone number is released.",
                "Your agents, workflows and call history are kept for 60 days.",
                "You can still sign in, review your data and export it at any time.",
            ],
            closing="Questions about which plan fits? Just reply to this email.",
            notification_title="Your free trial has ended",
            notification_body="Your agents are paused. Choose a plan to resume.",
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


async def _flag_stale_active(
    db: AsyncSession, now: datetime, report: ReconcileReport
) -> None:
    """Log paid subscriptions that look overdue, without touching them.

    An ``active`` row past ``current_period_end`` almost always means a missed
    ``invoice.paid`` webhook, not a customer who stopped paying. Expiring them
    here would lock out paying customers over our own delivery problem, so this
    only records that a reconciliation is needed.
    """
    result = await db.execute(
        select(Subscription).where(
            Subscription.status == STATUS_ACTIVE,
            Subscription.current_period_end < now - timedelta(hours=6),
        )
    )
    stale = result.scalars().all()
    for subscription in stale:
        logger.warning(
            "Subscription %s (org %s) is active but its period ended at %s — "
            "likely a missed Stripe webhook. Left live deliberately; re-check "
            "against Stripe.",
            subscription.id,
            subscription.organization_id,
            subscription.current_period_end,
        )
    report.stale_active = len(stale)


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
        threshold = next((d for d in TRIAL_NOTICE_DAYS if days_left <= d), None)
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

    Stripe-backed subscriptions reset on ``invoice.paid``, which is the only
    moment that genuinely starts a new billing period. This covers the rows
    Stripe never sends an invoice for.
    """
    now = now or _utcnow()
    result = await db.execute(
        select(Subscription).where(
            Subscription.source != "stripe",
            Subscription.status.in_((STATUS_ACTIVE,)),
            Subscription.current_period_end <= now,
        )
    )
    rolled = 0
    for subscription in result.scalars().all():
        span = subscription.current_period_end - subscription.current_period_start
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
