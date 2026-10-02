"""
Putting money into the wallet: card top-ups (Stripe), hosted top-ups (Polar),
auto-recharge, and the refunds and disputes that take it back out.

One rule shapes every path here: **the wallet is credited only when the
provider says the money moved** — never because the browser came back to a
success page. Each provider therefore has two witnesses for the same payment:

* Stripe — the request that confirms the card (or ``/wallet/topup/confirm``
  after the bank's 3-D Secure prompt), and the ``payment_intent.succeeded``
  webhook for a browser that never came back.
* Polar — the ``order.paid`` webhook only; the return page just waits for it.

Both witnesses call the same crediting function, and the ledger's idempotency
key is the provider's own payment id, so whichever arrives second is a no-op.

Auto-recharge exists only on Stripe. Polar is a Merchant of Record with a
hosted checkout and offers no way to charge a saved card later without the
customer present, so on Polar the owners are emailed when the balance runs low
and top up by hand.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import quote

import stripe
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.subscription import SOURCE_WALLET, STATUS_ACTIVE, Subscription
from app.models.user import Organization, User
from app.models.wallet import TXN_REFUND, TXN_TOPUP, Wallet, WalletTransaction
from app.services.billing import catalog, events, prepaid, providers
from app.services.billing import wallet as wallet_service
from app.services.billing import wallet_notices
from app.services.billing.wallet import WalletError

logger = logging.getLogger(__name__)

#: ``metadata.kind`` on every payment this module starts. A payment without it
#: is somebody else's (a subscription invoice) and is left alone.
TOPUP_KIND = "wallet_topup"

REF_STRIPE_INTENT = "stripe_payment_intent"
REF_STRIPE_CHARGE = "stripe_charge"
REF_STRIPE_DISPUTE = "stripe_dispute"
REF_POLAR_ORDER = "polar_order"

#: An automatic charge is not started again within this long of the last one,
#: so a burst of calls ending together starts a single charge.
AUTO_RECHARGE_COOLDOWN = timedelta(minutes=10)
#: After a declined automatic charge, how long before the card is tried again.
AUTO_RECHARGE_RETRY_AFTER = timedelta(hours=24)
#: Consecutive declines after which auto-recharge switches itself off.
AUTO_RECHARGE_MAX_FAILURES = 3

NOT_AVAILABLE = "Pay As You Go is not available right now. Please try again later."
NOT_CHARGED = (
    "Your card was not charged — {reason}. Nothing has changed on your account. "
    "Try again or use a different card."
)

# Fire-and-forget auto-recharge tasks; held so they are not garbage-collected
# before they finish.
_tasks: set = set()


def _get(obj: Any, key: str, default: Any = None) -> Any:
    try:
        return obj.get(key, default)
    except AttributeError:
        return getattr(obj, key, default)


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes")


def _as_uuid(value: Any) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Amounts
# ---------------------------------------------------------------------------


def topup_bounds(billing: Mapping[str, Any]) -> tuple[int, int]:
    """(minimum, maximum) top-up in cents."""
    minimum = max(100, wallet_service.to_cents(billing.get("topup_min") or 0))
    maximum = max(minimum, wallet_service.to_cents(billing.get("topup_max") or 0))
    return minimum, maximum


def validate_amount(amount: Any, billing: Mapping[str, Any]) -> int:
    """A requested top-up as whole cents, or a :class:`WalletError` saying why not.

    The amount comes from the browser, so it is checked against the plan's own
    bounds here; the price of a *minute* is never taken from the client at all.
    """
    try:
        cents = wallet_service.to_cents(amount)
    except Exception:
        raise WalletError("Enter the amount you want to add.")
    minimum, maximum = topup_bounds(billing)
    if cents < minimum:
        raise WalletError(f"The smallest top-up is {wallet_service.format_money(minimum)}.")
    if cents > maximum:
        raise WalletError(
            f"The largest single top-up is {wallet_service.format_money(maximum)}. "
            "Contact support if you need more."
        )
    return cents


# ---------------------------------------------------------------------------
# What happens after a credit has committed
# ---------------------------------------------------------------------------


@dataclass
class CreditResult:
    """The outcome of one attempt to credit a payment."""

    organization_id: uuid.UUID
    #: False when this payment had already been credited (a repeat delivery).
    credited: bool
    amount_cents: int = 0
    balance_cents: int = 0
    currency: str = "usd"
    #: The workspace moved onto the prepaid plan as part of this credit.
    activated_plan: Optional[str] = None
    automatic: bool = False


async def run_followups(db: AsyncSession, results: List[CreditResult]) -> None:
    """Everything a committed top-up triggers. Never raises.

    The plan cache is dropped, the owners are told, and phone numbers that were
    on hold for want of credit are paid for and switched back on.
    """
    from app.services.billing.entitlements import invalidate_entitlements

    for result in results:
        invalidate_entitlements(result.organization_id)
        if not result.credited:
            continue
        try:
            if result.activated_plan:
                await wallet_notices.plan_started(
                    db,
                    result.organization_id,
                    plan_name=result.activated_plan,
                    balance_cents=result.balance_cents,
                    currency=result.currency,
                )
            else:
                await wallet_notices.topup_received(
                    db,
                    result.organization_id,
                    amount_cents=result.amount_cents,
                    balance_cents=result.balance_cents,
                    currency=result.currency,
                    automatic=result.automatic,
                )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Top-up notice failed for org {result.organization_id}: {exc}")
        try:
            from app.services.telephony.number_reclaim import restore_numbers

            await restore_numbers(db, result.organization_id)
        except Exception as exc:  # noqa: BLE001
            try:
                await db.rollback()
            except Exception:  # pragma: no cover - defensive
                pass
            logger.error(f"Could not restore numbers for org {result.organization_id}: {exc}")


async def _credit(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    amount_cents: int,
    idempotency_key: str,
    reference_type: str,
    reference_id: str,
    client_ref: Optional[str],
    actor_type: str,
    actor_id: Optional[uuid.UUID],
    activate: bool,
    automatic: bool,
    details: Dict[str, Any],
    event_key: Optional[str] = None,
) -> CreditResult:
    """Stage a top-up credit and, if asked, the move onto the prepaid plan.

    Caller commits: the credit and the activation land together or not at all.
    """
    billing = await wallet_service.billing_for_org(db, organization_id)
    movement = await wallet_service.apply(
        db,
        organization_id,
        amount_cents=amount_cents,
        type=TXN_TOPUP,
        idempotency_key=idempotency_key,
        description="Auto-recharge" if automatic else "Credit added",
        reference_type=reference_type,
        reference_id=reference_id,
        client_ref=client_ref,
        actor_type=actor_type,
        actor_id=actor_id,
        details=details,
        low_balance_cents=wallet_service.to_cents(billing.get("low_balance") or 0),
    )
    if movement is None:
        return CreditResult(organization_id=organization_id, credited=False)

    activated_plan = None
    if activate:
        plan = await wallet_service.prepaid_plan(db)
        before = await prepaid.current_subscription(db, organization_id)
        was_on_plan = (
            before is not None
            and plan is not None
            and before.plan_id == plan.id
            and before.source == SOURCE_WALLET
            and before.status == STATUS_ACTIVE
        )
        subscription = await prepaid.activate(
            db,
            organization_id,
            plan=plan,
            actor_type=actor_type,
            actor_id=actor_id,
            event_key=event_key,
        )
        if subscription is not None and plan is not None and not was_on_plan:
            activated_plan = plan.name

    return CreditResult(
        organization_id=organization_id,
        credited=True,
        amount_cents=amount_cents,
        balance_cents=movement.balance_cents,
        currency=movement.currency,
        activated_plan=activated_plan,
        automatic=automatic,
    )


async def _refunded_so_far(db: AsyncSession, reference_type: str, reference_id: str) -> int:
    """Cents already taken back for this payment (a positive number)."""
    total = (
        await db.execute(
            select(func.coalesce(func.sum(WalletTransaction.amount_cents), 0)).where(
                WalletTransaction.type == TXN_REFUND,
                WalletTransaction.reference_type == reference_type,
                WalletTransaction.reference_id == reference_id,
            )
        )
    ).scalar()
    return -int(total or 0)


async def _debit_refund(
    db: AsyncSession,
    topup: WalletTransaction,
    *,
    refunded_total_cents: int,
    reference_type: str,
    reference_id: str,
    actor_type: str,
    description: str = "Top-up refunded",
) -> Optional[wallet_service.Movement]:
    """Take a refunded top-up back out of the wallet. Caller commits.

    Providers report the *cumulative* amount refunded, so only the part not yet
    taken back is debited, and never more than the top-up put in. The balance
    may go below zero when the credit has already been spent; that blocks calls
    until it is made good, which is the point.
    """
    refunded_total_cents = min(int(refunded_total_cents), int(topup.amount_cents))
    delta = refunded_total_cents - await _refunded_so_far(db, reference_type, reference_id)
    if delta <= 0:
        return None
    return await wallet_service.apply(
        db,
        topup.organization_id,
        amount_cents=-delta,
        type=TXN_REFUND,
        idempotency_key=f"refund:{reference_type}:{reference_id}:{refunded_total_cents}",
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        actor_type=actor_type,
        details={"topup_transaction_id": str(topup.id)},
    )


# ---------------------------------------------------------------------------
# Stripe
# ---------------------------------------------------------------------------


def stripe_ready() -> bool:
    """Can a card be charged through Stripe right now?"""
    return providers.active_provider() == providers.STRIPE and providers.is_ready(providers.STRIPE)


async def _configure_stripe() -> None:
    from app.services.billing.stripe_service import get_stripe_service

    await get_stripe_service()  # points the SDK at the current key; 503 if unset


async def _stripe_customer(db: AsyncSession, organization_id: uuid.UUID, user: User) -> str:
    """The Stripe customer top-ups are charged to, created on first use.

    Kept on the wallet rather than the subscription: a Pay As You Go
    subscription has no Stripe object at all. A customer id from the other
    Stripe mode (test keys swapped for live) is replaced rather than reused.
    """
    wallet = await wallet_service.get_wallet(db, organization_id, create=True)
    candidate = wallet.stripe_customer_id
    if not candidate:
        candidate = (
            await db.execute(
                select(Subscription.stripe_customer_id)
                .where(
                    Subscription.organization_id == organization_id,
                    Subscription.stripe_customer_id.is_not(None),
                )
                .order_by(Subscription.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    if candidate:
        try:
            customer = await asyncio.to_thread(stripe.Customer.retrieve, candidate)
            if not _get(customer, "deleted", False):
                if wallet.stripe_customer_id != candidate:
                    wallet.stripe_customer_id = candidate
                    await db.commit()
                return candidate
        except stripe.error.InvalidRequestError as exc:
            if getattr(exc, "code", None) != "resource_missing":
                raise

    customer = await asyncio.to_thread(
        stripe.Customer.create,
        email=user.email,
        name=user.full_name or user.email,
        metadata={"organization_id": str(organization_id)},
    )
    wallet.stripe_customer_id = customer.id
    # A card saved under the old customer cannot be charged under the new one.
    wallet.stripe_payment_method_id = None
    wallet.card_brand = None
    wallet.card_last4 = None
    await db.commit()
    return customer.id


def _is_topup_intent(intent: Any) -> bool:
    return _get(_get(intent, "metadata") or {}, "kind") == TOPUP_KIND


async def _card_details(payment_method_id: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """(brand, last4) of a saved card, for the "Visa ending 4242" line."""
    if not payment_method_id:
        return None, None
    try:
        method = await asyncio.to_thread(stripe.PaymentMethod.retrieve, payment_method_id)
        card = _get(method, "card") or {}
        return _get(card, "brand"), _get(card, "last4")
    except Exception as exc:  # noqa: BLE001 — cosmetic; the card still works
        logger.warning(f"Could not read card details for {payment_method_id}: {exc}")
        return None, None


async def credit_stripe_intent(
    db: AsyncSession, intent: Any, *, actor: Optional[User] = None
) -> Optional[CreditResult]:
    """Credit a succeeded top-up PaymentIntent. Commits. Idempotent.

    Returns ``None`` for anything that is not a paid wallet top-up for a known
    organization, so the webhook can hand every PaymentIntent to it.
    """
    if not _is_topup_intent(intent) or _get(intent, "status") != "succeeded":
        return None
    metadata = _get(intent, "metadata") or {}
    organization_id = _as_uuid(_get(metadata, "organization_id"))
    if organization_id is None or await db.get(Organization, organization_id) is None:
        logger.error(f"Top-up {_get(intent, 'id')} names no known organization")
        return None

    intent_id = _get(intent, "id")
    amount = int(_get(intent, "amount_received") or _get(intent, "amount") or 0)
    if amount <= 0:
        return None
    automatic = _truthy(_get(metadata, "automatic"))
    save_card = _truthy(_get(metadata, "save_card"))
    payment_method = _get(intent, "payment_method")
    if payment_method is not None and not isinstance(payment_method, str):
        payment_method = _get(payment_method, "id")

    # Network call, so before the wallet lock is taken.
    brand = last4 = None
    if save_card and payment_method:
        await _configure_stripe()
        brand, last4 = await _card_details(payment_method)

    latest_charge = _get(intent, "latest_charge")
    details: Dict[str, Any] = {"provider": "stripe", "automatic": automatic}
    if latest_charge is not None and not isinstance(latest_charge, str):
        details["receipt_url"] = _get(latest_charge, "receipt_url")
        details["charge_id"] = _get(latest_charge, "id")
    elif isinstance(latest_charge, str):
        details["charge_id"] = latest_charge

    result = await _credit(
        db,
        organization_id,
        amount_cents=amount,
        idempotency_key=f"topup:stripe:{intent_id}",
        reference_type=REF_STRIPE_INTENT,
        reference_id=intent_id,
        client_ref=_get(metadata, "topup_id"),
        actor_type=events.ACTOR_USER if actor is not None else events.ACTOR_STRIPE,
        actor_id=actor.id if actor is not None else _as_uuid(_get(metadata, "user_id")),
        activate=_truthy(_get(metadata, "activate")),
        automatic=automatic,
        details=details,
    )
    if result.credited:
        wallet = await wallet_service.get_wallet(db, organization_id)
        # A card that just paid is a card that works: forget earlier declines.
        wallet.auto_recharge_failures = 0
        customer = _get(intent, "customer")
        if customer and isinstance(customer, str):
            wallet.stripe_customer_id = customer
        if save_card and payment_method:
            wallet.stripe_payment_method_id = payment_method
            wallet.card_brand = brand
            wallet.card_last4 = last4
            # The owner asked for auto-recharge with this top-up; it could
            # only be switched on once there was a card to charge.
            if (
                _truthy(_get(metadata, "enable_auto"))
                and wallet.auto_recharge_threshold_cents
                and wallet.auto_recharge_amount_cents
            ):
                wallet.auto_recharge_enabled = True
                wallet.auto_recharge_attempted_at = None
    await db.commit()
    await run_followups(db, [result])
    return result


async def start_stripe_topup(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user: User,
    amount_cents: int,
    payment_method_id: str,
    save_card: bool,
    activate: bool,
    enable_auto_recharge: bool = False,
) -> Dict[str, Any]:
    """Charge a card for a top-up.

    Returns ``{"status": "succeeded", ...}`` once the wallet is credited,
    ``{"requires_action": True, "client_secret": ..., "payment_intent_id": ...}``
    when the bank wants the cardholder to approve it (3-D Secure) — finish with
    :func:`confirm_stripe_topup` — or ``{"status": "processing"}`` for a
    payment the bank has not settled yet (the webhook credits it).

    A declined card raises ``stripe.error.CardError``, which the app's Stripe
    error handler turns into a 402 with the bank's own wording.
    """
    await _configure_stripe()
    customer_id = await _stripe_customer(db, organization_id, user)

    params: Dict[str, Any] = {
        "amount": amount_cents,
        "currency": "usd",
        "customer": customer_id,
        "payment_method": payment_method_id,
        "payment_method_types": ["card"],
        "confirm": True,
        "description": f"{settings.APP_NAME} call credit",
        "expand": ["latest_charge"],
        "metadata": {
            "kind": TOPUP_KIND,
            "organization_id": str(organization_id),
            "user_id": str(user.id),
            "topup_id": uuid.uuid4().hex,
            "activate": "1" if activate else "0",
            "save_card": "1" if save_card else "0",
            "enable_auto": "1" if (save_card and enable_auto_recharge) else "0",
        },
        # A payment method id is minted per card entry, so a double click on
        # Pay reuses the first PaymentIntent instead of charging twice.
        "idempotency_key": f"wallet_topup:{organization_id}:{payment_method_id}:{amount_cents}",
    }
    if save_card:
        params["setup_future_usage"] = "off_session"

    intent = await asyncio.to_thread(lambda: stripe.PaymentIntent.create(**params))
    return await _stripe_intent_outcome(db, intent, user=user, organization_id=organization_id)


async def _stripe_intent_outcome(
    db: AsyncSession, intent: Any, *, user: User, organization_id: uuid.UUID
) -> Dict[str, Any]:
    intent_status = _get(intent, "status")
    if intent_status == "succeeded":
        result = await credit_stripe_intent(db, intent, actor=user)
        balance = (
            result.balance_cents
            if result is not None and result.credited
            else await wallet_service.balance_cents(db, organization_id)
        )
        return {
            "status": "succeeded",
            "balance": wallet_service.from_cents(balance),
            "activated": bool(result and result.activated_plan),
        }
    if intent_status == "requires_action" and _get(intent, "client_secret"):
        logger.info(f"Top-up for org {organization_id} needs cardholder authentication")
        return {
            "requires_action": True,
            "client_secret": _get(intent, "client_secret"),
            "payment_intent_id": _get(intent, "id"),
        }
    if intent_status == "processing":
        return {"status": "processing"}

    # Nothing was taken. Cancel so the intent cannot be completed later.
    try:
        await asyncio.to_thread(stripe.PaymentIntent.cancel, _get(intent, "id"))
    except Exception as exc:  # pragma: no cover - best effort cleanup
        logger.warning(f"Could not cancel unpaid top-up {_get(intent, 'id')}: {exc}")
    declined = _get(_get(intent, "last_payment_error") or {}, "message")
    if intent_status == "requires_payment_method" and not declined:
        reason = "your bank's verification was not completed"
    else:
        reason = (declined or "the payment could not be completed").rstrip(".")
    raise WalletError(NOT_CHARGED.format(reason=reason))


async def confirm_stripe_topup(
    db: AsyncSession, *, organization_id: uuid.UUID, user: User, payment_intent_id: str
) -> Optional[Dict[str, Any]]:
    """Second half of a top-up that needed 3-D Secure.

    Nothing the browser says is trusted: the PaymentIntent is re-read from
    Stripe and must be a top-up for this workspace. Returns ``None`` when it is
    not (the endpoint answers 404, never confirming that an id exists).
    """
    await _configure_stripe()
    try:
        intent = await asyncio.to_thread(
            stripe.PaymentIntent.retrieve, payment_intent_id, expand=["latest_charge"]
        )
    except stripe.error.InvalidRequestError:
        return None
    metadata = _get(intent, "metadata") or {}
    if not _is_topup_intent(intent) or _get(metadata, "organization_id") != str(organization_id):
        return None
    return await _stripe_intent_outcome(db, intent, user=user, organization_id=organization_id)


async def _topup_for_intent(db: AsyncSession, intent_id: Optional[str]) -> Optional[WalletTransaction]:
    if not intent_id:
        return None
    return await wallet_service.find_transaction(db, f"topup:stripe:{intent_id}")


async def apply_stripe_event(db: AsyncSession, event: Any) -> None:
    """Wallet effects of one Stripe webhook delivery. Idempotent.

    Run for every delivery, including one Stripe is retrying: the ledger's own
    idempotency keys make a repeat harmless, and that way a credit that failed
    half way the first time is completed by the retry. Raises on failure so
    the endpoint answers 500 and Stripe does retry.
    """
    event_type = _get(event, "type")
    data = _get(_get(event, "data") or {}, "object") or {}

    if event_type == "payment_intent.succeeded":
        await credit_stripe_intent(db, data)
        return

    if event_type == "charge.refunded":
        topup = await _topup_for_intent(db, _get(data, "payment_intent"))
        if topup is None:
            return  # a subscription invoice's refund, handled elsewhere
        movement = await _debit_refund(
            db,
            topup,
            refunded_total_cents=int(_get(data, "amount_refunded") or 0),
            reference_type=REF_STRIPE_CHARGE,
            reference_id=str(_get(data, "id")),
            actor_type=events.ACTOR_STRIPE,
        )
        await db.commit()
        await after_refund(db, movement)
        return

    if event_type in ("charge.dispute.created", "charge.dispute.funds_withdrawn"):
        topup = await _topup_for_intent(db, _get(data, "payment_intent"))
        if topup is None:
            return
        movement = await _debit_refund(
            db,
            topup,
            refunded_total_cents=int(_get(data, "amount") or 0),
            reference_type=REF_STRIPE_DISPUTE,
            reference_id=str(_get(data, "id")),
            actor_type=events.ACTOR_STRIPE,
            description="Top-up disputed with the card issuer",
        )
        if movement is not None:
            # A disputed card must not be charged again automatically.
            wallet = await wallet_service.get_wallet(db, topup.organization_id)
            wallet.auto_recharge_enabled = False
        await db.commit()
        await after_refund(db, movement)
        return

    if event_type == "charge.dispute.closed" and _get(data, "status") == "won":
        topup = await _topup_for_intent(db, _get(data, "payment_intent"))
        if topup is None:
            return
        dispute_id = str(_get(data, "id"))
        taken = await _refunded_so_far(db, REF_STRIPE_DISPUTE, dispute_id)
        if taken <= 0:
            return
        movement = await wallet_service.apply(
            db,
            topup.organization_id,
            amount_cents=taken,
            type=TXN_REFUND,
            idempotency_key=f"dispute_won:stripe:{dispute_id}",
            description="Dispute resolved in your favour, credit restored",
            # A different reference, so it is not netted against the debit above.
            reference_type=f"{REF_STRIPE_DISPUTE}_won",
            reference_id=dispute_id,
            actor_type=events.ACTOR_STRIPE,
        )
        await db.commit()
        if movement is not None:
            from app.services.billing.entitlements import invalidate_entitlements

            invalidate_entitlements(topup.organization_id)


async def after_refund(db: AsyncSession, movement: Optional[wallet_service.Movement]) -> None:
    if movement is None:
        return
    from app.services.billing.entitlements import invalidate_entitlements

    invalidate_entitlements(movement.organization_id)
    await wallet_notices.refund_applied(
        db,
        movement.organization_id,
        amount_cents=-movement.amount_cents,
        balance_cents=movement.balance_cents,
        currency=movement.currency,
    )


# ---------------------------------------------------------------------------
# Auto-recharge (Stripe only)
# ---------------------------------------------------------------------------


def auto_recharge_supported() -> bool:
    """Whether a saved card can be charged without the customer present."""
    return stripe_ready()


def schedule_auto_recharge(organization_id: uuid.UUID) -> None:
    """Start an automatic top-up in the background, if one is due.

    Fire-and-forget from the path that recorded a call: charging a card is a
    network call, and it must not hold up — or be able to fail — a carrier
    callback.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(_auto_recharge_task(organization_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def detach_card(payment_method_id: str) -> None:
    """Remove a saved card at Stripe. Best effort: it is already forgotten here."""
    try:
        await _configure_stripe()
        await asyncio.to_thread(stripe.PaymentMethod.detach, payment_method_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Could not detach saved card {payment_method_id}: {exc}")


async def _auto_recharge_task(organization_id: uuid.UUID) -> None:
    from app.database import get_db_session

    try:
        async with get_db_session() as db:
            await run_auto_recharge(db, organization_id)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Auto-recharge failed for org {organization_id}: {exc}", exc_info=True)


def _auto_recharge_due(wallet: Optional[Wallet], now: datetime) -> bool:
    if wallet is None or not wallet.auto_recharge_enabled:
        return False
    if not (wallet.stripe_payment_method_id and wallet.stripe_customer_id):
        return False
    if not wallet.auto_recharge_threshold_cents or not wallet.auto_recharge_amount_cents:
        return False
    if int(wallet.balance_cents or 0) >= int(wallet.auto_recharge_threshold_cents):
        return False
    if wallet.auto_recharge_attempted_at is not None:
        wait = AUTO_RECHARGE_RETRY_AFTER if wallet.auto_recharge_failures else AUTO_RECHARGE_COOLDOWN
        if now - wallet.auto_recharge_attempted_at < wait:
            return False
    return True


async def run_auto_recharge(
    db: AsyncSession, organization_id: uuid.UUID, *, now: Optional[datetime] = None
) -> Optional[CreditResult]:
    """Charge the saved card if the balance is under the owner's threshold.

    One at a time per wallet: the attempt is stamped on the wallet row under
    its lock and committed *before* Stripe is called, so a second trigger a
    moment later sees the stamp and stands down. The lock is not held while
    Stripe is being talked to.
    """
    now = now or datetime.utcnow()
    if not auto_recharge_supported():
        return None

    wallet = await wallet_service.get_wallet(db, organization_id, lock=True)
    if not _auto_recharge_due(wallet, now):
        await db.commit()  # nothing changed; this only lets go of the lock
        return None

    amount = int(wallet.auto_recharge_amount_cents)
    customer_id = wallet.stripe_customer_id
    payment_method_id = wallet.stripe_payment_method_id
    wallet_id = wallet.id
    wallet.auto_recharge_attempted_at = now
    await db.commit()

    await _configure_stripe()
    try:
        intent = await asyncio.to_thread(
            lambda: stripe.PaymentIntent.create(
                amount=amount,
                currency="usd",
                customer=customer_id,
                payment_method=payment_method_id,
                payment_method_types=["card"],
                confirm=True,
                off_session=True,
                description=f"{settings.APP_NAME} call credit (auto-recharge)",
                metadata={
                    "kind": TOPUP_KIND,
                    "organization_id": str(organization_id),
                    "topup_id": uuid.uuid4().hex,
                    "automatic": "1",
                    "activate": "0",
                    "save_card": "0",
                },
                idempotency_key=f"wallet_auto:{wallet_id}:{int(now.timestamp())}",
            )
        )
    except stripe.error.CardError as exc:
        # Declined, expired, or the bank wants the cardholder present.
        logger.warning(
            f"Auto-recharge declined for org {organization_id}: code={getattr(exc, 'code', None)}"
        )
        await _auto_recharge_failed(db, organization_id)
        return None
    except stripe.error.StripeError as exc:
        # Ours or Stripe's problem, not the card's: try again after the cooldown.
        logger.error(f"Auto-recharge could not reach Stripe for org {organization_id}: {exc}")
        return None

    if _get(intent, "status") == "succeeded":
        return await credit_stripe_intent(db, intent)
    if _get(intent, "status") == "processing":
        return None  # the webhook credits it
    try:
        await asyncio.to_thread(stripe.PaymentIntent.cancel, _get(intent, "id"))
    except Exception:  # pragma: no cover - best effort cleanup
        pass
    await _auto_recharge_failed(db, organization_id)
    return None


async def _auto_recharge_failed(db: AsyncSession, organization_id: uuid.UUID) -> None:
    wallet = await wallet_service.get_wallet(db, organization_id, lock=True)
    if wallet is None:
        await db.commit()
        return
    wallet.auto_recharge_failures = int(wallet.auto_recharge_failures or 0) + 1
    switched_off = wallet.auto_recharge_failures >= AUTO_RECHARGE_MAX_FAILURES
    if switched_off:
        wallet.auto_recharge_enabled = False
    await db.commit()
    await wallet_notices.auto_recharge_failed(db, organization_id, switched_off=switched_off)


async def sweep_auto_recharges(db: AsyncSession, *, now: Optional[datetime] = None, limit: int = 25) -> int:
    """Retry automatic top-ups that are still due. Run by the reconciler.

    Covers a trigger that was lost (a restart between the call ending and the
    charge) and the daily retry after a decline. Returns how many were topped up.
    """
    now = now or datetime.utcnow()
    if not auto_recharge_supported():
        return 0
    rows = (
        await db.execute(
            select(Wallet.organization_id)
            .where(
                Wallet.auto_recharge_enabled.is_(True),
                Wallet.stripe_payment_method_id.is_not(None),
                Wallet.auto_recharge_threshold_cents.is_not(None),
                Wallet.balance_cents < Wallet.auto_recharge_threshold_cents,
            )
            .limit(limit)
        )
    ).scalars().all()
    topped_up = 0
    for organization_id in rows:
        try:
            result = await run_auto_recharge(db, organization_id, now=now)
            if result is not None and result.credited:
                topped_up += 1
        except Exception as exc:  # noqa: BLE001 — one wallet must not stop the sweep
            await db.rollback()
            logger.error(f"Auto-recharge sweep failed for org {organization_id}: {exc}")
    return topped_up


# ---------------------------------------------------------------------------
# Polar
# ---------------------------------------------------------------------------


def polar_ready(plan) -> bool:
    """Can a top-up be sold through Polar right now?"""
    return (
        providers.active_provider() == providers.POLAR
        and providers.is_ready(providers.POLAR)
        and bool(getattr(plan, "polar_product_id", None))
    )


def _frontend_url(path: str) -> str:
    return f"{(settings.FRONTEND_URL or '').rstrip('/')}{path}"


async def start_polar_topup(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user: User,
    amount_cents: int,
    activate: bool,
    return_path: str,
    cancel_path: str,
) -> Dict[str, str]:
    """Create a Polar checkout for a top-up and return where to send the customer.

    The amount is fixed for this checkout as an ad-hoc price on the credit
    product, so it cannot be changed on Polar's page. Nothing is credited
    here: Polar's ``order.paid`` webhook does that.
    """
    from app.services.billing import polar_service

    plan = await wallet_service.prepaid_plan(db)
    if plan is None or not plan.polar_product_id:
        raise WalletError(NOT_AVAILABLE)
    product_id = plan.polar_product_id

    # {CHECKOUT_ID} is filled in by Polar, so it must reach Polar unencoded.
    success_url = (
        _frontend_url("/billing/return")
        + "?checkout_id={CHECKOUT_ID}&kind=topup&next="
        + quote(return_path, safe="")
    )
    body: Dict[str, Any] = {
        "products": [product_id],
        "prices": {
            product_id: [
                {
                    "amount_type": "fixed",
                    "price_amount": amount_cents,
                    "price_currency": (plan.currency or "usd").lower(),
                }
            ]
        },
        "external_customer_id": str(organization_id),
        "customer_email": user.email,
        "success_url": success_url,
        "return_url": _frontend_url(cancel_path),
        "allow_discount_codes": False,
        "metadata": {
            "kind": TOPUP_KIND,
            "organization_id": str(organization_id),
            "user_id": str(user.id),
            "topup_id": uuid.uuid4().hex,
            "amount_cents": amount_cents,
            "activate": "1" if activate else "0",
        },
    }
    if user.full_name:
        body["customer_name"] = user.full_name[:256]

    checkout = await polar_service.get_polar_client().create_checkout(body)
    if not checkout.get("url") or not checkout.get("id"):
        raise WalletError("The payment provider did not return a checkout link. Please try again.")
    return {"url": checkout["url"], "checkout_id": checkout["id"]}


def is_polar_topup(order: Mapping[str, Any]) -> bool:
    return (order.get("metadata") or {}).get("kind") == TOPUP_KIND


def _polar_net_cents(order: Mapping[str, Any]) -> int:
    """What the customer paid for credit: after discounts, before sales tax.

    Polar adds tax on top as Merchant of Record; tax is not credit.
    """
    net = order.get("net_amount")
    if net is None:
        if order.get("subtotal_amount") is not None:
            net = int(order.get("subtotal_amount") or 0) - int(order.get("discount_amount") or 0)
        else:
            net = int(order.get("total_amount") or 0) - int(order.get("tax_amount") or 0)
    return max(0, int(net or 0))


async def credit_polar_order(
    db: AsyncSession, order: Mapping[str, Any], *, event_key: Optional[str] = None
) -> Optional[CreditResult]:
    """Credit a paid Polar top-up order. Staged on ``db``; the webhook commits.

    Returns ``None`` when the order is not a wallet top-up for a known
    organization.
    """
    if not is_polar_topup(order) or not order.get("id"):
        return None
    metadata = order.get("metadata") or {}
    customer = order.get("customer") or {}
    organization_id = _as_uuid(metadata.get("organization_id")) or _as_uuid(customer.get("external_id"))
    if organization_id is None or await db.get(Organization, organization_id) is None:
        logger.error("Polar top-up order %s names no known organization", order.get("id"))
        return None

    amount = _polar_net_cents(order)
    if amount <= 0:
        return None
    plan = await wallet_service.prepaid_plan(db, include_inactive=True)
    if plan is not None and plan.polar_product_id and order.get("product_id") not in (None, plan.polar_product_id):
        # Still credited: the order is signed, paid and marked as a top-up by
        # the checkout this app created. Worth a look, though.
        logger.warning(
            "Polar top-up order %s is for product %s, not the credit product %s",
            order.get("id"), order.get("product_id"), plan.polar_product_id,
        )

    return await _credit(
        db,
        organization_id,
        amount_cents=amount,
        idempotency_key=f"topup:polar:{order['id']}",
        reference_type=REF_POLAR_ORDER,
        reference_id=str(order["id"]),
        client_ref=str(metadata.get("topup_id") or "") or None,
        actor_type=events.ACTOR_POLAR,
        actor_id=_as_uuid(metadata.get("user_id")),
        activate=_truthy(metadata.get("activate")),
        automatic=False,
        details={
            "provider": "polar",
            "checkout_id": order.get("checkout_id"),
            "tax_cents": int(order.get("tax_amount") or 0),
        },
        event_key=event_key,
    )


async def refund_polar_order(db: AsyncSession, order: Mapping[str, Any]) -> Optional[wallet_service.Movement]:
    """Take a refunded Polar top-up back out. Staged on ``db``; the webhook commits."""
    if not order.get("id"):
        return None
    topup = await wallet_service.find_transaction(db, f"topup:polar:{order['id']}")
    if topup is None:
        return None
    if order.get("status") == "refunded":
        refunded = int(topup.amount_cents)
    else:
        # Excludes tax, which Polar reports separately as refunded_tax_amount.
        refunded = int(order.get("refunded_amount") or 0)
    return await _debit_refund(
        db,
        topup,
        refunded_total_cents=refunded,
        reference_type=REF_POLAR_ORDER,
        reference_id=str(order["id"]),
        actor_type=events.ACTOR_POLAR,
    )


async def polar_topup_status(db: AsyncSession, *, organization_id: uuid.UUID, checkout_id: str) -> Optional[str]:
    """Where a hosted top-up has got to, for the return page.

    ``active`` once the credit is in the wallet, ``pending`` while the payment
    is made but the webhook has not landed, otherwise Polar's own
    ``open`` / ``failed`` / ``expired``. ``None`` when the checkout is not this
    workspace's top-up.
    """
    from app.services.billing import polar_service

    try:
        checkout = await polar_service.get_polar_client().get_checkout(checkout_id)
    except polar_service.PolarError as exc:
        if exc.status_code == 404:
            return None
        raise
    metadata = checkout.get("metadata") or {}
    if metadata.get("kind") != TOPUP_KIND or str(metadata.get("organization_id")) != str(organization_id):
        return None

    topup_id = str(metadata.get("topup_id") or "")
    if topup_id:
        landed = (
            await db.execute(
                select(WalletTransaction.id)
                .where(
                    WalletTransaction.organization_id == organization_id,
                    WalletTransaction.client_ref == topup_id,
                    WalletTransaction.type == TXN_TOPUP,
                )
                .limit(1)
            )
        ).first()
        if landed is not None:
            return "active"

    polar_status = checkout.get("status")
    if polar_status in ("failed", "expired", "open"):
        return polar_status
    return "pending"


async def sync_polar_credit_product(plan) -> str:
    """Create (or refresh) the one-time Polar product top-ups are sold as.

    Its catalogue price is "pay what you want" from the plan's minimum top-up;
    each checkout pins the exact amount with an ad-hoc price. Returns the
    product id; the caller stores it on the plan and commits.
    """
    from app.services.billing import polar_service

    client = polar_service.get_polar_client()
    minimum, maximum = topup_bounds(catalog.billing_config(wallet_service.plan_document(plan)))
    name = f"{settings.APP_NAME} call credit"[:64]
    description = "Prepaid credit for call minutes on the Pay As You Go plan."
    price = {
        "amount_type": "custom",
        "price_currency": (plan.currency or "usd").lower(),
        "minimum_amount": minimum,
        "maximum_amount": maximum,
        "preset_amount": minimum,
    }
    if plan.polar_product_id:
        await client.update_product(
            plan.polar_product_id, {"name": name, "description": description, "prices": [price]}
        )
        return plan.polar_product_id
    created = await client.create_product(
        {
            "name": name,
            "description": description,
            "recurring_interval": None,
            "prices": [price],
            "metadata": {"voicecon_plan": plan.slug or str(plan.id), "kind": TOPUP_KIND},
        }
    )
    return created["id"]


# ---------------------------------------------------------------------------
# Staff adjustments
# ---------------------------------------------------------------------------


async def adjust(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    amount_cents: int,
    reason: str,
    admin: User,
) -> wallet_service.Movement:
    """Add or remove credit by hand. Staged on ``db``; the caller commits.

    Always with a reason, and always as a ledger row of its own — a balance is
    never edited in place.
    """
    reason = (reason or "").strip()
    if not reason:
        raise WalletError("Say why the balance is being changed.")
    if not amount_cents:
        raise WalletError("Enter an amount other than zero.")
    movement = await wallet_service.apply(
        db,
        organization_id,
        amount_cents=amount_cents,
        type=wallet_service.TXN_ADJUSTMENT,
        idempotency_key=None,
        description="Credit added by support" if amount_cents > 0 else "Credit removed by support",
        actor_type=events.ACTOR_ADMIN,
        actor_id=admin.id,
        details={"reason": reason[:500], "admin_email": admin.email},
    )
    if movement is None:  # pragma: no cover - only for a zero amount, refused above
        raise WalletError("The balance could not be changed. Please try again.")
    return movement
