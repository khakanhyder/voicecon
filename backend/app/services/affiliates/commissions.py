"""Earning, reversing and maturing affiliate commissions.

Called from the payment webhooks (Stripe ``invoice.paid`` / ``charge.refunded``,
Polar ``order.paid`` / ``order.refunded``) inside their transactions, and from
the billing scheduler to move commissions out of their hold period.

Eligibility, in order — the first failing rule skips the payment:

1. the program is on and the workspace was referred by an affiliate who may earn;
2. the payment's billing period (monthly / yearly) is one this affiliate earns
   on — set per affiliate: yearly only (the default), monthly only, or both;
3. the plan is on the program's eligible list (empty list: every plan);
4. it pays for a new period (create or renewal) — a mid-period upgrade
   proration only earns while an already-commissioned period is running;
5. the first qualifying payment falls inside the referral window;
6. the customer has not used up the affiliate's number of commissioned payments
   *of that billing period* (monthly and yearly are counted separately);
7. something was actually paid, net of discount and tax.

The rate is the affiliate's rate for that billing period.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate import (
    AFFILIATE_EARNING_STATUSES,
    COMMISSION_APPROVED,
    COMMISSION_PAID,
    COMMISSION_PENDING,
    COMMISSION_REJECTED,
    COMMISSION_REVERSED,
    KIND_CLAWBACK,
    KIND_COMMISSION,
    Affiliate,
    AffiliateCommission,
    AffiliateReferral,
)
from app.services.affiliates.program import (
    BASE_BILLING_REASONS,
    PRORATION_BILLING_REASONS,
    earns_on,
    get_program,
    max_payments_for,
    rate_for,
    money,
    utcnow,
)

logger = logging.getLogger(__name__)


@dataclass
class Payment:
    """One paid invoice or order, in the shape both providers reduce to."""

    provider: str
    #: ``stripe:<invoice id>`` or ``polar:<order id>``.
    external_ref: str
    organization_id: uuid.UUID
    plan_slug: Optional[str]
    billing_period: Optional[str]
    billing_reason: Optional[str]
    #: Net of discount, before tax.
    base_amount: Decimal
    currency: str
    paid_at: datetime
    service_period_end: Optional[datetime] = None
    invoice_id: Optional[uuid.UUID] = None


def _skip(reason: str, payment: Payment) -> None:
    logger.info("No affiliate commission for %s: %s", payment.external_ref, reason)


async def record_payment(db: AsyncSession, payment: Payment) -> Optional[AffiliateCommission]:
    """Create the commission this payment earns, if any. Idempotent by ``external_ref``."""
    existing = await db.scalar(
        select(AffiliateCommission).where(AffiliateCommission.external_ref == payment.external_ref)
    )
    if existing is not None:
        return existing

    referral = await db.scalar(
        select(AffiliateReferral).where(AffiliateReferral.organization_id == payment.organization_id)
    )
    if referral is None:
        return None
    affiliate = await db.get(Affiliate, referral.affiliate_id)
    program = await get_program(db)
    if affiliate is None or affiliate.status not in AFFILIATE_EARNING_STATUSES:
        _skip("affiliate cannot earn", payment)
        return None
    if not program.enabled:
        _skip("program disabled", payment)
        return None
    if not earns_on(affiliate, payment.billing_period):
        _skip(
            f"billing period is {payment.billing_period}; affiliate earns on "
            f"{affiliate.commission_billing_periods} payments only",
            payment,
        )
        return None
    eligible = [s for s in (program.eligible_plan_slugs or []) if s]
    if eligible and payment.plan_slug not in eligible:
        _skip(f"plan {payment.plan_slug} not eligible", payment)
        return None

    base_rows = select(AffiliateCommission).where(
        AffiliateCommission.referral_id == referral.id,
        AffiliateCommission.kind == KIND_COMMISSION,
        AffiliateCommission.billing_reason.in_(BASE_BILLING_REASONS),
        AffiliateCommission.status.notin_((COMMISSION_REJECTED,)),
    )
    earned = (await db.execute(base_rows)).scalars().all()

    if payment.billing_reason in BASE_BILLING_REASONS:
        if not earned and program.referral_window_days is not None:
            deadline = referral.created_at + timedelta(days=program.referral_window_days)
            if payment.paid_at > deadline:
                _skip("first yearly payment came after the referral window", payment)
                return None
        same_period = [c for c in earned if c.billing_period == payment.billing_period]
        limit = max_payments_for(affiliate, program, payment.billing_period)
        if limit is not None and len(same_period) >= limit:
            _skip(
                f"customer already earned {len(same_period)} of {limit} commissioned "
                f"{payment.billing_period} payments",
                payment,
            )
            return None
    elif payment.billing_reason in PRORATION_BILLING_REASONS:
        covered = any(
            c.service_period_end and c.service_period_end > payment.paid_at and c.status != COMMISSION_REVERSED
            for c in earned
        )
        if not covered:
            _skip("upgrade proration outside a commissioned year", payment)
            return None
    else:
        _skip(f"billing reason {payment.billing_reason!r} does not earn", payment)
        return None

    base = money(payment.base_amount)
    if base <= 0:
        _skip("nothing was paid", payment)
        return None

    rate = rate_for(affiliate, payment.billing_period)
    amount = money(base * rate / 100)
    if amount <= 0:
        _skip("commission rounds to zero", payment)
        return None

    commission = AffiliateCommission(
        affiliate_id=affiliate.id,
        referral_id=referral.id,
        organization_id=payment.organization_id,
        invoice_id=payment.invoice_id,
        external_ref=payment.external_ref,
        kind=KIND_COMMISSION,
        provider=payment.provider,
        plan_slug=payment.plan_slug,
        billing_period=payment.billing_period,
        billing_reason=payment.billing_reason,
        base_amount=base,
        rate_percent=rate,
        amount=amount,
        original_amount=amount,
        currency=(payment.currency or "usd").lower()[:3],
        status=COMMISSION_PENDING,
        earned_at=payment.paid_at,
        available_at=payment.paid_at + timedelta(days=max(0, program.hold_days)),
        service_period_end=payment.service_period_end,
    )
    db.add(commission)
    if referral.converted_at is None:
        referral.converted_at = payment.paid_at
    await db.flush()
    logger.info(
        "Affiliate %s earned %s %s on %s", affiliate.referral_code, amount, commission.currency, payment.external_ref
    )
    return commission


async def record_payment_safely(db: AsyncSession, payment: Payment) -> None:
    """:func:`record_payment` in a savepoint: a commission bug must never fail a billing webhook.

    A failure is logged loudly; staff can add the commission by hand as an
    adjustment from the admin console.
    """
    try:
        async with db.begin_nested():
            await record_payment(db, payment)
    except Exception as exc:  # noqa: BLE001
        logger.error("Affiliate commission for %s failed: %s", payment.external_ref, exc, exc_info=True)


async def apply_refund(db: AsyncSession, external_ref: str, refunded_fraction: Decimal) -> None:
    """Shrink or cancel the commission of a payment that was (partly) refunded.

    ``refunded_fraction`` is the running total refunded so far (0..1), which is
    what both providers report, so a repeated event changes nothing. Before
    payout the commission itself shrinks; after payout a negative clawback is
    added and nets off the next payout.
    """
    commission = await db.scalar(
        select(AffiliateCommission).where(AffiliateCommission.external_ref == external_ref)
    )
    if commission is None:
        return
    fraction = min(Decimal("1"), max(Decimal("0"), Decimal(refunded_fraction)))
    if fraction <= Decimal(commission.refunded_fraction or 0):
        return
    commission.refunded_fraction = fraction
    target = money(Decimal(commission.original_amount) * (1 - fraction))
    now = utcnow()

    if commission.status in (COMMISSION_REVERSED, COMMISSION_REJECTED):
        return

    if commission.status == COMMISSION_PENDING or (
        commission.status == COMMISSION_APPROVED and commission.payout_id is None
    ):
        commission.amount = target
        if target <= 0:
            commission.status = COMMISSION_REVERSED
            commission.reversed_at = now
        commission.note = _append(commission.note, f"Customer refunded {fraction * 100:.0f}% of the payment.")
        return

    # Already paid, or inside a payout being sent: take the difference back.
    clawed = await db.scalar(
        select(func.coalesce(func.sum(AffiliateCommission.amount), 0)).where(
            AffiliateCommission.external_ref.like(f"clawback:{commission.id}:%")
        )
    )
    delta = money(target - (Decimal(commission.amount) + Decimal(clawed or 0)))
    if delta >= 0:
        return
    count = await db.scalar(
        select(func.count()).where(AffiliateCommission.external_ref.like(f"clawback:{commission.id}:%"))
    )
    db.add(
        AffiliateCommission(
            affiliate_id=commission.affiliate_id,
            referral_id=commission.referral_id,
            organization_id=commission.organization_id,
            invoice_id=commission.invoice_id,
            external_ref=f"clawback:{commission.id}:{(count or 0) + 1}",
            kind=KIND_CLAWBACK,
            provider=commission.provider,
            plan_slug=commission.plan_slug,
            billing_period=commission.billing_period,
            billing_reason=commission.billing_reason,
            base_amount=Decimal("0"),
            rate_percent=commission.rate_percent,
            amount=delta,
            original_amount=delta,
            currency=commission.currency,
            status=COMMISSION_APPROVED,
            earned_at=now,
            available_at=now,
            approved_at=now,
            note=f"Refund after payout ({fraction * 100:.0f}% refunded); deducted from the next payout.",
        )
    )
    await db.flush()


async def apply_refund_safely(db: AsyncSession, external_ref: str, refunded_fraction: Decimal) -> None:
    try:
        async with db.begin_nested():
            await apply_refund(db, external_ref, refunded_fraction)
    except Exception as exc:  # noqa: BLE001
        logger.error("Affiliate refund for %s failed: %s", external_ref, exc, exc_info=True)


def _append(note: Optional[str], line: str) -> str:
    return f"{note}\n{line}" if note else line


async def mature(db: AsyncSession, now: Optional[datetime] = None) -> int:
    """Move commissions whose hold period has ended to ``approved``. Caller commits."""
    now = now or utcnow()
    result = await db.execute(
        update(AffiliateCommission)
        .where(
            AffiliateCommission.status == COMMISSION_PENDING,
            AffiliateCommission.available_at <= now,
        )
        .values(status=COMMISSION_APPROVED, approved_at=now)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount or 0


async def mature_and_commit(db: AsyncSession) -> int:
    """Scheduler entry point."""
    moved = await mature(db)
    await db.commit()
    if moved:
        logger.info("Approved %s affiliate commission(s) past their hold period", moved)
    return moved


async def balances(db: AsyncSession, affiliate_ids: Optional[list] = None) -> Dict[uuid.UUID, Dict[str, Decimal]]:
    """Per-affiliate totals: pending, available (approved, not in a payout), paid, lifetime."""
    query = select(
        AffiliateCommission.affiliate_id,
        AffiliateCommission.status,
        (AffiliateCommission.payout_id.is_(None)).label("unassigned"),
        func.coalesce(func.sum(AffiliateCommission.amount), 0),
    ).group_by(
        AffiliateCommission.affiliate_id,
        AffiliateCommission.status,
        AffiliateCommission.payout_id.is_(None),
    )
    if affiliate_ids is not None:
        if not affiliate_ids:
            return {}
        query = query.where(AffiliateCommission.affiliate_id.in_(affiliate_ids))
    totals: Dict[uuid.UUID, Dict[str, Decimal]] = {}
    for affiliate_id, status, unassigned, total in (await db.execute(query)).all():
        row = totals.setdefault(
            affiliate_id,
            {"pending": Decimal("0"), "available": Decimal("0"), "in_payout": Decimal("0"), "paid": Decimal("0")},
        )
        total = Decimal(total or 0)
        if status == COMMISSION_PENDING:
            row["pending"] += total
        elif status == COMMISSION_APPROVED:
            row["available" if unassigned else "in_payout"] += total
        elif status == COMMISSION_PAID:
            row["paid"] += total
    for row in totals.values():
        row["lifetime"] = row["pending"] + row["available"] + row["in_payout"] + row["paid"]
        for key in row:
            row[key] = money(row[key])
    return totals


def empty_balance() -> Dict[str, Decimal]:
    zero = Decimal("0.00")
    return {"pending": zero, "available": zero, "in_payout": zero, "paid": zero, "lifetime": zero}


async def referral_stats(db: AsyncSession, affiliate_ids: list) -> Dict[uuid.UUID, Dict[str, int]]:
    """Referral and conversion counts per affiliate."""
    if not affiliate_ids:
        return {}
    rows = (
        await db.execute(
            select(
                AffiliateReferral.affiliate_id,
                func.count(AffiliateReferral.id),
                func.count(AffiliateReferral.converted_at),
            )
            .where(AffiliateReferral.affiliate_id.in_(affiliate_ids))
            .group_by(AffiliateReferral.affiliate_id)
        )
    ).all()
    return {aid: {"referrals": int(total), "conversions": int(converted)} for aid, total, converted in rows}


__all__ = [
    "Payment",
    "apply_refund",
    "apply_refund_safely",
    "balances",
    "empty_balance",
    "mature",
    "mature_and_commit",
    "record_payment",
    "record_payment_safely",
    "referral_stats",
]
