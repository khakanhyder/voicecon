"""
What stands between a request and one more phone number.

A number is the one resource here that costs money the moment it exists, so
getting one is guarded twice over, on top of the plan checks at the HTTP edge:

- **One at a time per workspace.** ``require_entitlement`` counts the numbers a
  workspace has and the endpoint then buys one; two requests arriving together
  both saw the same count and both bought. :func:`hold_number_slot` takes a
  workspace lock and counts again under it, so the check and the purchase are
  one step.
- **A daily ceiling on Voicecon numbers.** Numbers bought on Voicecon's own
  carrier account are billed to us. :func:`reserve_voicecon_purchase` caps how
  many the whole platform, and any one workspace, may buy in 24 hours, so a bug
  or a stolen card costs a bounded amount. Platform admins are emailed when the
  platform ceiling is reached.

Purchases are counted from the event ledger rather than from ``phone_numbers``,
because a released number's row is deleted while the carrier has already
charged for it: buying and releasing in a loop must still run into the cap.

The locks are Postgres advisory locks scoped to the transaction, so they are
released by the commit that records the number (or by the rollback when the
purchase fails) and can never be left behind by a crashed request.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.entitlement_guard import assert_within_limit
from app.models.subscription import SubscriptionEvent
from app.models.user import User
from app.services.billing import catalog, events
from app.services.billing.entitlements import (
    Entitlements,
    get_entitlement_service,
    resolve_entitlements,
)
from app.services.telephony.purchase_account import VOICECON_UNAVAILABLE

logger = logging.getLogger(__name__)

#: The window both daily caps are counted over.
PURCHASE_WINDOW = timedelta(hours=24)

#: A workspace may buy at least this many Voicecon numbers a day whatever its
#: plan, so picking the wrong number and replacing it is not a day's wait.
MIN_WORKSPACE_DAILY_PURCHASES = 2

#: How long to wait for another request holding the lock. A purchase is one
#: carrier call, so a holder that takes longer than this is stuck, not busy.
WORKSPACE_LOCK_WAIT_SECONDS = 15.0
PLATFORM_LOCK_WAIT_SECONDS = 30.0
_LOCK_POLL_SECONDS = 0.2

WORKSPACE_BUSY = (
    "Another number is being set up for this workspace. Please wait a moment and try again."
)
WORKSPACE_DAILY_LIMIT = (
    "You've reached today's limit for new numbers. Please try again tomorrow or contact support."
)

# Fire-and-forget alert emails; held here so they are not garbage-collected
# before they finish.
_alert_tasks: set = set()


def _utcnow() -> datetime:
    return datetime.utcnow()


async def _lock(db: AsyncSession, key: str, *, wait: float) -> bool:
    """Take a transaction-scoped advisory lock, waiting up to ``wait`` seconds.

    Polls ``pg_try_advisory_xact_lock`` rather than blocking, so giving up
    leaves the transaction usable. On a database without advisory locks
    (SQLite in unit tests) there is nothing to take.
    """
    if db.get_bind().dialect.name != "postgresql":
        return True
    deadline = asyncio.get_running_loop().time() + wait
    while True:
        acquired = (
            await db.execute(
                text("SELECT pg_try_advisory_xact_lock(hashtext(:key))"), {"key": key}
            )
        ).scalar()
        if acquired:
            return True
        if asyncio.get_running_loop().time() >= deadline:
            return False
        await asyncio.sleep(_LOCK_POLL_SECONDS)


async def lock_workspace_numbers(
    db: AsyncSession, organization_id: uuid.UUID, *, wait: float = WORKSPACE_LOCK_WAIT_SECONDS
) -> bool:
    """Serialise changes to how many numbers a workspace holds."""
    return await _lock(db, f"voicecon:numbers:org:{organization_id}", wait=wait)


async def hold_number_slot(db: AsyncSession, organization_id: uuid.UUID) -> Entitlements:
    """Lock the workspace and confirm, under the lock, that it has room for one
    more number.

    Call it immediately before the number is obtained, and do not commit
    between this and the commit that records the number: that commit is what
    releases the lock.

    Raises ``EntitlementError`` (402) when the plan has no room, and 409 when
    another request for the same workspace does not finish in time.
    """
    if not await lock_workspace_numbers(db, organization_id):
        raise HTTPException(status_code=409, detail=WORKSPACE_BUSY)

    entitlements = await resolve_entitlements(db, organization_id)
    count = await get_entitlement_service().count_for_limit(
        db, organization_id, catalog.LIMIT_PHONE_NUMBERS
    )
    entitlements = entitlements.with_usage({catalog.LIMIT_PHONE_NUMBERS: count})
    assert_within_limit(entitlements, catalog.LIMIT_PHONE_NUMBERS)
    return entitlements


def workspace_daily_allowance(entitlements: Entitlements) -> Optional[int]:
    """Voicecon numbers one workspace may buy in 24 hours; ``None`` is no cap.

    Tied to the plan's own number allowance: nobody needs to buy more numbers
    in a day than they are allowed to hold, and the difference is exactly the
    buy-release-buy loop this exists to stop.
    """
    if entitlements.is_unlimited(catalog.LIMIT_PHONE_NUMBERS):
        return None
    return max(MIN_WORKSPACE_DAILY_PURCHASES, entitlements.limit(catalog.LIMIT_PHONE_NUMBERS))


async def purchases_since(
    db: AsyncSession, since: datetime, organization_id: Optional[uuid.UUID] = None
) -> int:
    """Voicecon numbers bought since ``since`` — platform-wide, or by one workspace."""
    query = select(func.count(SubscriptionEvent.id)).where(
        SubscriptionEvent.event_type == events.NUMBER_PURCHASED,
        SubscriptionEvent.created_at >= since,
    )
    if organization_id is not None:
        query = query.where(SubscriptionEvent.organization_id == organization_id)
    return int((await db.execute(query)).scalar() or 0)


async def reserve_voicecon_purchase(
    db: AsyncSession, organization_id: uuid.UUID, entitlements: Entitlements
) -> None:
    """Refuse a Voicecon purchase that would go past a daily cap.

    Takes the platform lock, so Voicecon purchases run one at a time and the
    count read here is still true when the purchase is recorded. Call after
    :func:`hold_number_slot` — the two locks are always taken in that order.
    """
    cap = max(0, int(settings.VOICECON_NUMBER_DAILY_PURCHASE_CAP))

    # Pay As You Go pays each number's monthly fee from the wallet. Refuse the
    # purchase up front when the wallet cannot cover the first month, rather
    # than buying a number that goes on hold at the next sweep.
    if entitlements.is_prepaid:
        from app.services.billing import prepaid, wallet as wallet_service

        fee = prepaid.number_fee_cents(entitlements.billing)
        if fee > 0 and await wallet_service.available_cents(db, organization_id) < fee:
            raise HTTPException(
                status_code=402,
                detail=(
                    f"A phone number costs {wallet_service.format_money(fee)} a month on your plan, "
                    "and your balance does not cover it. Add credit, then try again."
                ),
            )

    if not await _lock(db, "voicecon:numbers:platform", wait=PLATFORM_LOCK_WAIT_SECONDS):
        raise HTTPException(status_code=503, detail=VOICECON_UNAVAILABLE)

    since = _utcnow() - PURCHASE_WINDOW

    allowance = workspace_daily_allowance(entitlements)
    if allowance is not None:
        mine = await purchases_since(db, since, organization_id)
        if mine >= allowance:
            logger.warning(
                "Org %s refused a Voicecon number: %d bought in the last 24h (allowance %d)",
                organization_id, mine, allowance,
            )
            raise HTTPException(status_code=429, detail=WORKSPACE_DAILY_LIMIT)

    total = await purchases_since(db, since)
    if total >= cap:
        # A cap of 0 is an operator pausing purchases on purpose: no alert.
        if cap:
            await alert_purchase_cap_reached(db, organization_id, total=total, cap=cap)
        raise HTTPException(status_code=503, detail=VOICECON_UNAVAILABLE)


async def record_voicecon_purchase(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    phone_number: str,
    user_id: Optional[uuid.UUID] = None,
) -> None:
    """Count a Voicecon purchase against the daily caps.

    Staged on ``db``, so it commits together with the number's own row.
    """
    await events.record_event(
        db,
        organization_id=organization_id,
        event_type=events.NUMBER_PURCHASED,
        actor_type=events.ACTOR_USER if user_id else events.ACTOR_SYSTEM,
        actor_id=user_id,
        payload={"phone_number": phone_number},
    )


async def alert_if_cap_now_reached(db: AsyncSession, organization_id: uuid.UUID) -> None:
    """Tell the admins when a purchase just used the last slot of the day.

    Run after the purchase has committed, so they hear about it before the
    next customer is turned away rather than because of it.
    """
    try:
        cap = max(0, int(settings.VOICECON_NUMBER_DAILY_PURCHASE_CAP))
        total = await purchases_since(db, _utcnow() - PURCHASE_WINDOW)
        if cap and total >= cap:
            await alert_purchase_cap_reached(db, organization_id, total=total, cap=cap)
    except Exception as exc:  # noqa: BLE001 — the number is bought; never fail on the alert
        logger.error(f"Could not check the Voicecon purchase cap after a purchase: {exc}")


async def alert_purchase_cap_reached(
    db: AsyncSession, organization_id: uuid.UUID, *, total: int, cap: int
) -> None:
    """Email the platform admins that Voicecon number buying has stopped.

    At most once per 24 hours. Written on a session of its own, because the
    request that tripped the cap is about to be refused and rolled back.
    """
    logger.error(
        "Voicecon number purchase cap reached: %d bought in the last 24h (cap %d). "
        "Further Voicecon purchases are refused until older ones leave the window.",
        total, cap,
    )
    try:
        async with AsyncSession(bind=db.bind, expire_on_commit=False) as side:
            already = (
                await side.execute(
                    select(SubscriptionEvent.id)
                    .where(
                        SubscriptionEvent.event_type == events.NUMBER_CAP_REACHED,
                        SubscriptionEvent.created_at >= _utcnow() - PURCHASE_WINDOW,
                    )
                    .limit(1)
                )
            ).first()
            if already:
                return
            await events.record_event(
                side,
                organization_id=organization_id,
                event_type=events.NUMBER_CAP_REACHED,
                payload={"purchased_24h": total, "cap": cap},
            )
            admins = (
                await side.execute(
                    select(User.email).where(
                        User.is_platform_admin.is_(True), User.is_active.is_(True)
                    )
                )
            ).scalars().all()
            await side.commit()
    except Exception as exc:  # noqa: BLE001 — an alert must never break the request
        logger.error(f"Could not record the Voicecon purchase cap alert: {exc}")
        return

    if not admins:
        return
    task = asyncio.create_task(_email_admins(list(admins), total=total, cap=cap))
    _alert_tasks.add(task)
    task.add_done_callback(_alert_tasks.discard)


async def _email_admins(emails: list, *, total: int, cap: int) -> None:
    from app.services.email.service import email_service

    base = (settings.FRONTEND_URL or "").rstrip("/")
    for email in emails:
        try:
            await email_service.send_billing_notice(
                to_email=email,
                subject="Voicecon number purchases are paused for today",
                heading="The daily number purchase limit was reached",
                intro=(
                    f"{total} Voicecon numbers were bought on the platform phone "
                    f"account in the last 24 hours, which is the daily limit of {cap}. "
                    "Customers can't buy another Voicecon number until older "
                    "purchases leave the 24-hour window."
                ),
                bullets=[
                    "If this is real demand, raise the limit under API Keys & Providers → Twilio.",
                    "If it is not, check Phone Numbers for the workspaces that bought them.",
                    "Numbers on a customer's own provider are not affected.",
                ],
                action_url=f"{base}/admin/phone-numbers",
                action_label="Review phone numbers",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Could not email {email} about the purchase cap: {exc}")
