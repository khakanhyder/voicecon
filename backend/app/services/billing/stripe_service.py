"""
Stripe billing integration service.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
import uuid
import logging

import stripe


def utc_from_timestamp(epoch: Optional[int]) -> Optional[datetime]:
    """Convert a Stripe epoch to the naive **UTC** datetime the columns hold.

    The bare ``datetime.fromtimestamp(epoch)`` this replaces read the epoch in
    the *server's* local
    zone. Every date in this module is compared against ``datetime.utcnow()``,
    so on a host that is not set to UTC a subscription's period start and end
    land hours out of step with the clock that decides whether it has expired —
    and the renewal date shown to the customer is wrong by the same offset.
    Containers happen to run UTC today, which is why this never bit; that is a
    property of the deployment, not of the code.
    """
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(tzinfo=None)
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.billing import catalog
from app.models.subscription import (
    LIVE_STATUSES,
    SubscriptionPlan,
    Subscription,
    UsageRecord,
    Invoice,
    PaymentFailure,
)

logger = logging.getLogger(__name__)


class StripeService:
    """Service for handling Stripe billing operations."""

    def __init__(self, api_key: str, webhook_secret: str, configure_sdk: bool = True):
        """
        Initialize Stripe service.

        Args:
            api_key: Stripe secret API key
            webhook_secret: Stripe webhook signing secret
            configure_sdk: Whether to point the Stripe SDK at `api_key`.
                `stripe.api_key` is module-level global state shared by every
                request in the process, so an instance built without real
                credentials must not touch it — otherwise it would blank the
                key out from under a paid request running concurrently.
        """
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        if configure_sdk:
            stripe.api_key = api_key

    # ==================== Subscription Plans ====================

    async def create_subscription_plan(
        self,
        db: AsyncSession,
        name: str,
        description: str,
        price_monthly: Decimal,
        included_minutes: int = 0,
        included_calls: int = 0,
        max_agents: int = 1,
        max_phone_numbers: int = 1,
        max_knowledge_bases: int = 0,
        features: Optional[Dict[str, Any]] = None,
        price_yearly: Optional[Decimal] = None,
    ) -> SubscriptionPlan:
        """
        Create a subscription plan in Stripe and database.

        Args:
            db: Database session
            name: Plan name
            description: Plan description
            price_monthly: Monthly price in dollars
            included_minutes: Included minutes per month
            included_calls: Included calls per month
            max_agents: Maximum number of agents
            max_phone_numbers: Maximum phone numbers
            max_knowledge_bases: Maximum knowledge bases
            features: Feature flags
            price_yearly: Optional yearly price

        Returns:
            Created subscription plan
        """
        # Create Stripe product
        product = await asyncio.to_thread(
            stripe.Product.create,
            name=name,
            description=description,
            metadata={
                "included_minutes": included_minutes,
                "included_calls": included_calls,
                "max_agents": max_agents,
            },
        )

        # Create Stripe price (monthly)
        price = await asyncio.to_thread(
            stripe.Price.create,
            product=product.id,
            unit_amount=int(price_monthly * 100),  # Convert to cents
            currency="usd",
            recurring={"interval": "month"},
        )

        # Create plan in database
        plan = SubscriptionPlan(
            name=name,
            description=description,
            stripe_product_id=product.id,
            stripe_price_id=price.id,
            price_monthly=price_monthly,
            price_yearly=price_yearly,
            included_minutes=included_minutes,
            included_calls=included_calls,
            max_agents=max_agents,
            max_phone_numbers=max_phone_numbers,
            max_knowledge_bases=max_knowledge_bases,
            features=features or {},
        )

        db.add(plan)
        await db.commit()
        await db.refresh(plan)

        logger.info(f"Created subscription plan: {plan.name} ({plan.id})")
        return plan

    # ==================== Customer Management ====================

    async def create_customer(
        self,
        email: str,
        name: str,
        organization_id: uuid.UUID,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Create a Stripe customer.

        Args:
            email: Customer email
            name: Customer name
            organization_id: Organization UUID
            metadata: Additional metadata

        Returns:
            Stripe customer ID
        """
        customer_metadata = metadata or {}
        customer_metadata["organization_id"] = str(organization_id)

        customer = await asyncio.to_thread(
            stripe.Customer.create,
            email=email,
            name=name,
            metadata=customer_metadata,
        )

        logger.info(f"Created Stripe customer: {customer.id} for org {organization_id}")
        return customer.id

    # ==================== Subscriptions ====================

    async def create_subscription(
        self,
        db: AsyncSession,
        organization_id: uuid.UUID,
        plan_id: uuid.UUID,
        stripe_customer_id: str,
        trial_days: int = 0,
    ) -> Subscription:
        """
        Create a subscription for a customer.

        Args:
            db: Database session
            organization_id: Organization UUID
            plan_id: Subscription plan UUID
            stripe_customer_id: Stripe customer ID
            trial_days: Number of trial days

        Returns:
            Created subscription
        """
        # Get plan
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        # Create Stripe subscription
        stripe_sub_params = {
            "customer": stripe_customer_id,
            "items": [{"price": plan.stripe_price_id}],
            "metadata": {
                "organization_id": str(organization_id),
                "plan_id": str(plan_id),
            },
        }

        if trial_days > 0:
            stripe_sub_params["trial_period_days"] = trial_days

        stripe_subscription = await asyncio.to_thread(
            stripe.Subscription.create, **stripe_sub_params
        )

        # Create subscription in database
        subscription = Subscription(
            organization_id=organization_id,
            plan_id=plan_id,
            stripe_subscription_id=stripe_subscription.id,
            stripe_customer_id=stripe_customer_id,
            status=stripe_subscription.status,
            billing_period="monthly",
            current_period_start=utc_from_timestamp(
                stripe_subscription.current_period_start
            ),
            current_period_end=utc_from_timestamp(
                stripe_subscription.current_period_end
            ),
            trial_start=utc_from_timestamp(stripe_subscription.trial_start)
            if stripe_subscription.trial_start
            else None,
            trial_end=utc_from_timestamp(stripe_subscription.trial_end)
            if stripe_subscription.trial_end
            else None,
        )

        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)

        logger.info(
            f"Created subscription {subscription.id} for org {organization_id}"
        )
        return subscription

    async def cancel_subscription(
        self,
        db: AsyncSession,
        subscription_id: uuid.UUID,
        immediate: bool = False,
    ) -> Subscription:
        """
        Cancel a subscription.

        Args:
            db: Database session
            subscription_id: Subscription UUID
            immediate: Cancel immediately vs at period end

        Returns:
            Updated subscription
        """
        # Get subscription
        result = await db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        # Cancel in Stripe
        if immediate:
            stripe_subscription = await asyncio.to_thread(
                stripe.Subscription.delete, subscription.stripe_subscription_id
            )
        else:
            stripe_subscription = await asyncio.to_thread(
                stripe.Subscription.modify,
                subscription.stripe_subscription_id,
                cancel_at_period_end=True,
            )

        # Update database
        subscription.status = stripe_subscription.status
        subscription.canceled_at = datetime.utcnow()
        if immediate:
            subscription.ended_at = datetime.utcnow()

        await db.commit()
        await db.refresh(subscription)

        logger.info(f"Canceled subscription {subscription_id}")
        return subscription

    async def update_subscription_plan(
        self,
        db: AsyncSession,
        subscription_id: uuid.UUID,
        new_plan_id: uuid.UUID,
        prorate: bool = True,
    ) -> Subscription:
        """
        Update subscription to a different plan.

        Args:
            db: Database session
            subscription_id: Subscription UUID
            new_plan_id: New plan UUID
            prorate: Whether to prorate the change

        Returns:
            Updated subscription
        """
        # Get subscription and new plan
        result = await db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == new_plan_id)
        )
        new_plan = result.scalar_one_or_none()
        if not new_plan:
            raise ValueError(f"Plan {new_plan_id} not found")

        # Get Stripe subscription
        stripe_subscription = await asyncio.to_thread(
            stripe.Subscription.retrieve, subscription.stripe_subscription_id
        )

        # Update subscription items
        stripe_subscription = await asyncio.to_thread(
            stripe.Subscription.modify,
            subscription.stripe_subscription_id,
            items=[
                {
                    "id": stripe_subscription["items"]["data"][0].id,
                    "price": new_plan.stripe_price_id,
                }
            ],
            proration_behavior="create_prorations" if prorate else "none",
        )

        # Update database
        subscription.plan_id = new_plan_id
        subscription.status = stripe_subscription.status

        await db.commit()
        await db.refresh(subscription)

        logger.info(
            f"Updated subscription {subscription_id} to plan {new_plan_id}"
        )
        return subscription

    # ==================== Usage Tracking ====================

    async def record_usage(
        self,
        db: AsyncSession,
        subscription_id: uuid.UUID,
        usage_type: str,
        quantity: int,
        resource_type: Optional[str] = None,
        resource_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UsageRecord:
        """
        Record metered usage for billing.

        Args:
            db: Database session
            subscription_id: Subscription UUID
            usage_type: Type of usage (minutes, calls, sms)
            quantity: Quantity used
            resource_type: Optional resource type
            resource_id: Optional resource UUID
            metadata: Additional metadata

        Returns:
            Created usage record
        """
        # Get subscription with plan
        result = await db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        # Get plan for pricing
        result = await db.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.id == subscription.plan_id
            )
        )
        plan = result.scalar_one_or_none()

        # Determine unit price based on usage type
        if usage_type == "minutes":
            unit_price = plan.overage_rate_per_minute
        elif usage_type == "calls":
            unit_price = plan.overage_rate_per_call
        else:
            unit_price = Decimal("0.00")

        total_amount = unit_price * quantity

        # Create usage record
        usage_record = UsageRecord(
            subscription_id=subscription_id,
            organization_id=subscription.organization_id,
            usage_type=usage_type,
            quantity=quantity,
            unit_price=unit_price,
            total_amount=total_amount,
            resource_type=resource_type,
            resource_id=resource_id,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            metadata=metadata or {},
        )

        db.add(usage_record)

        # Update subscription usage counters
        if usage_type == "minutes":
            subscription.current_period_minutes += quantity
        elif usage_type == "calls":
            subscription.current_period_calls += quantity

        await db.commit()
        await db.refresh(usage_record)

        logger.debug(
            f"Recorded {usage_type} usage: {quantity} for subscription {subscription_id}"
        )
        return usage_record

    async def report_usage_to_stripe(
        self,
        db: AsyncSession,
        subscription_id: uuid.UUID,
    ) -> int:
        """
        Report accumulated usage to Stripe for metered billing.

        Args:
            db: Database session
            subscription_id: Subscription UUID

        Returns:
            Number of usage records reported
        """
        # Get unreported usage records
        result = await db.execute(
            select(UsageRecord).where(
                and_(
                    UsageRecord.subscription_id == subscription_id,
                    UsageRecord.reported_to_stripe == False,
                )
            )
        )
        usage_records = result.scalars().all()

        if not usage_records:
            return 0

        # Get subscription
        result = await db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        subscription = result.scalar_one_or_none()

        # Report to Stripe (aggregate by usage type)
        usage_by_type = {}
        for record in usage_records:
            if record.usage_type not in usage_by_type:
                usage_by_type[record.usage_type] = 0
            usage_by_type[record.usage_type] += record.quantity

        for usage_type, quantity in usage_by_type.items():
            # Create usage record in Stripe
            await asyncio.to_thread(
                stripe.SubscriptionItem.create_usage_record,
                subscription.stripe_subscription_id,
                quantity=quantity,
                timestamp=int(datetime.utcnow().timestamp()),
                action="increment",
            )

        # Mark as reported
        for record in usage_records:
            record.reported_to_stripe = True

        await db.commit()

        logger.info(
            f"Reported {len(usage_records)} usage records to Stripe for subscription {subscription_id}"
        )
        return len(usage_records)

    async def get_current_usage(
        self, db: AsyncSession, subscription_id: uuid.UUID
    ) -> Dict[str, int]:
        """
        Get current period usage for a subscription.

        Args:
            db: Database session
            subscription_id: Subscription UUID

        Returns:
            Dictionary with usage counts
        """
        result = await db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        result = await db.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.id == subscription.plan_id
            )
        )
        plan = result.scalar_one_or_none()

        # Minutes and calls are uncapped on every plan, so there is no allowance
        # to be "included" in and nothing to spill over into overage. The keys
        # stay in the response because clients read them; `included` reports the
        # unlimited sentinel and overage is always zero.
        return {
            "minutes_used": subscription.current_period_minutes,
            "minutes_included": catalog.UNLIMITED,
            "minutes_overage": 0,
            "calls_used": subscription.current_period_calls,
            "calls_included": catalog.UNLIMITED,
            "calls_overage": 0,
        }

    async def check_usage_limits(
        self, db: AsyncSession, organization_id: uuid.UUID
    ) -> Dict[str, bool]:
        """
        Check if organization has exceeded usage limits.

        Args:
            db: Database session
            organization_id: Organization UUID

        Returns:
            Dictionary with limit status
        """
        # Every other query in the codebase treats a subscription as live when
        # its status is in LIVE_STATUSES — which includes "trialing". Matching
        # only "active" here meant a user on the free trial was reported as
        # having no subscription and as being outside their limits, on the one
        # plan the product hands out by default.
        result = await db.execute(
            select(Subscription).where(
                and_(
                    Subscription.organization_id == organization_id,
                    Subscription.status.in_(LIVE_STATUSES),
                )
            )
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            return {
                "has_active_subscription": False,
                "within_limits": False,
            }

        # There are no conversation limits on any plan, so neither flag can be
        # reached. They remain in the response as a stable contract for clients
        # that already branch on them.
        return {
            "has_active_subscription": True,
            "within_limits": True,
            "minutes_limit_reached": False,
            "calls_limit_reached": False,
        }

    # ==================== Invoices ====================

    async def sync_invoice(
        self, db: AsyncSession, stripe_invoice_id: str
    ) -> Invoice:
        """
        Sync an invoice from Stripe to database.

        Args:
            db: Database session
            stripe_invoice_id: Stripe invoice ID

        Returns:
            Synced invoice
        """
        # Retrieve from Stripe
        stripe_invoice = await asyncio.to_thread(
            stripe.Invoice.retrieve, stripe_invoice_id
        )

        # Get or create invoice
        result = await db.execute(
            select(Invoice).where(Invoice.stripe_invoice_id == stripe_invoice_id)
        )
        invoice = result.scalar_one_or_none()

        # Get subscription
        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_invoice.subscription
            )
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            logger.warning(
                f"Subscription not found for invoice {stripe_invoice_id}"
            )
            return None

        if not invoice:
            invoice = Invoice(
                subscription_id=subscription.id,
                organization_id=subscription.organization_id,
                stripe_invoice_id=stripe_invoice_id,
                stripe_customer_id=stripe_invoice.customer,
            )
            db.add(invoice)

        # Update invoice fields
        invoice.invoice_number = stripe_invoice.number
        invoice.status = stripe_invoice.status
        invoice.amount_due = Decimal(stripe_invoice.amount_due) / 100
        invoice.amount_paid = Decimal(stripe_invoice.amount_paid) / 100
        invoice.amount_remaining = Decimal(stripe_invoice.amount_remaining) / 100
        invoice.subtotal = Decimal(stripe_invoice.subtotal) / 100
        invoice.tax = (
            Decimal(stripe_invoice.tax) / 100 if stripe_invoice.tax else None
        )
        invoice.total = Decimal(stripe_invoice.total) / 100
        invoice.invoice_pdf = stripe_invoice.invoice_pdf
        invoice.hosted_invoice_url = stripe_invoice.hosted_invoice_url
        invoice.period_start = utc_from_timestamp(
            stripe_invoice.period_start
        )
        invoice.period_end = utc_from_timestamp(stripe_invoice.period_end)
        invoice.due_date = (
            utc_from_timestamp(stripe_invoice.due_date)
            if stripe_invoice.due_date
            else None
        )
        invoice.paid_at = (
            utc_from_timestamp(stripe_invoice.status_transitions.paid_at)
            if stripe_invoice.status_transitions.paid_at
            else None
        )

        # Store line items
        invoice.line_items = {
            "data": [
                {
                    "description": item.description,
                    "amount": item.amount / 100,
                    "quantity": item.quantity,
                }
                for item in stripe_invoice.lines.data
            ]
        }

        await db.commit()
        await db.refresh(invoice)

        logger.info(f"Synced invoice {stripe_invoice_id}")
        return invoice

    async def handle_payment_failure(
        self,
        db: AsyncSession,
        invoice_id: uuid.UUID,
        failure_code: str,
        failure_message: str,
    ) -> PaymentFailure:
        """
        Record a payment failure.

        Args:
            db: Database session
            invoice_id: Invoice UUID
            failure_code: Stripe failure code
            failure_message: Failure message

        Returns:
            Created payment failure record
        """
        # Get invoice
        result = await db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Create payment failure
        payment_failure = PaymentFailure(
            invoice_id=invoice_id,
            organization_id=invoice.organization_id,
            failure_code=failure_code,
            failure_message=failure_message,
        )

        db.add(payment_failure)
        await db.commit()
        await db.refresh(payment_failure)

        logger.warning(
            f"Payment failure for invoice {invoice_id}: {failure_message}"
        )
        return payment_failure

    # ==================== Webhooks ====================

    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> Dict[str, Any]:
        """
        Verify Stripe webhook signature.

        Args:
            payload: Request payload
            signature: Stripe signature header

        Returns:
            Parsed event

        Raises:
            ValueError: If signature is invalid
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return event
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise ValueError("Invalid signature")

    async def _already_processed(
        self, db: AsyncSession, event_id: Optional[str], event_type: str
    ) -> bool:
        """Claim this Stripe event id, or report that it is a re-delivery.

        Stripe retries deliveries, so without this a repeated ``invoice.paid``
        applies its effect twice. The claim is committed before the handler
        runs: two workers racing on the same delivery means one of them loses
        the insert and skips, which is exactly the intended outcome.
        """
        from app.models.subscription import ProcessedStripeEvent

        if not event_id:
            # Unsigned/synthetic events (tests, manual replays) carry no id and
            # cannot be deduplicated. Let them through rather than dropping them.
            return False

        existing = await db.get(ProcessedStripeEvent, event_id)
        if existing is not None:
            return True

        db.add(ProcessedStripeEvent(stripe_event_id=event_id, event_type=event_type))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            return True
        return False

    async def handle_webhook_event(
        self, db: AsyncSession, event: Dict[str, Any]
    ) -> bool:
        """
        Handle a Stripe webhook event. Idempotent: a re-delivered event is a
        no-op rather than a second application of the same effect.
        """
        event_type = event["type"]
        data = event["data"]["object"]
        event_id = event.get("id")

        if await self._already_processed(db, event_id, event_type):
            logger.info(f"Skipping already-processed Stripe event {event_id}")
            return True

        logger.info(f"Handling webhook event: {event_type} ({event_id})")

        try:
            if event_type == "invoice.paid":
                await self.sync_invoice(db, data["id"])
                await self._on_invoice_paid(db, data, event_id)

            elif event_type == "invoice.payment_failed":
                invoice = await self.sync_invoice(db, data["id"])
                if invoice:
                    await self.handle_payment_failure(
                        db,
                        invoice.id,
                        data.get("last_payment_error", {}).get("code", "unknown"),
                        data.get("last_payment_error", {}).get(
                            "message", "Payment failed"
                        ),
                    )
                await self._on_payment_failed(db, data, event_id)

            elif event_type == "customer.subscription.trial_will_end":
                # Only fires for Stripe-managed trials (a card-on-file trial).
                # Our own card-free trials are noticed by the reconciler.
                await self._on_trial_will_end(db, data, event_id)

            elif event_type == "customer.subscription.updated":
                await self._on_subscription_updated(db, data, event_id)

            elif event_type == "customer.subscription.deleted":
                await self._on_subscription_deleted(db, data, event_id)

            return True

        except Exception as e:
            logger.error(f"Error handling webhook event {event_type}: {e}", exc_info=True)
            return False

    # ---- Individual webhook effects ----

    async def _subscription_by_stripe_id(
        self, db: AsyncSession, stripe_id: Optional[str]
    ) -> Optional[Subscription]:
        if not stripe_id:
            return None
        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_id
            )
        )
        return result.scalar_one_or_none()

    async def _on_invoice_paid(
        self, db: AsyncSession, data: Dict[str, Any], event_id: Optional[str]
    ) -> None:
        """A paid invoice starts a new billing period — roll the usage counters.

        Resetting here rather than on a calendar cron is what keeps the counters
        aligned with the period the customer is actually being billed for.
        """
        from app.services.billing import events as billing_events
        from app.services.billing.entitlements import invalidate_entitlements

        subscription = await self._subscription_by_stripe_id(
            db, data.get("subscription")
        )
        if subscription is None:
            return

        previous_status = subscription.status
        subscription.status = "active"
        subscription.grace_period_end = None
        subscription.expired_at = None
        subscription.current_period_minutes = 0
        subscription.current_period_calls = 0
        subscription.current_period_sms = 0
        subscription.current_period_emails = 0

        period_start = data.get("period_start")
        period_end = data.get("period_end")
        if period_start:
            subscription.current_period_start = utc_from_timestamp(period_start)
        if period_end:
            subscription.current_period_end = utc_from_timestamp(period_end)

        await billing_events.record_event(
            db,
            organization_id=subscription.organization_id,
            event_type=billing_events.RENEWED,
            subscription=subscription,
            from_status=previous_status,
            to_status=subscription.status,
            actor_type=billing_events.ACTOR_STRIPE,
            stripe_event_id=event_id,
        )
        await db.commit()
        invalidate_entitlements(subscription.organization_id)

    async def _on_payment_failed(
        self, db: AsyncSession, data: Dict[str, Any], event_id: Optional[str]
    ) -> None:
        """Start the dunning clock. Access continues while Stripe retries.

        Stripe retries roughly four times over two weeks and most failures
        resolve themselves, so cutting the customer off at the first decline
        would churn accounts that were never going to leave.
        """
        from app.services.billing import events as billing_events
        from app.services.billing.entitlements import (
            PAYMENT_GRACE_DAYS,
            invalidate_entitlements,
        )

        subscription = await self._subscription_by_stripe_id(
            db, data.get("subscription")
        )
        if subscription is None:
            return

        previous_status = subscription.status
        subscription.status = "past_due"
        if subscription.grace_period_end is None:
            subscription.grace_period_end = datetime.utcnow() + timedelta(
                days=PAYMENT_GRACE_DAYS
            )

        await billing_events.record_event(
            db,
            organization_id=subscription.organization_id,
            event_type=billing_events.PAST_DUE,
            subscription=subscription,
            from_status=previous_status,
            to_status=subscription.status,
            actor_type=billing_events.ACTOR_STRIPE,
            stripe_event_id=event_id,
            payload={"grace_period_end": subscription.grace_period_end.isoformat()},
        )
        await db.commit()
        invalidate_entitlements(subscription.organization_id)

    async def _on_trial_will_end(
        self, db: AsyncSession, data: Dict[str, Any], event_id: Optional[str]
    ) -> None:
        from app.services.billing import events as billing_events

        subscription = await self._subscription_by_stripe_id(db, data.get("id"))
        if subscription is None:
            return
        await billing_events.record_event(
            db,
            organization_id=subscription.organization_id,
            event_type=billing_events.TRIAL_EXPIRING,
            subscription=subscription,
            actor_type=billing_events.ACTOR_STRIPE,
            stripe_event_id=event_id,
        )
        await db.commit()

    async def _on_subscription_updated(
        self, db: AsyncSession, data: Dict[str, Any], event_id: Optional[str]
    ) -> None:
        from app.services.billing import events as billing_events
        from app.services.billing.entitlements import invalidate_entitlements

        subscription = await self._subscription_by_stripe_id(db, data.get("id"))
        if subscription is None:
            return

        previous_status = subscription.status
        subscription.status = data["status"]
        subscription.current_period_start = utc_from_timestamp(
            data["current_period_start"]
        )
        subscription.current_period_end = utc_from_timestamp(
            data["current_period_end"]
        )
        subscription.cancel_at_period_end = bool(data.get("cancel_at_period_end", False))
        if subscription.status == "active":
            subscription.grace_period_end = None
            subscription.expired_at = None

        if previous_status != subscription.status:
            await billing_events.record_event(
                db,
                organization_id=subscription.organization_id,
                event_type=billing_events.ACTIVATED
                if subscription.status == "active"
                else billing_events.PAST_DUE,
                subscription=subscription,
                from_status=previous_status,
                to_status=subscription.status,
                actor_type=billing_events.ACTOR_STRIPE,
                stripe_event_id=event_id,
            )
        await db.commit()
        invalidate_entitlements(subscription.organization_id)

    async def _on_subscription_deleted(
        self, db: AsyncSession, data: Dict[str, Any], event_id: Optional[str]
    ) -> None:
        """Cancelled at Stripe. Access persists until the paid period runs out.

        The reconciler moves it to ``expired`` once ``current_period_end``
        passes — this only records that it will.
        """
        from app.services.billing import events as billing_events
        from app.services.billing.entitlements import invalidate_entitlements

        subscription = await self._subscription_by_stripe_id(db, data.get("id"))
        if subscription is None:
            return

        previous_status = subscription.status
        subscription.status = "canceled"
        subscription.ended_at = datetime.utcnow()
        subscription.canceled_at = subscription.canceled_at or datetime.utcnow()

        await billing_events.record_event(
            db,
            organization_id=subscription.organization_id,
            event_type=billing_events.CANCELED,
            subscription=subscription,
            from_status=previous_status,
            to_status=subscription.status,
            actor_type=billing_events.ACTOR_STRIPE,
            stripe_event_id=event_id,
        )
        await db.commit()
        invalidate_entitlements(subscription.organization_id)


    # ==================== Pricing helpers ====================

    async def get_or_create_price(
        self,
        product_id: str,
        unit_amount_cents: int,
        interval: str,
        currency: str = "usd",
    ) -> str:
        """
        Find a recurring Stripe Price for a product matching amount + interval,
        creating it if it does not exist. Lets us support monthly/yearly billing
        without storing a separate price id per interval.
        """
        prices = await asyncio.to_thread(
            stripe.Price.list, product=product_id, active=True, limit=100
        )
        for price in prices.data:
            recurring = price.get("recurring") or {}
            if (
                price.get("unit_amount") == unit_amount_cents
                and recurring.get("interval") == interval
                and price.get("currency") == currency
            ):
                return price.id

        price = await asyncio.to_thread(
            stripe.Price.create,
            product=product_id,
            unit_amount=unit_amount_cents,
            currency=currency,
            recurring={"interval": interval},
        )
        return price.id

    async def ensure_stripe_price(
        self,
        db: AsyncSession,
        plan: SubscriptionPlan,
        billing_period: str,
    ) -> str:
        """
        Return a usable Stripe price id for ``plan`` on the requested interval,
        creating the Stripe product/price on demand. Handles plans seeded with
        placeholder ids (when Stripe was not configured at seed time) by creating
        the real Stripe product and backfilling the DB row.
        """
        # Ensure a real Stripe product exists
        product_id = plan.stripe_product_id
        if not product_id or not product_id.startswith("prod_"):
            product = await asyncio.to_thread(
                stripe.Product.create,
                name=plan.name,
                description=plan.description or plan.name,
                metadata={"plan_id": str(plan.id)},
            )
            product_id = product.id
            plan.stripe_product_id = product_id

        interval = "year" if billing_period == "yearly" else "month"
        if interval == "year":
            # Never fall back to the monthly amount here. That silently charged
            # one month's price for a *year* of service, against a pricing page
            # that had already quoted the yearly figure (it renders a 25%-off
            # estimate when the column is empty). Refusing surfaces the missing
            # price to an operator instead of billing the wrong number.
            if not plan.price_yearly:
                from fastapi import HTTPException, status

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Yearly billing is not available for this plan yet. "
                        "Choose monthly, or contact support."
                    ),
                )
            amount = int(Decimal(plan.price_yearly) * 100)
        else:
            amount = int(Decimal(plan.price_monthly) * 100)

        price_id = await self.get_or_create_price(
            product_id=product_id,
            unit_amount_cents=amount,
            interval=interval,
            currency=plan.currency or "usd",
        )

        # Cache the monthly price id on the plan for reuse
        if interval == "month" and (
            not plan.stripe_price_id or not plan.stripe_price_id.startswith("price_")
        ):
            plan.stripe_price_id = price_id

        await db.flush()
        return price_id


# Dependency for FastAPI
async def get_stripe_service() -> StripeService:
    """Get Stripe service instance.

    Reads keys from application settings (STRIPE_SECRET_KEY, falling back to the
    legacy STRIPE_API_KEY). Raises 503 only when no usable key is configured so
    the free-trial path keeps working without Stripe.
    """
    from app.core.config import settings

    # Treat missing OR placeholder keys (e.g. "sk_test_...") as not configured so
    # the paid path fails fast with a clear message instead of hitting Stripe with
    # an invalid key. The free-trial path does not depend on this service.
    if not settings.stripe_configured:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Card payments are not configured yet. Please try the free trial.",
        )

    api_key = settings.stripe_secret_key
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET or "not_configured"

    return StripeService(api_key=api_key, webhook_secret=webhook_secret)


async def get_usage_reader() -> StripeService:
    """
    A service for endpoints that only read usage rows out of our own database.

    `get_current_usage` and `check_usage_limits` never call Stripe — they read
    the local Subscription and SubscriptionPlan and do arithmetic. Obtaining
    them through `get_stripe_service` meant the *dependency* rejected the
    request with 503 whenever Stripe was unconfigured, so a trial user on a
    deployment with no card payments set up could not load the billing page at
    all — despite that being exactly the case the trial exists to serve.

    No credentials, and deliberately does not configure the SDK: this instance
    must never be able to make a live call.
    """
    return StripeService(api_key="", webhook_secret="", configure_sdk=False)
