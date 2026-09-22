"""
Polar (https://polar.sh) as a payment provider.

Polar is a Merchant of Record: it hosts the checkout page, charges the card,
handles sales tax and pays out. This app never sees card data and never holds a
Stripe key when Polar is the active provider. What it does hold is a Polar
organization access token, limited to the scopes billing needs, and the webhook
signing secret.

The flow:

1. ``POST /billing/checkout-session`` creates a Polar checkout with
   ``external_customer_id = <organization id>`` and the org/plan in
   ``metadata``, and the browser is sent to Polar's hosted page.
2. Polar calls ``POST /billing/webhooks/polar``. ``subscription.*`` events keep
   the local :class:`Subscription` row in step; ``order.paid`` records the
   invoice and, on a renewal, starts the new usage period.
3. Plan changes, cancellation and reactivation call the Polar API directly;
   the webhooks that follow are applied idempotently on top.

Uses the REST API over ``httpx`` rather than the SDK: a handful of calls, and
no new dependency in the image.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple

import httpx
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UserFacingError
from app.models.subscription import (
    LIVE_STATUSES,
    SOURCE_POLAR,
    SOURCE_STRIPE,
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_PAST_DUE,
    Invoice,
    PaymentFailure,
    ProcessedStripeEvent,
    Subscription,
    SubscriptionPlan,
    TrialGrant,
)
from app.models.user import Organization, User

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 20.0
#: Standard Webhooks tolerance for the signed timestamp.
WEBHOOK_TOLERANCE_SECONDS = 5 * 60


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------


class PolarError(UserFacingError):
    """A Polar API call failed. ``public_message`` is safe to show a customer."""

    def __init__(self, message: str, *, status_code: Optional[int] = None, detail: str = ""):
        super().__init__(message)
        self.status_code = status_code
        #: Polar's own explanation. For logs and the admin console only — never
        #: shown to customers (see ``UserFacingError``).
        self.detail = detail


class PolarNotConfigured(PolarError):
    pass


class PolarClient:
    def __init__(self, token: str, base_url: str):
        self._token = token
        self._base = base_url.rstrip("/")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> Dict[str, Any]:
        url = f"{self._base}{path}"
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.request(
                    method,
                    url,
                    json=json_body,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Accept": "application/json",
                    },
                )
        except httpx.HTTPError as exc:
            logger.warning("Polar %s %s failed to connect: %s", method, path, exc)
            raise PolarError("The payment provider could not be reached. Please try again.")

        if response.status_code < 300:
            if not response.content:
                return {}
            return response.json()

        detail = _error_detail(response)
        logger.warning("Polar %s %s -> HTTP %s: %s", method, path, response.status_code, detail)
        if response.status_code in (401, 403):
            raise PolarError(
                "The payment provider rejected this server's credentials. An administrator needs to check the Polar settings.",
                status_code=response.status_code,
                detail=detail,
            )
        if response.status_code == 404:
            raise PolarError("The payment provider has no record of this item.", status_code=404, detail=detail)
        raise PolarError(
            "The payment provider refused the request. Please try again or contact support.",
            status_code=response.status_code,
            detail=detail,
        )

    # -- checkouts --
    async def create_checkout(self, body: dict) -> dict:
        return await self._request("POST", "/v1/checkouts/", json_body=body)

    async def get_checkout(self, checkout_id: str) -> dict:
        return await self._request("GET", f"/v1/checkouts/{checkout_id}")

    # -- subscriptions --
    async def get_subscription(self, subscription_id: str) -> dict:
        return await self._request("GET", f"/v1/subscriptions/{subscription_id}")

    async def update_subscription(self, subscription_id: str, body: dict) -> dict:
        return await self._request("PATCH", f"/v1/subscriptions/{subscription_id}", json_body=body)

    async def revoke_subscription(self, subscription_id: str) -> dict:
        return await self._request("DELETE", f"/v1/subscriptions/{subscription_id}")

    # -- customer portal --
    async def create_customer_session(self, body: dict) -> dict:
        return await self._request("POST", "/v1/customer-sessions/", json_body=body)

    # -- products --
    async def create_product(self, body: dict) -> dict:
        return await self._request("POST", "/v1/products/", json_body=body)

    async def update_product(self, product_id: str, body: dict) -> dict:
        return await self._request("PATCH", f"/v1/products/{product_id}", json_body=body)

    async def get_product(self, product_id: str) -> dict:
        return await self._request("GET", f"/v1/products/{product_id}")


def _error_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return ""
    detail = data.get("detail") if isinstance(data, dict) else None
    if isinstance(detail, list):
        # FastAPI-style validation errors: [{"loc": [...], "msg": "..."}]
        return "; ".join(str(d.get("msg", d)) for d in detail[:3] if isinstance(d, dict))
    return str(detail or data.get("error") or "")[:300] if isinstance(data, dict) else ""


def get_polar_client() -> PolarClient:
    """A client built from the current settings, so a rotated token applies at once."""
    if not settings.polar_configured:
        raise PolarNotConfigured("Polar payments are not configured on this server.")
    return PolarClient(settings.POLAR_ACCESS_TOKEN, settings.polar_api_base)


def product_for(plan: SubscriptionPlan, billing_period: str) -> Optional[str]:
    return plan.polar_product_id_yearly if billing_period == "yearly" else plan.polar_product_id


# ---------------------------------------------------------------------------
# Webhook signatures
# ---------------------------------------------------------------------------


class WebhookVerificationError(Exception):
    pass


def _signing_keys(secret: str) -> List[bytes]:
    """Keys a delivery may have been signed with.

    Polar secrets created from 2026-09-08 follow Standard Webhooks (the part
    after ``whsec_`` is base64 key material). Older secrets use Polar's own
    scheme, keyed on the UTF-8 bytes of the whole ``whsec_…`` string. Trying
    both means neither generation of secret needs configuring differently.
    """
    keys: List[bytes] = []
    material = secret[len("whsec_"):] if secret.startswith("whsec_") else secret
    try:
        keys.append(base64.b64decode(material, validate=True))
    except (ValueError, TypeError):
        pass
    keys.append(secret.encode("utf-8"))
    return keys


def verify_webhook(body: bytes, headers: Mapping[str, str]) -> dict:
    secret = settings.POLAR_WEBHOOK_SECRET
    if not secret:
        raise WebhookVerificationError("Polar webhook secret is not configured")

    msg_id = headers.get("webhook-id")
    timestamp = headers.get("webhook-timestamp")
    signature_header = headers.get("webhook-signature")
    if not (msg_id and timestamp and signature_header):
        raise WebhookVerificationError("Missing webhook signature headers")

    try:
        sent_at = int(timestamp)
    except ValueError:
        raise WebhookVerificationError("Invalid webhook timestamp")
    if abs(time.time() - sent_at) > WEBHOOK_TOLERANCE_SECONDS:
        raise WebhookVerificationError("Webhook timestamp outside the tolerance window")

    signed = f"{msg_id}.{timestamp}.".encode() + body
    presented = [
        part.split(",", 1)[1]
        for part in signature_header.split()
        if part.startswith("v1,") and "," in part
    ]
    for key in _signing_keys(secret):
        expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
        if any(hmac.compare_digest(expected, sig) for sig in presented):
            try:
                return json.loads(body)
            except ValueError:
                raise WebhookVerificationError("Webhook body is not JSON")
    raise WebhookVerificationError("No matching webhook signature")


# ---------------------------------------------------------------------------
# Webhook effects
# ---------------------------------------------------------------------------


@dataclass
class WebhookOutcome:
    """Side effects to run only once the transaction has committed."""

    invalidate: set = field(default_factory=set)
    #: (email, plan name) confirmations to send.
    confirmations: List[Tuple[str, str]] = field(default_factory=list)


def _utcnow() -> datetime:
    return datetime.utcnow()


def parse_dt(value: Any) -> Optional[datetime]:
    """Polar sends ISO 8601 with an offset; the database stores naive UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _as_uuid(value: Any) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


async def plan_for_product(
    db: AsyncSession, product_id: Optional[str]
) -> Tuple[Optional[SubscriptionPlan], Optional[str]]:
    """The plan and billing period a Polar product id belongs to."""
    if not product_id:
        return None, None
    result = await db.execute(
        select(SubscriptionPlan).where(
            or_(
                SubscriptionPlan.polar_product_id == product_id,
                SubscriptionPlan.polar_product_id_yearly == product_id,
            )
        )
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        return None, None
    return plan, "yearly" if plan.polar_product_id_yearly == product_id else "monthly"


async def _subscription_by_polar_id(db: AsyncSession, polar_id: Optional[str]) -> Optional[Subscription]:
    if not polar_id:
        return None
    result = await db.execute(select(Subscription).where(Subscription.polar_subscription_id == polar_id))
    return result.scalar_one_or_none()


def _local_status(polar_status: str) -> Optional[str]:
    if polar_status in ("active", "trialing"):
        return STATUS_ACTIVE
    if polar_status in ("past_due", "unpaid"):
        return STATUS_PAST_DUE
    if polar_status in ("canceled", "incomplete_expired"):
        return STATUS_CANCELED
    # incomplete / paused: nothing we act on.
    return None


async def handle_webhook_event(db: AsyncSession, event_id: str, payload: dict) -> WebhookOutcome:
    """Apply one verified Polar delivery. Idempotent by webhook id.

    The idempotency claim is written in the same transaction as the effect, so
    a delivery that fails half way is rolled back entirely and Polar's retry
    applies it from scratch. The caller commits nothing; this function does.
    """
    outcome = WebhookOutcome()
    event_type = str(payload.get("type") or "")
    data = payload.get("data") or {}
    claim_key = f"polar:{event_id}"

    if await db.get(ProcessedStripeEvent, claim_key) is not None:
        logger.info("Skipping already-processed Polar event %s", event_id)
        return outcome
    db.add(ProcessedStripeEvent(stripe_event_id=claim_key, event_type=event_type[:100]))

    if event_type.startswith("subscription."):
        await sync_subscription(db, data, outcome, event_type=event_type, event_key=claim_key)
    elif event_type == "order.paid":
        await _on_order_paid(db, data, outcome, event_key=claim_key)
    elif event_type == "order.refunded":
        await _on_order_refunded(db, data)
    else:
        logger.debug("Ignoring Polar event %s", event_type)

    try:
        await db.commit()
    except IntegrityError:
        # Two workers raced on the same delivery; the other one applied it.
        await db.rollback()
        return WebhookOutcome()
    return outcome


async def sync_subscription(
    db: AsyncSession,
    data: dict,
    outcome: WebhookOutcome,
    *,
    event_type: str = "subscription.updated",
    event_key: Optional[str] = None,
) -> Optional[Subscription]:
    """Bring the local row in line with a Polar subscription object.

    The first time an active Polar subscription is seen for an organization it
    is linked to that organization's row — converting a running trial in place,
    exactly as the Stripe checkout does. After that, status, period, plan and
    the cancellation flag follow Polar.
    """
    from app.services.billing import events

    polar_id = data.get("id")
    polar_status = str(data.get("status") or "")
    local = await _subscription_by_polar_id(db, polar_id)
    plan, period = await plan_for_product(db, data.get("product_id"))

    if local is None:
        if _local_status(polar_status) not in (STATUS_ACTIVE, STATUS_PAST_DUE):
            return None  # incomplete or already over; nothing to link
        return await _link_new_subscription(db, data, plan, period, outcome, event_key=event_key)

    previous_status = local.status
    new_status = _local_status(polar_status)
    now = _utcnow()

    period_start = parse_dt(data.get("current_period_start"))
    period_end = parse_dt(data.get("current_period_end"))
    if period_start:
        local.current_period_start = period_start
    if period_end:
        local.current_period_end = period_end

    local.cancel_at_period_end = bool(data.get("cancel_at_period_end"))
    if local.cancel_at_period_end:
        local.canceled_at = local.canceled_at or parse_dt(data.get("canceled_at")) or now
    elif new_status != STATUS_CANCELED:
        local.canceled_at = None

    if new_status == STATUS_ACTIVE:
        local.status = STATUS_ACTIVE
        local.grace_period_end = None
        local.expired_at = None
    elif new_status == STATUS_PAST_DUE:
        from app.services.billing.entitlements import PAYMENT_GRACE_DAYS

        local.status = STATUS_PAST_DUE
        if local.grace_period_end is None:
            local.grace_period_end = now + timedelta(days=PAYMENT_GRACE_DAYS)
    elif new_status == STATUS_CANCELED:
        ended = parse_dt(data.get("ended_at")) or now
        local.status = STATUS_CANCELED
        local.canceled_at = local.canceled_at or parse_dt(data.get("canceled_at")) or ended
        local.ended_at = ended
        # Revoked: access ends when Polar ended it, not at a period end that
        # may still be in the future.
        local.current_period_end = min(local.current_period_end, ended)
        local.cancel_at_period_end = False

    if plan is not None and plan.id != local.plan_id:
        previous_plan = local.plan_id
        local.plan_id = plan.id
        local.billing_period = period or local.billing_period
        if local.scheduled_plan_id == plan.id:
            local.scheduled_plan_id = None
        await events.record_event(
            db,
            organization_id=local.organization_id,
            event_type=events.PLAN_CHANGED,
            subscription=local,
            from_plan_id=previous_plan,
            to_plan_id=plan.id,
            actor_type=events.ACTOR_POLAR,
            stripe_event_id=event_key,
        )

    if previous_status != local.status:
        event_name = {
            STATUS_ACTIVE: events.ACTIVATED,
            STATUS_PAST_DUE: events.PAST_DUE,
            STATUS_CANCELED: events.CANCELED,
        }.get(local.status, events.PAST_DUE)
        await events.record_event(
            db,
            organization_id=local.organization_id,
            event_type=event_name,
            subscription=local,
            from_status=previous_status,
            to_status=local.status,
            actor_type=events.ACTOR_POLAR,
            stripe_event_id=event_key,
            payload={"polar_event": event_type},
        )
        if local.status == STATUS_PAST_DUE:
            await _record_payment_failure(db, local)

    outcome.invalidate.add(local.organization_id)
    return local


async def _link_new_subscription(
    db: AsyncSession,
    data: dict,
    plan: Optional[SubscriptionPlan],
    period: Optional[str],
    outcome: WebhookOutcome,
    *,
    event_key: Optional[str],
) -> Optional[Subscription]:
    from app.services.billing import events
    from app.services.billing.conversion import apply_paid_conversion, mark_onboarding_done

    metadata = data.get("metadata") or {}
    customer = data.get("customer") or {}
    org_id = _as_uuid(metadata.get("organization_id")) or _as_uuid(customer.get("external_id"))
    if org_id is None or await db.get(Organization, org_id) is None:
        logger.error("Polar subscription %s has no known organization (metadata=%s)", data.get("id"), metadata)
        return None

    if plan is None:
        # A product not mapped in the admin console; fall back to the plan the
        # checkout was created for.
        plan_id = _as_uuid(metadata.get("plan_id"))
        plan = await db.get(SubscriptionPlan, plan_id) if plan_id else None
        period = str(metadata.get("billing_period") or "monthly")
    if plan is None:
        logger.error(
            "Polar subscription %s uses product %s, which no plan is mapped to. "
            "Set the Polar product on the plan in the admin console.",
            data.get("id"),
            data.get("product_id"),
        )
        return None

    from app.services.billing.entitlements import get_entitlement_service

    existing = await get_entitlement_service().live_subscription(db, org_id)
    if existing is not None and existing.source in (SOURCE_STRIPE, SOURCE_POLAR) and existing.status == STATUS_ACTIVE:
        # Already paying through a provider. Linking would silently orphan the
        # other subscription, so leave it for a human to sort out in Polar.
        logger.error(
            "Org %s already has an active %s subscription %s; not linking Polar subscription %s. "
            "Refund or revoke the duplicate in Polar.",
            org_id,
            existing.source,
            existing.id,
            data.get("id"),
        )
        return None
    if existing is None:
        result = await db.execute(
            select(Subscription)
            .where(Subscription.organization_id == org_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()

    now = _utcnow()
    status = _local_status(str(data.get("status") or "")) or STATUS_ACTIVE
    period_start = parse_dt(data.get("current_period_start")) or now
    period_end = parse_dt(data.get("current_period_end")) or (
        now + timedelta(days=365 if period == "yearly" else 30)
    )

    if existing is not None:
        previous_status = existing.status
        converting_trial = apply_paid_conversion(
            existing,
            plan,
            stripe_status=status,
            billing_period=period or "monthly",
            period_start=period_start,
            period_end=period_end,
            now=now,
            source=SOURCE_POLAR,
            polar_subscription_id=data.get("id"),
            polar_customer_id=data.get("customer_id"),
        )
        subscription = existing
        await events.record_event(
            db,
            organization_id=org_id,
            event_type=events.TRIAL_CONVERTED if converting_trial else events.ACTIVATED,
            subscription=subscription,
            from_status=previous_status,
            to_status=subscription.status,
            to_plan_id=plan.id,
            actor_type=events.ACTOR_POLAR,
            stripe_event_id=event_key,
        )
        if converting_trial:
            grants = await db.execute(select(TrialGrant).where(TrialGrant.organization_id == org_id))
            for grant in grants.scalars().all():
                grant.converted = True
    else:
        subscription = Subscription(
            organization_id=org_id,
            plan_id=plan.id,
            polar_subscription_id=data.get("id"),
            polar_customer_id=data.get("customer_id"),
            status=status,
            source=SOURCE_POLAR,
            billing_period=period or "monthly",
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db.add(subscription)
        await db.flush()
        await events.record_event(
            db,
            organization_id=org_id,
            event_type=events.ACTIVATED,
            subscription=subscription,
            to_status=subscription.status,
            to_plan_id=plan.id,
            actor_type=events.ACTOR_POLAR,
            stripe_event_id=event_key,
        )

    subscription.cancel_at_period_end = bool(data.get("cancel_at_period_end"))
    await mark_onboarding_done(db, org_id)
    await db.flush()

    email = None
    user_id = _as_uuid(metadata.get("user_id"))
    if user_id:
        user = await db.get(User, user_id)
        email = user.email if user else None
    email = email or customer.get("email")
    if email:
        outcome.confirmations.append((email, plan.name))
    outcome.invalidate.add(org_id)
    logger.info("Linked Polar subscription %s to org %s on plan %s", data.get("id"), org_id, plan.slug)
    return subscription


async def _record_payment_failure(db: AsyncSession, subscription: Subscription) -> None:
    """Put a failed Polar renewal in the admin payment-failure queue.

    Polar reports the failure on the subscription, not on an order, so it is
    attached to the subscription's latest invoice. With no invoice yet there is
    nothing to attach it to; the ``past_due`` event in the ledger still records it.
    """
    result = await db.execute(
        select(Invoice)
        .where(Invoice.subscription_id == subscription.id)
        .order_by(Invoice.created_at.desc())
        .limit(1)
    )
    invoice = result.scalar_one_or_none()
    if invoice is None:
        return
    db.add(
        PaymentFailure(
            invoice_id=invoice.id,
            organization_id=subscription.organization_id,
            failure_code="polar_past_due",
            failure_message="Polar could not collect the renewal payment and is retrying.",
        )
    )


async def _on_order_paid(db: AsyncSession, data: dict, outcome: WebhookOutcome, *, event_key: str) -> None:
    from app.services.billing import events

    polar_subscription_id = data.get("subscription_id")
    if not polar_subscription_id:
        return  # a one-off purchase; nothing this app sells

    local = await _subscription_by_polar_id(db, polar_subscription_id)
    if local is None:
        # order.paid can arrive before subscription.active. Fetch the
        # subscription and link it now rather than dropping the invoice.
        try:
            remote = await get_polar_client().get_subscription(polar_subscription_id)
        except PolarError as exc:
            # Transient: fail the delivery so Polar retries it.
            raise RuntimeError(f"Could not fetch Polar subscription {polar_subscription_id}: {exc}")
        local = await sync_subscription(db, remote, outcome, event_type="order.paid", event_key=event_key)
        if local is None:
            logger.error("Polar order %s paid for an unlinkable subscription %s", data.get("id"), polar_subscription_id)
            return

    await _upsert_invoice(db, local, data)

    nested = data.get("subscription") or {}
    period_start = parse_dt(nested.get("current_period_start"))
    period_end = parse_dt(nested.get("current_period_end"))
    previous_status = local.status

    if data.get("billing_reason") == "subscription_cycle":
        # A renewal starts a new billing period: roll the usage counters here,
        # on the payment, exactly as Stripe's invoice.paid does.
        local.status = STATUS_ACTIVE
        local.grace_period_end = None
        local.expired_at = None
        local.current_period_minutes = 0
        local.current_period_calls = 0
        local.current_period_sms = 0
        local.current_period_emails = 0
        if period_start:
            local.current_period_start = period_start
        if period_end:
            local.current_period_end = period_end
        await events.record_event(
            db,
            organization_id=local.organization_id,
            event_type=events.RENEWED,
            subscription=local,
            from_status=previous_status,
            to_status=local.status,
            actor_type=events.ACTOR_POLAR,
            stripe_event_id=event_key,
        )
    elif local.status == STATUS_PAST_DUE:
        local.status = STATUS_ACTIVE
        local.grace_period_end = None
        await events.record_event(
            db,
            organization_id=local.organization_id,
            event_type=events.ACTIVATED,
            subscription=local,
            from_status=previous_status,
            to_status=local.status,
            actor_type=events.ACTOR_POLAR,
            stripe_event_id=event_key,
        )
    outcome.invalidate.add(local.organization_id)


def _money(cents: Any) -> float:
    try:
        return round(int(cents or 0) / 100, 2)
    except (TypeError, ValueError):
        return 0.0


async def _upsert_invoice(db: AsyncSession, subscription: Subscription, order: dict) -> Invoice:
    result = await db.execute(select(Invoice).where(Invoice.polar_order_id == order.get("id")))
    invoice = result.scalar_one_or_none()
    total = _money(order.get("total_amount"))
    if invoice is None:
        invoice = Invoice(
            subscription_id=subscription.id,
            organization_id=subscription.organization_id,
            provider=SOURCE_POLAR,
            polar_order_id=order.get("id"),
            status="paid",
            amount_due=total,
            amount_remaining=0,
            subtotal=_money(order.get("subtotal_amount")),
            total=total,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
        )
        db.add(invoice)
    invoice.invoice_number = order.get("invoice_number") or invoice.invoice_number
    invoice.status = "paid"
    invoice.amount_paid = total
    invoice.tax = _money(order.get("tax_amount"))
    invoice.currency = (order.get("currency") or "usd")[:3]
    invoice.paid_at = parse_dt(order.get("created_at")) or _utcnow()
    invoice.line_items = {"billing_reason": order.get("billing_reason"), "product_id": order.get("product_id")}
    await db.flush()
    return invoice


async def _on_order_refunded(db: AsyncSession, data: dict) -> None:
    result = await db.execute(select(Invoice).where(Invoice.polar_order_id == data.get("id")))
    invoice = result.scalar_one_or_none()
    if invoice is None:
        return
    invoice.status = str(data.get("status") or "refunded")[:50]


# ---------------------------------------------------------------------------
# Outbound actions used by the billing endpoints
# ---------------------------------------------------------------------------


async def cancel(subscription: Subscription, *, immediate: bool) -> None:
    client = get_polar_client()
    if immediate:
        await client.revoke_subscription(subscription.polar_subscription_id)
    else:
        await client.update_subscription(subscription.polar_subscription_id, {"cancel_at_period_end": True})


async def reactivate(subscription: Subscription) -> None:
    await get_polar_client().update_subscription(
        subscription.polar_subscription_id, {"cancel_at_period_end": False}
    )


async def change_product(subscription: Subscription, product_id: str, *, immediately: bool) -> dict:
    """Upgrades prorate now; downgrades wait for the next period, as locally."""
    return await get_polar_client().update_subscription(
        subscription.polar_subscription_id,
        {"product_id": product_id, "proration_behavior": "prorate" if immediately else "next_period"},
    )


async def portal_url(subscription: Subscription, return_url: Optional[str]) -> str:
    body: Dict[str, Any] = {}
    if subscription.polar_customer_id:
        body["customer_id"] = subscription.polar_customer_id
    else:
        body["external_customer_id"] = str(subscription.organization_id)
    if return_url:
        body["return_url"] = return_url
    session = await get_polar_client().create_customer_session(body)
    url = session.get("customer_portal_url")
    if not url:
        raise PolarError("The payment provider did not return a billing portal link.")
    return url


def is_live_polar(subscription: Optional[Subscription]) -> bool:
    return (
        subscription is not None
        and subscription.source == SOURCE_POLAR
        and bool(subscription.polar_subscription_id)
        and subscription.status in LIVE_STATUSES
    )


# ---------------------------------------------------------------------------
# Products (admin console)
# ---------------------------------------------------------------------------


def _price_body(amount: Any, currency: str) -> dict:
    from decimal import Decimal

    return {
        "amount_type": "fixed",
        "price_amount": int(Decimal(str(amount)) * 100),
        "price_currency": (currency or "usd").lower(),
    }


async def sync_plan_products(plan: SubscriptionPlan) -> Dict[str, str]:
    """Create the plan's Polar products if missing, else refresh name and price.

    Returns ``{"monthly": id, "yearly": id}`` for the products that exist
    afterwards. Price changes are pushed as a new price on the product; Polar
    keeps existing subscribers on the price they bought.
    """
    client = get_polar_client()
    out: Dict[str, str] = {}
    for period, interval, amount in (
        ("monthly", "month", plan.price_monthly),
        ("yearly", "year", plan.price_yearly),
    ):
        existing_id = plan.polar_product_id if period == "monthly" else plan.polar_product_id_yearly
        if amount is None:
            if existing_id:
                out[period] = existing_id
            continue
        name = f"{plan.name} ({'Yearly' if period == 'yearly' else 'Monthly'})"[:64]
        if existing_id:
            await client.update_product(
                existing_id,
                {"name": name, "description": plan.description or None, "prices": [_price_body(amount, plan.currency)]},
            )
            out[period] = existing_id
        else:
            created = await client.create_product(
                {
                    "name": name,
                    "description": plan.description or None,
                    "recurring_interval": interval,
                    "prices": [_price_body(amount, plan.currency)],
                    "metadata": {"voicecon_plan": plan.slug or str(plan.id), "billing_period": period},
                }
            )
            out[period] = created["id"]
    return out


async def push_price(product_id: str, amount: Any, currency: str) -> None:
    await get_polar_client().update_product(product_id, {"prices": [_price_body(amount, currency)]})
