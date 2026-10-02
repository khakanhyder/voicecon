"""
The prepaid wallet: balance, ledger, and the money reserved for calls in flight.

Everything that moves a balance goes through :func:`apply`, and three rules
hold for every movement:

* **One ledger row per movement, in the same transaction as the balance.** The
  balance on the wallet row is only ever changed together with the row that
  explains it, so the two cannot drift apart. The reconciler checks anyway
  (:func:`ledger_mismatches`).
* **Exactly once.** Each movement carries an idempotency key built from what
  caused it (the payment, the call). The key is unique in the database, so a
  webhook delivered twice or a carrier callback repeated cannot credit or
  charge twice — the second attempt finds the first and does nothing.
* **Short locks.** The wallet row is locked for the read-modify-write and
  released by the caller's commit. Nothing here calls a payment provider or
  waits on a live call while holding it.

Money is whole cents in integers. Rates are ``Decimal`` and are rounded to
cents once, when a charge is worked out.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserFacingError
from app.models.subscription import SubscriptionPlan
from app.models.wallet import (
    NOTICE_EMPTY,
    NOTICE_LOW,
    NOTICE_NONE,
    TXN_ADJUSTMENT,
    TXN_NUMBER_FEE,
    TXN_REFUND,
    TXN_TOPUP,
    TXN_USAGE,
    Wallet,
    WalletTransaction,
)
from app.services.billing import catalog

logger = logging.getLogger(__name__)

#: ``Call.call_metadata`` key holding what a live call has reserved::
#:
#:     {"cents": 490, "max_seconds": 840, "per_minute": "0.35"}
HOLD_KEY = "wallet_hold"

#: Shown when a call cannot start because the wallet cannot pay for a minute.
INSUFFICIENT_BALANCE = (
    "Your balance is too low to make or receive calls. Add credit to continue."
)


class WalletError(UserFacingError):
    """A wallet operation that cannot go ahead. The message is for the customer."""


class InsufficientBalance(WalletError):
    """There is not enough unreserved credit for what was asked."""


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------


def to_cents(amount: Any) -> int:
    """A currency amount (``10``, ``"0.35"``, ``Decimal``) as whole cents."""
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_cents(cents: Optional[int]) -> float:
    """Whole cents as a currency amount for JSON. Display only, never arithmetic."""
    return float(Decimal(int(cents or 0)) / 100)


def format_money(cents: int, currency: str = "usd") -> str:
    """``$12.50`` / ``-$3.00`` for emails and ledger descriptions."""
    symbol = "$" if (currency or "usd").lower() == "usd" else f"{currency.upper()} "
    sign = "-" if cents < 0 else ""
    return f"{sign}{symbol}{Decimal(abs(int(cents))) / 100:.2f}"


def rate_cents(billing: Mapping[str, Any]) -> Decimal:
    """Price of one call minute in cents. May be fractional (7.5 cents)."""
    return Decimal(str(billing.get("per_minute") or 0)) * 100


def call_cost_cents(minutes: int, billing: Mapping[str, Any]) -> int:
    """What ``minutes`` of calling costs, rounded to a whole cent once."""
    return int((Decimal(int(minutes)) * rate_cents(billing)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def minutes_affordable(cents: int, billing: Mapping[str, Any]) -> Optional[int]:
    """Whole minutes ``cents`` pays for; ``None`` when minutes are free."""
    rate = rate_cents(billing)
    if rate <= 0:
        return None
    if cents <= 0:
        return 0
    return int((Decimal(int(cents)) / rate).to_integral_value(rounding=ROUND_FLOOR))


# ---------------------------------------------------------------------------
# Plan configuration
# ---------------------------------------------------------------------------


async def prepaid_plan(db: AsyncSession, *, include_inactive: bool = False) -> Optional[SubscriptionPlan]:
    """The prepaid (Pay As You Go) plan on sale, if there is one.

    Found by what its entitlement document says, not by slug, so a renamed or
    re-created plan still counts. With more than one, the first in display
    order wins.
    """
    query = select(SubscriptionPlan).order_by(SubscriptionPlan.sort_order, SubscriptionPlan.created_at)
    if not include_inactive:
        query = query.where(SubscriptionPlan.is_active.is_(True))
    for plan in (await db.execute(query)).scalars().all():
        if plan_is_prepaid(plan):
            return plan
    return None


def plan_document(plan: Optional[SubscriptionPlan]) -> Dict[str, Any]:
    if plan is None:
        return {}
    return plan.entitlements or catalog.entitlements_for_plan(plan.slug)


def plan_is_prepaid(plan: Optional[SubscriptionPlan]) -> bool:
    return catalog.is_prepaid(plan_document(plan))


async def billing_for_org(db: AsyncSession, organization_id: uuid.UUID) -> Dict[str, Any]:
    """The prepaid settings that apply to this organization's wallet.

    A workspace on Pay As You Go uses its own resolved settings (which include
    any per-organization override). Anyone else — a subscriber topping up
    ahead of a switch — gets the plan's.
    """
    from app.services.billing.entitlements import resolve_entitlements

    ent = await resolve_entitlements(db, organization_id)
    if ent.is_prepaid:
        return dict(ent.billing)
    return catalog.billing_config(plan_document(await prepaid_plan(db)))


# ---------------------------------------------------------------------------
# The wallet row
# ---------------------------------------------------------------------------


async def get_wallet(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    create: bool = False,
    lock: bool = False,
) -> Optional[Wallet]:
    """The organization's wallet.

    ``lock`` takes the row lock that serialises balance changes; it is held
    until the caller commits or rolls back, so take it last and commit soon.
    ``create`` makes an empty wallet when there is none.
    """
    query = select(Wallet).where(Wallet.organization_id == organization_id)
    if lock:
        # populate_existing: a wallet already loaded in this session must be
        # re-read under the lock, or the balance used is the stale one.
        query = query.with_for_update().execution_options(populate_existing=True)
    wallet = (await db.execute(query)).scalar_one_or_none()
    if wallet is not None or not create:
        return wallet

    try:
        async with db.begin_nested():
            db.add(Wallet(organization_id=organization_id, balance_cents=0))
    except IntegrityError:
        # Another request created it between the read and the insert.
        pass
    return (await db.execute(query)).scalar_one_or_none()


async def balance_cents(db: AsyncSession, organization_id: uuid.UUID) -> int:
    """Current balance, read fresh from the database (never from a cache)."""
    value = (
        await db.execute(
            select(Wallet.balance_cents).where(Wallet.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    return int(value or 0)


# ---------------------------------------------------------------------------
# Movements
# ---------------------------------------------------------------------------


@dataclass
class Movement:
    """What :func:`apply` did, and what the caller should do once it commits.

    Plain values, captured when the movement was staged, so they can be read
    after the commit without touching the session again.
    """

    transaction: WalletTransaction
    organization_id: uuid.UUID
    amount_cents: int
    balance_cents: int
    currency: str = "usd"
    #: ``low`` or ``empty`` when this movement crossed that threshold and the
    #: owners have not been told yet; otherwise ``None``.
    notice: Optional[str] = None
    #: Auto-recharge is on and has a card to charge.
    auto_recharge_ready: bool = False
    #: The balance is under the auto-recharge threshold and a card is saved.
    wants_recharge: bool = False


def _next_notice_level(balance: int, low_cents: int) -> str:
    if balance <= 0:
        return NOTICE_EMPTY
    if low_cents > 0 and balance < low_cents:
        return NOTICE_LOW
    return NOTICE_NONE


_NOTICE_RANK = {NOTICE_NONE: 0, NOTICE_LOW: 1, NOTICE_EMPTY: 2}


async def find_transaction(db: AsyncSession, idempotency_key: str) -> Optional[WalletTransaction]:
    return (
        await db.execute(
            select(WalletTransaction).where(WalletTransaction.idempotency_key == idempotency_key)
        )
    ).scalar_one_or_none()


async def apply(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    amount_cents: int,
    type: str,
    idempotency_key: Optional[str],
    description: str = "",
    reference_type: Optional[str] = None,
    reference_id: Optional[str] = None,
    client_ref: Optional[str] = None,
    actor_type: str = "system",
    actor_id: Optional[uuid.UUID] = None,
    details: Optional[Dict[str, Any]] = None,
    low_balance_cents: Optional[int] = None,
) -> Optional[Movement]:
    """Move the balance by ``amount_cents`` and write the ledger row for it.

    Staged on ``db`` and flushed, **not committed** — the caller commits, so
    the movement lands together with whatever caused it (the usage record, the
    plan activation). The wallet row stays locked until then.

    Returns ``None`` when ``idempotency_key`` has already been applied: the
    movement happened before and must not happen again. A caller that loses a
    race on the same key gets an ``IntegrityError`` from the flush instead and
    should roll back — the other request applied it.
    """
    amount_cents = int(amount_cents)
    if amount_cents == 0:
        return None

    # Looked up before the lock is taken, so the lock covers only the write.
    if low_balance_cents is None:
        low_balance_cents = to_cents((await billing_for_org(db, organization_id)).get("low_balance") or 0)

    wallet = await get_wallet(db, organization_id, create=True, lock=True)
    if wallet is None:  # pragma: no cover - create=True always yields a row
        raise WalletError("Your balance could not be updated. Please try again.")

    # Checked under the wallet lock, so two deliveries of the same event for
    # this wallet cannot both pass it.
    if idempotency_key and await find_transaction(db, idempotency_key) is not None:
        return None

    balance = int(wallet.balance_cents or 0) + amount_cents
    wallet.balance_cents = balance

    previous_level = wallet.notice_level or NOTICE_NONE
    level = _next_notice_level(balance, low_balance_cents)
    wallet.notice_level = level
    # A notice only on the way down, and only for a level not yet announced.
    notice = level if _NOTICE_RANK[level] > _NOTICE_RANK.get(previous_level, 0) else None

    transaction = WalletTransaction(
        wallet_id=wallet.id,
        organization_id=organization_id,
        type=type,
        amount_cents=amount_cents,
        balance_after_cents=balance,
        currency=wallet.currency or "usd",
        description=(description or "")[:255] or None,
        reference_type=reference_type,
        reference_id=str(reference_id) if reference_id is not None else None,
        client_ref=client_ref,
        idempotency_key=idempotency_key,
        actor_type=actor_type,
        actor_id=actor_id,
        details=details or {},
    )
    db.add(transaction)
    await db.flush()

    auto_recharge_ready = bool(wallet.auto_recharge_enabled and wallet.stripe_payment_method_id)
    wants_recharge = bool(
        amount_cents < 0
        and auto_recharge_ready
        and wallet.auto_recharge_threshold_cents is not None
        and balance < int(wallet.auto_recharge_threshold_cents)
    )
    return Movement(
        transaction=transaction,
        organization_id=organization_id,
        amount_cents=amount_cents,
        balance_cents=balance,
        currency=wallet.currency or "usd",
        notice=notice,
        auto_recharge_ready=auto_recharge_ready,
        wants_recharge=wants_recharge,
    )


async def ledger_mismatches(db: AsyncSession, *, limit: int = 50) -> List[Dict[str, Any]]:
    """Wallets whose stored balance is not the sum of their ledger.

    Should always be empty. Anything returned means a balance was changed
    without a ledger row (or the reverse) and needs a person to look at it —
    nothing is corrected automatically.
    """
    ledger = (
        select(
            WalletTransaction.wallet_id.label("wallet_id"),
            func.coalesce(func.sum(WalletTransaction.amount_cents), 0).label("total"),
        )
        .group_by(WalletTransaction.wallet_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(Wallet.id, Wallet.organization_id, Wallet.balance_cents, ledger.c.total)
            .outerjoin(ledger, ledger.c.wallet_id == Wallet.id)
            .where(Wallet.balance_cents != func.coalesce(ledger.c.total, 0))
            .limit(limit)
        )
    ).all()
    return [
        {
            "wallet_id": str(wallet_id),
            "organization_id": str(organization_id),
            "balance_cents": int(balance or 0),
            "ledger_cents": int(total or 0),
        }
        for wallet_id, organization_id, balance, total in rows
    ]


# ---------------------------------------------------------------------------
# Money reserved for calls in flight
# ---------------------------------------------------------------------------
#
# A call is charged when it ends, so without a reservation two calls running
# together could each spend the whole balance. Each live call therefore holds
# part of the balance, and may only run for as long as its hold pays for. The
# hold lives on the call row, so it needs no cleaning up: once the call is no
# longer in flight it simply stops counting.


def call_hold(call) -> Dict[str, Any]:
    return dict((getattr(call, "call_metadata", None) or {}).get(HOLD_KEY) or {})


async def held_cents(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    exclude_call_id: Optional[uuid.UUID] = None,
) -> int:
    """Credit reserved by the organization's calls in flight right now.

    Uses the same definition of "in flight" as the concurrent-call limit, so a
    call whose final callback never arrived stops holding credit after a few
    hours rather than for ever.
    """
    from app.models.call import Call
    from app.services.billing.entitlements import ACTIVE_CALL_WINDOW, IN_FLIGHT_CALL_STATUSES

    filters = [
        Call.organization_id == organization_id,
        Call.status.in_(IN_FLIGHT_CALL_STATUSES),
        Call.ended_at.is_(None),
        Call.created_at >= datetime.utcnow() - ACTIVE_CALL_WINDOW,
    ]
    if exclude_call_id is not None:
        filters.append(Call.id != exclude_call_id)
    rows = (await db.execute(select(Call.call_metadata).where(*filters))).scalars().all()
    total = 0
    for metadata in rows:
        try:
            total += int(((metadata or {}).get(HOLD_KEY) or {}).get("cents") or 0)
        except (TypeError, ValueError):
            continue
    return total


async def available_cents(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    exclude_call_id: Optional[uuid.UUID] = None,
) -> int:
    """Balance not already reserved by a call in flight."""
    return await balance_cents(db, organization_id) - await held_cents(
        db, organization_id, exclude_call_id=exclude_call_id
    )


async def can_start_call(db: AsyncSession, organization_id: uuid.UUID, billing: Mapping[str, Any]) -> bool:
    """Is there unreserved credit for at least one more minute?"""
    affordable = minutes_affordable(await available_cents(db, organization_id), billing)
    return affordable is None or affordable >= 1


def _share(affordable_minutes: int, wanted_minutes: int, *, single_line: bool) -> int:
    """How many of the affordable minutes one call may reserve.

    A workspace with one line gives the call everything. Otherwise a call takes
    at most half of what is free, so a second call arriving a moment later is
    not turned away by a first call that reserved the lot; a call that outlasts
    its share asks for more (:func:`reserve_for_call` again).
    """
    if affordable_minutes < 1:
        return 0
    share = affordable_minutes if single_line else max(1, affordable_minutes // 2)
    return max(1, min(share, wanted_minutes))


async def reserve_for_call(
    db: AsyncSession,
    call_id: uuid.UUID,
    *,
    max_seconds: int,
    extend: bool = False,
) -> Optional[int]:
    """Reserve credit for a call, or (``extend``) add to what it has reserved.

    ``max_seconds`` is the longest the call could run at all (the agent's
    maximum call duration). Returns how many seconds the call may run in
    total, or ``None`` when the organization is not on a prepaid plan (nothing
    limits the call here). Raises :class:`InsufficientBalance` when there is
    no unreserved credit for a first minute. An extension that finds nothing
    more to reserve returns the same total as before — the caller sees no
    increase and ends the call.

    Calling it again without ``extend`` for a call that already holds credit
    changes nothing, so the dial request and the answer webhook can both call
    it.

    Commits: the hold has to be visible to the next call's check, and the
    wallet lock is released by the same commit.
    """
    from app.models.call import Call
    from app.services.billing.entitlements import resolve_entitlements

    call = await db.get(Call, call_id)
    if call is None or not call.organization_id:
        return None
    ent = await resolve_entitlements(db, call.organization_id)
    if not ent.is_prepaid:
        return None
    billing = ent.billing
    rate = rate_cents(billing)
    if rate <= 0:
        return None

    if not extend and call_hold(call).get("max_seconds"):
        return int(call_hold(call)["max_seconds"])

    wallet = await get_wallet(db, call.organization_id, create=True, lock=True)
    # Re-read under the lock: an extension may race the status callback.
    await db.refresh(call)
    hold = call_hold(call)
    already_cents = int(hold.get("cents") or 0)
    already_seconds = int(hold.get("max_seconds") or 0)

    free = int(wallet.balance_cents or 0) - await held_cents(
        db, call.organization_id, exclude_call_id=call.id
    ) - already_cents
    affordable = minutes_affordable(free, billing) or 0
    wanted_seconds = max(0, int(max_seconds) - already_seconds)
    wanted = int((Decimal(wanted_seconds) / 60).to_integral_value(rounding=ROUND_CEILING))

    single_line = ent.limit(catalog.LIMIT_CONCURRENT_CALLS) == 1
    minutes = _share(affordable, wanted, single_line=single_line) if wanted > 0 else 0

    if minutes < 1:
        # Nothing changed; this only lets go of the lock. A commit, not a
        # rollback: a rollback would expire every object the caller has loaded.
        await db.commit()
        if already_seconds:
            return already_seconds
        raise InsufficientBalance(INSUFFICIENT_BALANCE)

    cents = int((Decimal(minutes) * rate).to_integral_value(rounding=ROUND_CEILING))
    total_seconds = already_seconds + minutes * 60
    # JSON column: reassign, do not mutate in place.
    call.call_metadata = {
        **(call.call_metadata or {}),
        HOLD_KEY: {
            "cents": already_cents + cents,
            "max_seconds": total_seconds,
            "per_minute": str(billing.get("per_minute")),
        },
    }
    await db.commit()
    return total_seconds


__all__ = [
    "HOLD_KEY",
    "INSUFFICIENT_BALANCE",
    "InsufficientBalance",
    "Movement",
    "WalletError",
    "TXN_ADJUSTMENT",
    "TXN_NUMBER_FEE",
    "TXN_REFUND",
    "TXN_TOPUP",
    "TXN_USAGE",
    "apply",
    "available_cents",
    "balance_cents",
    "billing_for_org",
    "call_cost_cents",
    "call_hold",
    "can_start_call",
    "find_transaction",
    "format_money",
    "from_cents",
    "get_wallet",
    "held_cents",
    "ledger_mismatches",
    "minutes_affordable",
    "plan_document",
    "plan_is_prepaid",
    "prepaid_plan",
    "rate_cents",
    "reserve_for_call",
    "to_cents",
]
