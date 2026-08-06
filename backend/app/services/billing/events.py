"""
The subscription event ledger.

Every state change writes a row. Current state is a materialised convenience;
this log is what answers "why is this account in this state?" — the question
support asks most often — and it doubles as the send-once guard for lifecycle
emails, so a retried job cannot email a customer twice.

Rows are only ever inserted. Nothing here updates or deletes.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription, SubscriptionEvent

logger = logging.getLogger(__name__)

# ---- Event types ----
TRIAL_STARTED = "trial_started"
TRIAL_EXPIRING = "trial_expiring"
TRIAL_EXPIRED = "trial_expired"
TRIAL_CONVERTED = "trial_converted"
GRACE_STARTED = "grace_started"
GRACE_ENDED = "grace_ended"
ACTIVATED = "activated"
RENEWED = "renewed"
PAYMENT_FAILED = "payment_failed"
PAST_DUE = "past_due"
CANCELED = "canceled"
REACTIVATED = "reactivated"
PLAN_CHANGED = "plan_changed"
PLAN_CHANGE_SCHEDULED = "plan_change_scheduled"
NOTICE_SENT = "notice_sent"

# ---- Actors ----
ACTOR_USER = "user"
ACTOR_SYSTEM = "system"
ACTOR_STRIPE = "stripe"
ACTOR_ADMIN = "admin"


async def record_event(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    event_type: str,
    subscription: Optional[Subscription] = None,
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    from_plan_id: Optional[uuid.UUID] = None,
    to_plan_id: Optional[uuid.UUID] = None,
    actor_type: str = ACTOR_SYSTEM,
    actor_id: Optional[uuid.UUID] = None,
    stripe_event_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> SubscriptionEvent:
    """Append one row to the ledger.

    Added to the session but not committed — the caller owns the transaction,
    so the event and the state change it describes land together or not at all.
    """
    event = SubscriptionEvent(
        organization_id=organization_id,
        subscription_id=subscription.id if subscription is not None else None,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        from_plan_id=from_plan_id,
        to_plan_id=to_plan_id,
        actor_type=actor_type,
        actor_id=actor_id,
        stripe_event_id=stripe_event_id,
        payload=payload or {},
    )
    db.add(event)
    return event


async def has_event(
    db: AsyncSession,
    subscription_id: uuid.UUID,
    event_type: str,
    *,
    notice: Optional[str] = None,
) -> bool:
    """Has this already happened for this subscription?

    The send-once guard for lifecycle emails: a reconciler that runs every 15
    minutes must not send the "your trial ends tomorrow" email 96 times.
    ``notice`` narrows the check to one kind of notice inside the payload.
    """
    result = await db.execute(
        select(SubscriptionEvent.id, SubscriptionEvent.payload).where(
            SubscriptionEvent.subscription_id == subscription_id,
            SubscriptionEvent.event_type == event_type,
        )
    )
    rows = result.all()
    if notice is None:
        return bool(rows)
    return any((row.payload or {}).get("notice") == notice for row in rows)
