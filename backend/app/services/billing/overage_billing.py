"""
Charge subscription overage through the subscription's payment provider.

``UsageTracker.record_call_usage`` prices the minutes of a call that fall past
the plan's monthly allowance and stores them on the call's ``minutes``
``UsageRecord`` (``total_amount``). This module turns that record into a real
charge, on the invoice the customer already gets:

* **Stripe:** a pending invoice item on the customer, tied to the
  subscription, so it lands on the next renewal invoice.
* **Polar:** a usage event (``polar_service.OVERAGE_EVENT_NAME``) carrying the
  amount in cents. The subscription's product has a metered price of one cent
  per unit on the overage meter, and Polar invoices it with the renewal.

Each record is pushed at most once. The provider call is idempotent on the
record id (Stripe idempotency key, Polar event ``external_id``), so a retry
after a crash between the provider call and our commit cannot double charge.

State lives on the ``UsageRecord`` row, in columns that predate Polar:

* ``reported_to_stripe`` — the charge reached the provider (any provider).
* ``stripe_usage_record_id`` — the provider's reference (``ii_…`` or
  ``polar:<event id>``).
* ``stripe_metadata["bill_overage"]`` — set by the usage tracker on a record
  whose amount is subscription overage. Only flagged records are ever sent,
  so neither a Pay As You Go row (the wallet already took that money) nor an
  overage row written before overage billing existed is charged.
* ``stripe_metadata["overage_billing"]`` — ``{"status", "reason", "at"}``;
  status is ``billed``, ``failed`` (retried by the sweep) or ``unbillable``
  (no provider can take it; shown to platform admins, never retried).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import (
    SOURCE_POLAR,
    SOURCE_STRIPE,
    Subscription,
    UsageRecord,
)

logger = logging.getLogger(__name__)

STATUS_BILLED = "billed"
STATUS_FAILED = "failed"
STATUS_UNBILLABLE = "unbillable"

#: Records older than this are left alone by the retry sweep: their period has
#: been invoiced long ago and a late charge would surprise the customer.
RETRY_WINDOW = timedelta(days=45)
#: Failed pushes are retried this many times, then left for an admin.
MAX_ATTEMPTS = 8


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def amount_cents(record: UsageRecord) -> int:
    return int((Decimal(str(record.total_amount or 0)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def billing_state(record: UsageRecord) -> dict:
    return dict((record.stripe_metadata or {}).get("overage_billing") or {})


def _set_state(record: UsageRecord, status: str, reason: str = "", reference: Optional[str] = None) -> None:
    meta = dict(record.stripe_metadata or {})
    previous = dict(meta.get("overage_billing") or {})
    meta["overage_billing"] = {
        "status": status,
        "reason": reason,
        "at": _utcnow().isoformat(),
        "attempts": int(previous.get("attempts") or 0) + (1 if status == STATUS_FAILED else 0),
    }
    record.stripe_metadata = meta  # JSON column: reassign
    if status == STATUS_BILLED:
        record.reported_to_stripe = True
        record.stripe_usage_record_id = reference


def _description(record: UsageRecord) -> str:
    rate = Decimal(str(record.unit_price or 0)).quantize(Decimal("0.01"))
    minutes = int((record.stripe_metadata or {}).get("overage_minutes") or 0)
    return f"Call minutes over your plan's allowance: {minutes} min at ${rate}/min"


async def _push_stripe(subscription: Subscription, record: UsageRecord, cents: int) -> str:
    from app.core.config import settings

    if not settings.stripe_configured:
        raise _Unbillable("Stripe is not configured")
    if not subscription.stripe_customer_id or not subscription.stripe_subscription_id:
        raise _Unbillable("subscription has no Stripe customer")

    import stripe

    from app.services.billing.stripe_service import get_stripe_service

    await get_stripe_service()  # sets the module-level api key
    item = await asyncio.to_thread(
        stripe.InvoiceItem.create,
        customer=subscription.stripe_customer_id,
        subscription=subscription.stripe_subscription_id,
        amount=cents,
        currency="usd",
        description=_description(record),
        metadata={
            "voicecon_usage_record": str(record.id),
            "voicecon_call": str(record.resource_id or ""),
            "organization_id": str(record.organization_id),
        },
        idempotency_key=f"overage:{record.id}",
    )
    return item.id


async def _push_polar(subscription: Subscription, record: UsageRecord, cents: int) -> str:
    from app.core.config import settings
    from app.services.billing import polar_service

    if not settings.polar_configured:
        raise _Unbillable("Polar is not configured")
    if not subscription.polar_subscription_id:
        raise _Unbillable("subscription has no Polar subscription")

    meter_id = await polar_service.overage_meter_id()
    client = polar_service.get_polar_client()
    polar_sub = await client.get_subscription(subscription.polar_subscription_id)
    if not polar_service.subscription_bills_overage(polar_sub, meter_id):
        # Started before the product had the overage price. Polar would store
        # the event and never invoice it, so say so instead of pretending.
        raise _Unbillable(
            "the Polar subscription has no overage price; it was bought before "
            "overage billing was set up (press Sync to Polar on the plan, then "
            "move the customer to the current price in Polar)"
        )

    event_id = f"overage:{record.id}"
    event = {
        "name": polar_service.OVERAGE_EVENT_NAME,
        "external_id": event_id,
        "metadata": {
            "amount_cents": cents,
            "minutes": int((record.stripe_metadata or {}).get("overage_minutes") or 0),
            "call_id": str(record.resource_id or ""),
        },
    }
    if subscription.polar_customer_id:
        event["customer_id"] = subscription.polar_customer_id
    else:
        event["external_customer_id"] = str(subscription.organization_id)
    await client.ingest_events([event])
    return f"polar:{event_id}"


class _Unbillable(Exception):
    """No provider can take this charge; retrying will not help."""


async def push_record(db: AsyncSession, record: UsageRecord) -> str:
    """Send one overage record to its provider and stage the outcome on the row.

    The caller commits. Returns the resulting status.
    """
    if record.reported_to_stripe:
        return STATUS_BILLED
    if not (record.stripe_metadata or {}).get("bill_overage"):
        return STATUS_UNBILLABLE
    cents = amount_cents(record)
    if cents <= 0:
        return STATUS_BILLED

    subscription = await db.get(Subscription, record.subscription_id)
    try:
        if subscription is None:
            raise _Unbillable("subscription not found")
        if subscription.source == SOURCE_STRIPE:
            reference = await _push_stripe(subscription, record, cents)
        elif subscription.source == SOURCE_POLAR:
            reference = await _push_polar(subscription, record, cents)
        else:
            # A staff-made (manual) subscription is invoiced by hand.
            raise _Unbillable(f"subscription is billed outside Voicecon ({subscription.source})")
    except _Unbillable as exc:
        logger.warning("Overage %s (%s cents) cannot be billed: %s", record.id, cents, exc)
        _set_state(record, STATUS_UNBILLABLE, str(exc))
        return STATUS_UNBILLABLE
    except Exception as exc:
        logger.warning("Overage %s (%s cents) push failed, will retry: %s", record.id, cents, exc)
        _set_state(record, STATUS_FAILED, type(exc).__name__)
        return STATUS_FAILED

    _set_state(record, STATUS_BILLED, reference=reference)
    logger.info("Overage %s billed: %s cents -> %s", record.id, cents, reference)
    return STATUS_BILLED


async def push_for_call(db: AsyncSession, call_id: uuid.UUID) -> Optional[str]:
    """Bill the overage of one call, right after its usage was committed."""
    record = (
        await db.execute(
            select(UsageRecord).where(
                UsageRecord.resource_id == call_id,
                UsageRecord.usage_type == "minutes",
            )
        )
    ).scalars().first()
    if record is None or not (record.stripe_metadata or {}).get("bill_overage"):
        return None
    status = await push_record(db, record)
    await db.commit()
    return status


async def retry_pending(db: AsyncSession, *, now: Optional[datetime] = None, limit: int = 200) -> int:
    """Push every overage record that has not reached its provider yet.

    Picks up records whose immediate push failed (provider down) and any that
    were never tried (process died between commit and push). Returns how many
    were billed.
    """
    now = now or _utcnow()
    rows = (
        await db.execute(
            select(UsageRecord)
            .join(Subscription, Subscription.id == UsageRecord.subscription_id)
            .where(
                and_(
                    Subscription.source.in_((SOURCE_STRIPE, SOURCE_POLAR)),
                    UsageRecord.usage_type == "minutes",
                    UsageRecord.total_amount > 0,
                    UsageRecord.reported_to_stripe.is_not(True),
                    UsageRecord.created_at >= now - RETRY_WINDOW,
                    # Leave the immediate push a moment to finish first.
                    UsageRecord.created_at <= now - timedelta(minutes=2),
                )
            )
            .order_by(UsageRecord.created_at)
            .limit(limit)
        )
    ).scalars().all()

    billed = 0
    for record in rows:
        if not (record.stripe_metadata or {}).get("bill_overage"):
            continue
        state = billing_state(record)
        if state.get("status") == STATUS_UNBILLABLE:
            continue
        if int(state.get("attempts") or 0) >= MAX_ATTEMPTS:
            continue
        if await push_record(db, record) == STATUS_BILLED:
            billed += 1
        await db.commit()
    return billed
