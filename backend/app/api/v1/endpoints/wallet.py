"""
The prepaid wallet: balance, top-ups, auto-recharge and history.

Mounted at ``/billing/wallet``, under the same guards as the rest of billing:
anyone who may see the billing page may read the wallet, and only the workspace
owner may put money in or change its settings (``billing:manage``). Like the
rest of ``/billing`` it is exempt from the entitlement guard — a workspace
whose plan has lapsed must always be able to reach the place where it pays.

Nothing here decides a price. The per-minute rate, the top-up bounds and the
phone-number fee come from the plan's entitlement document on the server; the
only number taken from the browser is how much the customer wants to add, and
that is checked against those bounds.
"""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_current_org_id, get_db
from app.core.time import UTCDatetime
from app.models.subscription import Subscription
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services.billing import polar_service, prepaid, providers
from app.services.billing import wallet as wallet_service
from app.services.billing import wallet_topups
from app.services.billing.entitlements import get_entitlement_service, invalidate_entitlements
from app.services.billing.wallet import WalletError

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Schemas ====================


class AutoRechargeView(BaseModel):
    #: Can a saved card be charged automatically with the current provider?
    supported: bool
    enabled: bool
    threshold: Optional[float]
    amount: Optional[float]
    #: The saved card, as printed on a receipt. ``None`` when none is saved.
    card_brand: Optional[str]
    card_last4: Optional[str]


class TopupOptions(BaseModel):
    presets: List[float]
    minimum: float
    maximum: float


class WalletResponse(BaseModel):
    """Everything the wallet card and the top-up dialog render from."""

    #: Is Pay As You Go on sale at all? False hides every wallet surface.
    available: bool
    plan_id: Optional[uuid.UUID]
    plan_name: Optional[str]
    #: The workspace is on the prepaid plan now.
    on_plan: bool
    #: A paid subscription is queued to become Pay As You Go at this date.
    switching_at: Optional[UTCDatetime]

    balance: float
    #: Part of the balance reserved by calls in progress.
    held: float
    currency: str
    per_minute: float
    #: Whole minutes the unreserved balance pays for.
    minutes_left: Optional[int]
    number_monthly_fee: float
    low_balance: float
    is_low: bool
    is_empty: bool

    topup: TopupOptions
    #: ``stripe`` | ``polar``
    provider: str
    #: ``card``: collect the card in-app. ``hosted``: redirect to the provider.
    checkout_mode: str
    #: Can a top-up be taken right now?
    can_topup: bool
    #: Stripe publishable key; only while Stripe is the provider.
    publishable_key: Optional[str]

    auto_recharge: AutoRechargeView


class TransactionView(BaseModel):
    id: uuid.UUID
    #: topup | usage | number_fee | refund | adjustment
    type: str
    #: Signed: positive added credit, negative spent it.
    amount: float
    balance_after: float
    description: Optional[str]
    created_at: UTCDatetime
    receipt_url: Optional[str] = None


class TransactionPage(BaseModel):
    items: List[TransactionView]
    total: int
    page: int
    page_size: int
    pages: int


class AutoRechargeRequest(BaseModel):
    enabled: bool
    #: Top up when the balance falls below this.
    threshold: Optional[float] = Field(None, ge=0)
    #: How much to add each time.
    amount: Optional[float] = Field(None, gt=0)


class TopupRequest(BaseModel):
    """Add credit with a card (Stripe)."""

    amount: float = Field(..., gt=0)
    payment_method_id: str = Field(..., min_length=4, max_length=255, pattern=r"^pm_")
    #: Keep the card for auto-recharge.
    save_card: bool = False
    #: Also move the workspace onto Pay As You Go once the payment is in. Has
    #: no effect on a workspace a provider is billing for a subscription.
    activate: bool = False
    #: Switch auto-recharge on with these settings once the card is saved.
    auto_recharge: Optional[AutoRechargeRequest] = None


class TopupConfirmRequest(BaseModel):
    payment_intent_id: str = Field(..., min_length=4, max_length=255, pattern=r"^pi_")


class TopupSessionRequest(BaseModel):
    """Add credit through the provider's hosted checkout (Polar)."""

    amount: float = Field(..., gt=0)
    activate: bool = False
    return_path: Optional[str] = None
    cancel_path: Optional[str] = None


class TopupSessionResponse(BaseModel):
    url: str
    checkout_id: str


class TopupStatusResponse(BaseModel):
    #: ``active`` (credit is in the wallet) | ``pending`` | ``open`` | ``failed`` | ``expired``
    status: str


# ==================== Helpers ====================


def _wallet_http_error(exc: WalletError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.public_message)


def _safe_path(path: Optional[str], default: str) -> str:
    """A same-site path to send the customer back to. Never an absolute URL."""
    if path and path.startswith("/") and not path.startswith("//") and len(path) <= 300:
        return path
    return default


async def _require_plan(db: AsyncSession):
    plan = await wallet_service.prepaid_plan(db)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=wallet_topups.NOT_AVAILABLE
        )
    return plan


def _validated_auto_recharge(request: AutoRechargeRequest, billing: dict) -> tuple[int, int]:
    """(threshold, amount) in cents for an auto-recharge that is being switched on."""
    if request.threshold is None or request.amount is None:
        raise WalletError("Choose when to top up and how much to add.")
    amount = wallet_topups.validate_amount(request.amount, billing)
    threshold = wallet_service.to_cents(request.threshold)
    minimum, maximum = wallet_topups.topup_bounds(billing)
    if threshold < 100:
        raise WalletError("Auto-recharge needs a balance of at least $1.00 to trigger on.")
    if threshold > maximum:
        raise WalletError(
            f"The trigger balance can be at most {wallet_service.format_money(maximum)}."
        )
    return threshold, amount


async def _view(db: AsyncSession, org_id: uuid.UUID) -> WalletResponse:
    plan = await wallet_service.prepaid_plan(db)
    ent = await get_entitlement_service().resolve(db, org_id)
    billing = await wallet_service.billing_for_org(db, org_id)
    wallet = await wallet_service.get_wallet(db, org_id)

    balance = int(wallet.balance_cents) if wallet else 0
    held = await wallet_service.held_cents(db, org_id) if ent.is_prepaid else 0
    minutes_left = wallet_service.minutes_affordable(balance - held, billing)
    is_empty = minutes_left is not None and minutes_left < 1
    low = wallet_service.to_cents(billing.get("low_balance") or 0)
    minimum, maximum = wallet_topups.topup_bounds(billing)

    switching_at = None
    if ent.subscription_id and ent.cancel_at_period_end:
        subscription = await db.get(Subscription, ent.subscription_id)
        if await prepaid.scheduled_prepaid_plan(db, subscription) is not None:
            switching_at = subscription.current_period_end

    provider = providers.active_provider()
    hosted = provider == providers.POLAR
    can_topup = plan is not None and (
        wallet_topups.polar_ready(plan) if hosted else wallet_topups.stripe_ready()
    )
    from app.core.config import settings

    presets = sorted(
        {
            float(p)
            for p in (billing.get("topup_presets") or [])
            if minimum <= wallet_service.to_cents(p) <= maximum
        }
    )
    return WalletResponse(
        available=plan is not None,
        plan_id=plan.id if plan else None,
        plan_name=plan.name if plan else None,
        on_plan=ent.is_prepaid,
        switching_at=switching_at,
        balance=wallet_service.from_cents(balance),
        held=wallet_service.from_cents(held),
        currency=(wallet.currency if wallet else None) or "usd",
        per_minute=float(billing.get("per_minute") or 0),
        minutes_left=minutes_left,
        number_monthly_fee=float(billing.get("number_monthly_fee") or 0),
        low_balance=wallet_service.from_cents(low),
        is_low=ent.is_prepaid and not is_empty and balance < low,
        is_empty=ent.is_prepaid and is_empty,
        topup=TopupOptions(
            presets=presets,
            minimum=wallet_service.from_cents(minimum),
            maximum=wallet_service.from_cents(maximum),
        ),
        provider=provider,
        checkout_mode="hosted" if hosted else "card",
        can_topup=can_topup,
        publishable_key=settings.STRIPE_PUBLISHABLE_KEY if not hosted else None,
        auto_recharge=AutoRechargeView(
            supported=wallet_topups.auto_recharge_supported(),
            enabled=bool(wallet and wallet.auto_recharge_enabled),
            threshold=(
                wallet_service.from_cents(wallet.auto_recharge_threshold_cents)
                if wallet and wallet.auto_recharge_threshold_cents is not None
                else None
            ),
            amount=(
                wallet_service.from_cents(wallet.auto_recharge_amount_cents)
                if wallet and wallet.auto_recharge_amount_cents is not None
                else None
            ),
            card_brand=wallet.card_brand if wallet and wallet.stripe_payment_method_id else None,
            card_last4=wallet.card_last4 if wallet and wallet.stripe_payment_method_id else None,
        ),
    )


# ==================== Endpoints ====================


@router.get("", response_model=WalletResponse)
async def get_wallet(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """The workspace's balance and everything needed to top it up."""
    return await _view(db, org_id)


@router.get("/transactions", response_model=TransactionPage)
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: Optional[str] = Query(None, max_length=20),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """The wallet's history, newest first: top-ups, call charges, phone number
    fees, refunds and adjustments."""
    filters = [WalletTransaction.organization_id == org_id]
    if type:
        filters.append(WalletTransaction.type == type)
    total = int(
        (await db.execute(select(func.count(WalletTransaction.id)).where(*filters))).scalar() or 0
    )
    rows = (
        await db.execute(
            select(WalletTransaction)
            .where(*filters)
            .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return TransactionPage(
        items=[
            TransactionView(
                id=row.id,
                type=row.type,
                amount=wallet_service.from_cents(row.amount_cents),
                balance_after=wallet_service.from_cents(row.balance_after_cents),
                description=row.description,
                created_at=row.created_at,
                receipt_url=(row.details or {}).get("receipt_url"),
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, -(-total // page_size)),
    )


@router.post("/topup")
async def topup_with_card(
    request: TopupRequest,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Add credit with a card.

    Answers 200 once the wallet is credited. A card whose bank wants the
    payment approved (3-D Secure) gets **202** with what the browser needs to
    show the bank's prompt; the browser then calls ``/topup/confirm``. Nothing
    is credited until Stripe says the payment succeeded.
    """
    await _require_plan(db)
    if not wallet_topups.stripe_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments are not available right now. Please try again shortly.",
        )
    billing = await wallet_service.billing_for_org(db, org_id)
    try:
        amount_cents = wallet_topups.validate_amount(request.amount, billing)
        auto = request.auto_recharge
        if auto is not None and auto.enabled:
            if not request.save_card:
                raise WalletError("Auto-recharge needs the card to be saved.")
            threshold, recharge_amount = _validated_auto_recharge(auto, billing)
            # Stored now; switched on only once the card is actually saved,
            # which happens when this payment succeeds.
            wallet = await wallet_service.get_wallet(db, org_id, create=True)
            wallet.auto_recharge_threshold_cents = threshold
            wallet.auto_recharge_amount_cents = recharge_amount
            await db.commit()

        outcome = await wallet_topups.start_stripe_topup(
            db,
            organization_id=org_id,
            user=current_user,
            amount_cents=amount_cents,
            payment_method_id=request.payment_method_id,
            save_card=request.save_card,
            activate=request.activate,
            enable_auto_recharge=bool(auto is not None and auto.enabled),
        )
    except WalletError as exc:
        raise _wallet_http_error(exc)

    if outcome.get("requires_action"):
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=outcome)
    return outcome


@router.post("/topup/confirm")
async def confirm_topup(
    request: TopupConfirmRequest,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Second half of a top-up whose card needed the bank's approval.

    The browser calls this after the bank's prompt closes, whichever way it
    went. The payment is re-read from Stripe and credited only if Stripe says
    it succeeded; otherwise the customer is told their card was not charged.
    """
    try:
        outcome = await wallet_topups.confirm_stripe_topup(
            db,
            organization_id=org_id,
            user=current_user,
            payment_intent_id=request.payment_intent_id,
        )
    except WalletError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=exc.public_message)
    # 404 for someone else's payment too: never confirm that an id exists.
    if outcome is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if outcome.get("requires_action"):
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=outcome)
    return outcome


@router.post("/topup-session", response_model=TopupSessionResponse)
async def create_topup_session(
    request: TopupSessionRequest,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Send the customer to the provider's hosted checkout to add credit.

    Nothing is credited here: the provider's webhook does that once the
    payment succeeds, and the return page polls
    ``GET /billing/wallet/topup-session/{id}`` until it has.
    """
    plan = await _require_plan(db)
    if not wallet_topups.polar_ready(plan):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments are not available right now. Please try again shortly.",
        )
    billing = await wallet_service.billing_for_org(db, org_id)
    try:
        amount_cents = wallet_topups.validate_amount(request.amount, billing)
        return await wallet_topups.start_polar_topup(
            db,
            organization_id=org_id,
            user=current_user,
            amount_cents=amount_cents,
            activate=request.activate,
            return_path=_safe_path(request.return_path, "/dashboard/settings/billing"),
            cancel_path=_safe_path(request.cancel_path, "/dashboard/settings/billing"),
        )
    except polar_service.PolarError as exc:
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if isinstance(exc, polar_service.PolarNotConfigured)
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=code, detail=exc.public_message)
    except WalletError as exc:
        raise _wallet_http_error(exc)


@router.get("/topup-session/{checkout_id}", response_model=TopupStatusResponse)
async def get_topup_session_status(
    checkout_id: str,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Has a hosted top-up reached the wallet yet?"""
    try:
        topup_status = await wallet_topups.polar_topup_status(
            db, organization_id=org_id, checkout_id=checkout_id
        )
    except polar_service.PolarError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.public_message)
    # Only ever describe this workspace's own checkouts.
    if topup_status is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checkout not found")
    return TopupStatusResponse(status=topup_status)


@router.put("/auto-recharge", response_model=WalletResponse)
async def set_auto_recharge(
    request: AutoRechargeRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Switch auto-recharge on or off, or change when it tops up and by how much.

    Switching it on needs a saved card, which comes from a top-up made with
    "save this card" ticked — a card is never saved without a payment the
    cardholder made themselves.
    """
    wallet = await wallet_service.get_wallet(db, org_id, create=True)
    try:
        if request.enabled:
            if not wallet_topups.auto_recharge_supported():
                raise WalletError("Auto-recharge is not available right now.")
            if not wallet.stripe_payment_method_id:
                raise WalletError(
                    'Add credit with your card and tick "Save this card" first, '
                    "then switch on auto-recharge."
                )
            billing = await wallet_service.billing_for_org(db, org_id)
            threshold, amount = _validated_auto_recharge(request, billing)
            wallet.auto_recharge_threshold_cents = threshold
            wallet.auto_recharge_amount_cents = amount
            wallet.auto_recharge_enabled = True
            # A fresh start: earlier declines belonged to the old settings.
            wallet.auto_recharge_failures = 0
            wallet.auto_recharge_attempted_at = None
        else:
            wallet.auto_recharge_enabled = False
    except WalletError as exc:
        raise _wallet_http_error(exc)
    await db.commit()

    if request.enabled:
        # Already under the new threshold: top up now rather than after the next call.
        wallet_topups.schedule_auto_recharge(org_id)
    return await _view(db, org_id)


@router.delete("/card", response_model=WalletResponse)
async def remove_saved_card(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Forget the card saved for auto-recharge, and switch auto-recharge off."""
    wallet = await wallet_service.get_wallet(db, org_id)
    if wallet is not None and wallet.stripe_payment_method_id:
        payment_method_id = wallet.stripe_payment_method_id
        wallet.stripe_payment_method_id = None
        wallet.card_brand = None
        wallet.card_last4 = None
        wallet.auto_recharge_enabled = False
        await db.commit()
        await wallet_topups.detach_card(payment_method_id)
    invalidate_entitlements(org_id)
    return await _view(db, org_id)
