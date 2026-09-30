"""Stripe Connect onboarding for affiliates, and paying them.

Each affiliate connects a Stripe **Express** account. A payout is one
``Transfer`` from VoiceCon's Stripe balance to that account, covering every
approved commission not yet paid. Staff start each payout from the admin
console; nothing is sent automatically.

The transfer draws on the *platform's Stripe balance*. While customers pay
through Polar, that balance only holds what VoiceCon tops up, so a transfer can
fail with ``balance_insufficient``: the payout is then marked failed and its
commissions return to the payable pool.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.affiliate import (
    COMMISSION_APPROVED,
    COMMISSION_PAID,
    PAYOUT_FAILED,
    PAYOUT_PAID,
    PAYOUT_PROCESSING,
    Affiliate,
    AffiliateCommission,
    AffiliatePayout,
)
from app.services.affiliates.commissions import mature
from app.services.affiliates.program import get_program, money, utcnow

logger = logging.getLogger(__name__)

METHOD_STRIPE = "stripe"
METHOD_MANUAL = "manual"


class PayoutError(Exception):
    """Refused or failed. ``public_message`` is safe to show the person who asked."""

    @property
    def public_message(self) -> str:
        return str(self)


def connect_ready() -> bool:
    """Can this server talk to Stripe Connect at all?"""
    return bool(settings.stripe_configured)


def _require_connect() -> None:
    if not connect_ready():
        raise PayoutError("Stripe payouts are not set up yet. Please try again later.")


def _stripe():
    import stripe

    stripe.api_key = settings.stripe_secret_key
    return stripe


# ---- Onboarding ----


async def onboarding_link(
    db: AsyncSession, affiliate: Affiliate, *, country: Optional[str], refresh_url: str, return_url: str
) -> str:
    """A Stripe-hosted onboarding link, creating the Express account the first time."""
    _require_connect()
    stripe = _stripe()
    try:
        if not affiliate.stripe_account_id:
            params: dict = {
                "type": "express",
                "email": affiliate.user.email if affiliate.user else None,
                "capabilities": {"transfers": {"requested": True}},
                "business_profile": {"product_description": f"{settings.APP_NAME} affiliate payouts"},
                "metadata": {"affiliate_id": str(affiliate.id)},
            }
            country = (country or "").strip().upper()[:2] or None
            if country:
                params["country"] = country
                platform = await asyncio.to_thread(stripe.Account.retrieve)
                if (platform.get("country") or "").upper() != country:
                    # A partner abroad receives transfers only; Stripe calls
                    # this the recipient service agreement.
                    params["tos_acceptance"] = {"service_agreement": "recipient"}
            account = await asyncio.to_thread(stripe.Account.create, **params)
            affiliate.stripe_account_id = account.id
            affiliate.stripe_country = (account.get("country") or country or "")[:2] or None
            await db.commit()

        link = await asyncio.to_thread(
            stripe.AccountLink.create,
            account=affiliate.stripe_account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )
    except stripe.error.StripeError as exc:
        logger.error("Stripe Connect onboarding failed for affiliate %s: %s", affiliate.id, exc)
        raise PayoutError(
            "We couldn't start Stripe setup. Check that your country is supported by Stripe, "
            "or contact us and we'll help."
        )
    return link.url


async def refresh_account(db: AsyncSession, affiliate: Affiliate) -> Affiliate:
    """Pull the connected account's readiness from Stripe. Caller commits."""
    if not affiliate.stripe_account_id or not connect_ready():
        return affiliate
    stripe = _stripe()
    try:
        account = await asyncio.to_thread(stripe.Account.retrieve, affiliate.stripe_account_id)
    except stripe.error.StripeError as exc:
        logger.warning("Could not refresh Stripe account %s: %s", affiliate.stripe_account_id, exc)
        return affiliate
    capabilities = account.get("capabilities") or {}
    affiliate.stripe_details_submitted = bool(account.get("details_submitted"))
    affiliate.stripe_payouts_enabled = bool(account.get("payouts_enabled"))
    affiliate.stripe_transfers_enabled = capabilities.get("transfers") == "active"
    affiliate.stripe_country = (account.get("country") or affiliate.stripe_country or "")[:2] or None
    affiliate.stripe_checked_at = utcnow()
    return affiliate


async def dashboard_link(affiliate: Affiliate) -> str:
    """A one-time link into the affiliate's Stripe Express dashboard."""
    _require_connect()
    if not affiliate.stripe_account_id:
        raise PayoutError("Connect your Stripe account first.")
    stripe = _stripe()
    try:
        link = await asyncio.to_thread(stripe.Account.create_login_link, affiliate.stripe_account_id)
    except stripe.error.StripeError as exc:
        logger.warning("Stripe login link failed for %s: %s", affiliate.stripe_account_id, exc)
        raise PayoutError("Finish your Stripe setup first, then try again.")
    return link.url


def connect_state(affiliate: Affiliate) -> str:
    """``not_connected`` | ``incomplete`` | ``ready``"""
    if not affiliate.stripe_account_id:
        return "not_connected"
    if affiliate.stripe_transfers_enabled:
        return "ready"
    return "incomplete"


# ---- Payouts ----


async def payable(db: AsyncSession, affiliate_id: uuid.UUID) -> list[AffiliateCommission]:
    return list(
        (
            await db.execute(
                select(AffiliateCommission)
                .where(
                    AffiliateCommission.affiliate_id == affiliate_id,
                    AffiliateCommission.status == COMMISSION_APPROVED,
                    AffiliateCommission.payout_id.is_(None),
                )
                .order_by(AffiliateCommission.earned_at)
            )
        ).scalars().all()
    )


async def create_payout(
    db: AsyncSession,
    affiliate_id: uuid.UUID,
    *,
    method: str,
    actor_id: Optional[uuid.UUID],
    reference: Optional[str] = None,
    note: Optional[str] = None,
    ignore_minimum: bool = False,
) -> AffiliatePayout:
    """Pay every approved, unpaid commission of one affiliate. Commits.

    The payout row and its commissions are committed as ``processing`` before
    Stripe is called, and the transfer carries the payout id as its idempotency
    key, so a crash or a double click cannot send the money twice.
    """
    if method not in (METHOD_STRIPE, METHOD_MANUAL):
        raise PayoutError("Unknown payout method.")

    affiliate = await db.scalar(select(Affiliate).where(Affiliate.id == affiliate_id).with_for_update())
    if affiliate is None:
        raise PayoutError("Affiliate not found.")
    in_flight = await db.scalar(
        select(AffiliatePayout.id).where(
            AffiliatePayout.affiliate_id == affiliate.id, AffiliatePayout.status == PAYOUT_PROCESSING
        )
    )
    if in_flight is not None:
        raise PayoutError("A payout to this affiliate is already being sent.")

    await mature(db)
    rows = await payable(db, affiliate.id)
    if not rows:
        raise PayoutError("There is nothing approved to pay yet.")
    currencies = {c.currency for c in rows}
    if len(currencies) > 1:
        raise PayoutError(f"Approved commissions are in several currencies ({', '.join(sorted(currencies))}).")
    currency = currencies.pop()
    total = money(sum((Decimal(c.amount) for c in rows), Decimal("0")))
    if total <= 0:
        raise PayoutError("Refunds leave nothing to pay: the approved balance is not positive.")
    program = await get_program(db)
    if not ignore_minimum and total < Decimal(program.min_payout_amount):
        raise PayoutError(
            f"The approved balance ({total} {currency.upper()}) is below the minimum payout "
            f"({money(program.min_payout_amount)}). Tick 'ignore minimum' to pay anyway."
        )

    if method == METHOD_STRIPE:
        _require_connect()
        await refresh_account(db, affiliate)
        if not affiliate.stripe_transfers_enabled:
            raise PayoutError("This affiliate's Stripe account can't receive transfers yet (setup not finished).")

    now = utcnow()
    payout = AffiliatePayout(
        affiliate_id=affiliate.id,
        amount=total,
        currency=currency,
        method=method,
        status=PAYOUT_PROCESSING,
        reference=(reference or "").strip()[:255] or None,
        note=(note or "").strip() or None,
        commission_count=len(rows),
        created_by=actor_id,
    )
    db.add(payout)
    await db.flush()
    for commission in rows:
        commission.payout_id = payout.id

    if method == METHOD_MANUAL:
        _settle(payout, rows, now)
        await db.commit()
        return payout

    await db.commit()
    return await _send_transfer(db, payout, affiliate, rows)


async def resume_payout(db: AsyncSession, payout_id: uuid.UUID) -> AffiliatePayout:
    """Finish a Stripe payout left in ``processing`` (a crash between commit and transfer).

    Safe to repeat: the transfer reuses the payout's idempotency key, so if the
    first attempt did reach Stripe the same transfer comes back.
    """
    payout = await db.scalar(select(AffiliatePayout).where(AffiliatePayout.id == payout_id).with_for_update())
    if payout is None:
        raise PayoutError("Payout not found.")
    if payout.status != PAYOUT_PROCESSING or payout.method != METHOD_STRIPE:
        raise PayoutError("Only a Stripe payout that is still processing can be resumed.")
    _require_connect()
    affiliate = await db.get(Affiliate, payout.affiliate_id)
    rows = list(
        (await db.execute(select(AffiliateCommission).where(AffiliateCommission.payout_id == payout.id))).scalars().all()
    )
    return await _send_transfer(db, payout, affiliate, rows)


async def _send_transfer(
    db: AsyncSession, payout: AffiliatePayout, affiliate: Affiliate, rows: list[AffiliateCommission]
) -> AffiliatePayout:
    stripe = _stripe()
    try:
        transfer = await asyncio.to_thread(
            stripe.Transfer.create,
            amount=int((Decimal(payout.amount) * 100).to_integral_value()),
            currency=payout.currency,
            destination=affiliate.stripe_account_id,
            transfer_group=f"affiliate_payout_{payout.id}",
            description=f"{settings.APP_NAME} affiliate commissions",
            metadata={"affiliate_id": str(affiliate.id), "payout_id": str(payout.id)},
            idempotency_key=f"affiliate-payout:{payout.id}",
        )
    except stripe.error.StripeError as exc:
        reason = getattr(exc, "user_message", None) or str(exc)
        code = getattr(exc, "code", None)
        logger.error("Affiliate payout %s failed: %s (%s)", payout.id, reason, code)
        payout.status = PAYOUT_FAILED
        payout.failure_reason = (
            "VoiceCon's Stripe balance is too low for this transfer. Top up the balance and retry."
            if code == "balance_insufficient"
            else reason
        )[:2000]
        for commission in rows:
            commission.payout_id = None
        await db.commit()
        return payout

    payout.stripe_transfer_id = transfer.id
    _settle(payout, rows, utcnow())
    await db.commit()
    return payout


def _settle(payout: AffiliatePayout, rows: list[AffiliateCommission], when) -> None:
    payout.status = PAYOUT_PAID
    payout.paid_at = when
    for commission in rows:
        commission.status = COMMISSION_PAID
        commission.paid_at = when
