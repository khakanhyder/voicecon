"""
Billing and subscription management endpoints.
"""

from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_current_org_id, get_db
from app.models.user import User
from app.models.company import CompanyProfile
from app.models.subscription import (
    SubscriptionPlan,
    Subscription,
    UsageRecord,
    Invoice,
    PaymentFailure,
)
from app.services.billing import StripeService, get_stripe_service

router = APIRouter()


async def _mark_onboarding_done(db: AsyncSession, organization_id: uuid.UUID) -> None:
    """Flag the organization's onboarding as completed once a plan/trial is active."""
    result = await db.execute(
        select(CompanyProfile).where(
            CompanyProfile.organization_id == organization_id
        )
    )
    profile = result.scalar_one_or_none()
    if profile:
        profile.onboarding_completed = True
        profile.onboarding_step = "done"
        await db.flush()


# ==================== Schemas ====================


class SubscriptionPlanResponse(BaseModel):
    """Subscription plan response."""

    id: uuid.UUID
    name: str
    description: Optional[str]
    price_monthly: float
    price_yearly: Optional[float]
    included_minutes: int
    included_calls: int
    max_agents: int
    max_phone_numbers: int
    max_knowledge_bases: int
    overage_rate_per_minute: float
    overage_rate_per_call: float
    features: dict
    is_active: bool
    is_public: bool


class SubscriptionResponse(BaseModel):
    """Subscription response."""

    id: uuid.UUID
    plan_id: uuid.UUID
    plan_name: str
    status: str
    billing_period: str
    current_period_start: datetime
    current_period_end: datetime
    trial_end: Optional[datetime]
    canceled_at: Optional[datetime]
    current_period_minutes: int
    current_period_calls: int


class UsageResponse(BaseModel):
    """Current usage response."""

    minutes_used: int
    minutes_included: int
    minutes_overage: int
    calls_used: int
    calls_included: int
    calls_overage: int
    estimated_overage_cost: float


class InvoiceResponse(BaseModel):
    """Invoice response."""

    id: uuid.UUID
    invoice_number: Optional[str]
    status: str
    amount_due: float
    amount_paid: float
    total: float
    period_start: datetime
    period_end: datetime
    due_date: Optional[datetime]
    paid_at: Optional[datetime]
    invoice_pdf: Optional[str]
    hosted_invoice_url: Optional[str]


class CreateSubscriptionRequest(BaseModel):
    """Create subscription request."""

    plan_id: uuid.UUID = Field(..., description="Subscription plan ID")
    payment_method_id: str = Field(..., description="Stripe payment method ID")
    trial_days: int = Field(0, ge=0, le=30, description="Trial period in days")


class UpdateSubscriptionRequest(BaseModel):
    """Update subscription request."""

    plan_id: uuid.UUID = Field(..., description="New plan ID")
    prorate: bool = Field(True, description="Prorate the change")


class UsageLimitsResponse(BaseModel):
    """Usage limits response."""

    has_active_subscription: bool
    within_limits: bool
    minutes_limit_reached: bool = False
    calls_limit_reached: bool = False


# ==================== Endpoints ====================


@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def list_subscription_plans(
    db: AsyncSession = Depends(get_db),
    include_inactive: bool = False,
):
    """
    List all available subscription plans.

    Args:
        db: Database session
        include_inactive: Include inactive plans

    Returns:
        List of subscription plans
    """
    query = select(SubscriptionPlan).where(SubscriptionPlan.is_public == True)
    if not include_inactive:
        query = query.where(SubscriptionPlan.is_active == True)

    query = query.order_by(SubscriptionPlan.sort_order, SubscriptionPlan.price_monthly)

    result = await db.execute(query)
    plans = result.scalars().all()

    return [
        SubscriptionPlanResponse(
            id=plan.id,
            name=plan.name,
            description=plan.description,
            price_monthly=float(plan.price_monthly),
            price_yearly=float(plan.price_yearly) if plan.price_yearly else None,
            included_minutes=plan.included_minutes,
            included_calls=plan.included_calls,
            max_agents=plan.max_agents,
            max_phone_numbers=plan.max_phone_numbers,
            max_knowledge_bases=plan.max_knowledge_bases,
            overage_rate_per_minute=float(plan.overage_rate_per_minute),
            overage_rate_per_call=float(plan.overage_rate_per_call),
            features=plan.features,
            is_active=plan.is_active,
            is_public=plan.is_public,
        )
        for plan in plans
    ]


@router.get("/subscription", response_model=Optional[SubscriptionResponse])
async def get_current_subscription(
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user's active subscription.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Current subscription or None
    """
    result = await db.execute(
        select(Subscription)
        .where(
            and_(
                Subscription.organization_id == org_id,
                Subscription.status.in_(["active", "trialing", "past_due"]),
            )
        )
        .order_by(Subscription.created_at.desc())
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        return None

    # Get plan details
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
    )
    plan = result.scalar_one_or_none()

    return SubscriptionResponse(
        id=subscription.id,
        plan_id=subscription.plan_id,
        plan_name=plan.name if plan else "Unknown",
        status=subscription.status,
        billing_period=subscription.billing_period,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        trial_end=subscription.trial_end,
        canceled_at=subscription.canceled_at,
        current_period_minutes=subscription.current_period_minutes,
        current_period_calls=subscription.current_period_calls,
    )


@router.post(
    "/subscription", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED
)
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
):
    """
    Create a new subscription.

    Args:
        request: Subscription creation request
        current_user: Current authenticated user
        db: Database session
        stripe_service: Stripe service

    Returns:
        Created subscription
    """
    # Check if user already has an active subscription
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.organization_id == org_id,
                Subscription.status.in_(["active", "trialing"]),
            )
        )
    )
    existing_sub = result.scalar_one_or_none()
    if existing_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization already has an active subscription",
        )

    # Create or get Stripe customer
    # In production, store stripe_customer_id on organization
    stripe_customer_id = await stripe_service.create_customer(
        email=current_user.email,
        name=current_user.full_name or current_user.email,
        organization_id=org_id,
    )

    # Attach payment method (Stripe SDK calls are sync — run off the event loop)
    import asyncio
    import stripe

    await asyncio.to_thread(
        stripe.PaymentMethod.attach,
        request.payment_method_id,
        customer=stripe_customer_id,
    )
    await asyncio.to_thread(
        stripe.Customer.modify,
        stripe_customer_id,
        invoice_settings={"default_payment_method": request.payment_method_id},
    )

    # Create subscription
    subscription = await stripe_service.create_subscription(
        db=db,
        organization_id=org_id,
        plan_id=request.plan_id,
        stripe_customer_id=stripe_customer_id,
        trial_days=request.trial_days,
    )

    await _mark_onboarding_done(db, org_id)
    await db.commit()

    # Get plan details
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
    )
    plan = result.scalar_one_or_none()

    return SubscriptionResponse(
        id=subscription.id,
        plan_id=subscription.plan_id,
        plan_name=plan.name if plan else "Unknown",
        status=subscription.status,
        billing_period=subscription.billing_period,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        trial_end=subscription.trial_end,
        canceled_at=subscription.canceled_at,
        current_period_minutes=subscription.current_period_minutes,
        current_period_calls=subscription.current_period_calls,
    )


@router.put("/subscription", response_model=SubscriptionResponse)
async def update_subscription(
    request: UpdateSubscriptionRequest,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
):
    """
    Update subscription to a different plan.

    Args:
        request: Update request
        current_user: Current authenticated user
        db: Database session
        stripe_service: Stripe service

    Returns:
        Updated subscription
    """
    # Get current subscription
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.organization_id == org_id,
                Subscription.status.in_(["active", "trialing"]),
            )
        )
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    # Update subscription
    updated_subscription = await stripe_service.update_subscription_plan(
        db=db,
        subscription_id=subscription.id,
        new_plan_id=request.plan_id,
        prorate=request.prorate,
    )

    # Get plan details
    result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == updated_subscription.plan_id
        )
    )
    plan = result.scalar_one_or_none()

    return SubscriptionResponse(
        id=updated_subscription.id,
        plan_id=updated_subscription.plan_id,
        plan_name=plan.name if plan else "Unknown",
        status=updated_subscription.status,
        billing_period=updated_subscription.billing_period,
        current_period_start=updated_subscription.current_period_start,
        current_period_end=updated_subscription.current_period_end,
        trial_end=updated_subscription.trial_end,
        canceled_at=updated_subscription.canceled_at,
        current_period_minutes=updated_subscription.current_period_minutes,
        current_period_calls=updated_subscription.current_period_calls,
    )


@router.delete("/subscription", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_subscription(
    immediate: bool = False,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
):
    """
    Cancel current subscription.

    Args:
        immediate: Cancel immediately vs at period end
        current_user: Current authenticated user
        db: Database session
        stripe_service: Stripe service
    """
    # Get current subscription
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.organization_id == org_id,
                Subscription.status.in_(["active", "trialing"]),
            )
        )
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    # Cancel subscription
    await stripe_service.cancel_subscription(
        db=db, subscription_id=subscription.id, immediate=immediate
    )


@router.get("/usage", response_model=UsageResponse)
async def get_current_usage(
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
):
    """
    Get current billing period usage.

    Args:
        current_user: Current authenticated user
        db: Database session
        stripe_service: Stripe service

    Returns:
        Current usage statistics
    """
    # Get subscription
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.organization_id == org_id,
                Subscription.status.in_(["active", "trialing"]),
            )
        )
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    # Get usage
    usage = await stripe_service.get_current_usage(db=db, subscription_id=subscription.id)

    # Calculate estimated overage cost
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
    )
    plan = result.scalar_one_or_none()

    estimated_cost = 0.0
    if plan:
        estimated_cost = (
            float(plan.overage_rate_per_minute) * usage["minutes_overage"]
            + float(plan.overage_rate_per_call) * usage["calls_overage"]
        )

    return UsageResponse(
        minutes_used=usage["minutes_used"],
        minutes_included=usage["minutes_included"],
        minutes_overage=usage["minutes_overage"],
        calls_used=usage["calls_used"],
        calls_included=usage["calls_included"],
        calls_overage=usage["calls_overage"],
        estimated_overage_cost=estimated_cost,
    )


@router.get("/usage/limits", response_model=UsageLimitsResponse)
async def check_usage_limits(
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
):
    """
    Check if organization is within usage limits.

    Args:
        current_user: Current authenticated user
        db: Database session
        stripe_service: Stripe service

    Returns:
        Usage limits status
    """
    limits = await stripe_service.check_usage_limits(
        db=db, organization_id=org_id
    )

    return UsageLimitsResponse(
        has_active_subscription=limits["has_active_subscription"],
        within_limits=limits["within_limits"],
        minutes_limit_reached=limits.get("minutes_limit_reached", False),
        calls_limit_reached=limits.get("calls_limit_reached", False),
    )


@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    List invoices for current organization.

    Args:
        limit: Maximum number of invoices to return
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of invoices
    """
    result = await db.execute(
        select(Invoice)
        .where(Invoice.organization_id == org_id)
        .order_by(Invoice.created_at.desc())
        .limit(limit)
    )
    invoices = result.scalars().all()

    return [
        InvoiceResponse(
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            status=invoice.status,
            amount_due=float(invoice.amount_due),
            amount_paid=float(invoice.amount_paid),
            total=float(invoice.total),
            period_start=invoice.period_start,
            period_end=invoice.period_end,
            due_date=invoice.due_date,
            paid_at=invoice.paid_at,
            invoice_pdf=invoice.invoice_pdf,
            hosted_invoice_url=invoice.hosted_invoice_url,
        )
        for invoice in invoices
    ]


@router.post("/webhooks/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
):
    """
    Handle Stripe webhook events.

    Args:
        request: FastAPI request
        stripe_signature: Stripe signature header
        db: Database session
        stripe_service: Stripe service

    Returns:
        Success response
    """
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header",
        )

    # Get raw payload
    payload = await request.body()

    # Verify signature
    try:
        event = stripe_service.verify_webhook_signature(payload, stripe_signature)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature"
        )

    # Handle event
    success = await stripe_service.handle_webhook_event(db=db, event=event)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )

    return {"status": "success"}


# ==================== Onboarding: trial + checkout ====================


class BillingConfigResponse(BaseModel):
    """Public Stripe configuration for the frontend."""

    publishable_key: Optional[str]
    configured: bool


class StartTrialRequest(BaseModel):
    """Start a 7-day free trial (no card required)."""

    plan_id: Optional[uuid.UUID] = Field(
        None, description="Optional plan to trial; defaults to the first public plan"
    )
    billing_period: str = Field("monthly", description="monthly | yearly")
    trial_days: int = Field(7, ge=1, le=30)


class CheckoutRequest(BaseModel):
    """Activate a paid subscription from the billing page."""

    plan_id: uuid.UUID = Field(..., description="Selected subscription plan")
    payment_method_id: str = Field(..., description="Stripe PaymentMethod id (pm_…)")
    billing_period: str = Field("monthly", description="monthly | yearly")


@router.get("/config", response_model=BillingConfigResponse)
async def get_billing_config():
    """Expose the Stripe publishable key so the frontend can init Stripe.js."""
    from app.core.config import settings

    return BillingConfigResponse(
        publishable_key=settings.STRIPE_PUBLISHABLE_KEY,
        configured=settings.stripe_configured,
    )


async def _get_trial_plan(
    db: AsyncSession, plan_id: Optional[uuid.UUID]
) -> SubscriptionPlan:
    """Resolve the plan to attach a trial to (explicit, else first public plan)."""
    if plan_id is not None:
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if plan:
            return plan

    result = await db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.is_active == True)
        .order_by(SubscriptionPlan.sort_order, SubscriptionPlan.price_monthly)
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription plans are available",
        )
    return plan


@router.post(
    "/trial", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED
)
async def start_free_trial(
    request: StartTrialRequest,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Start a 7-day free trial without requiring payment details.

    Records a local ``trialing`` subscription so the trial start/end dates and
    status are persisted, marks onboarding complete, and lets the user reach the
    dashboard. Works even when Stripe is not configured.
    """
    from datetime import timedelta

    # Block duplicate active/trial subscriptions
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.organization_id == org_id,
                Subscription.status.in_(["active", "trialing"]),
            )
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization already has an active subscription or trial",
        )

    plan = await _get_trial_plan(db, request.plan_id)

    now = datetime.utcnow()
    trial_end = now + timedelta(days=request.trial_days)

    subscription = Subscription(
        organization_id=org_id,
        plan_id=plan.id,
        stripe_subscription_id=f"local_trial_{uuid.uuid4()}",
        stripe_customer_id="",
        status="trialing",
        billing_period=request.billing_period,
        current_period_start=now,
        current_period_end=trial_end,
        trial_start=now,
        trial_end=trial_end,
        stripe_metadata={"source": "free_trial", "local": True},
    )
    db.add(subscription)

    await _mark_onboarding_done(db, org_id)
    await db.commit()
    await db.refresh(subscription)

    return SubscriptionResponse(
        id=subscription.id,
        plan_id=subscription.plan_id,
        plan_name=plan.name,
        status=subscription.status,
        billing_period=subscription.billing_period,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        trial_end=subscription.trial_end,
        canceled_at=subscription.canceled_at,
        current_period_minutes=subscription.current_period_minutes,
        current_period_calls=subscription.current_period_calls,
    )


@router.post(
    "/checkout", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED
)
async def checkout(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
):
    """
    Activate a paid subscription using a Stripe PaymentMethod created on the
    billing page. Persists the subscription (plan, Stripe customer/subscription
    ids, status, billing cycle, period dates) and completes onboarding.
    """
    import asyncio
    import stripe

    # Block duplicate active/trial subscriptions
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.organization_id == org_id,
                Subscription.status.in_(["active", "trialing"]),
            )
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization already has an active subscription",
        )

    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == request.plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )

    # 1. Customer
    stripe_customer_id = await stripe_service.create_customer(
        email=current_user.email,
        name=current_user.full_name or current_user.email,
        organization_id=org_id,
    )

    # 2. Attach payment method + set as default
    await asyncio.to_thread(
        stripe.PaymentMethod.attach,
        request.payment_method_id,
        customer=stripe_customer_id,
    )
    await asyncio.to_thread(
        stripe.Customer.modify,
        stripe_customer_id,
        invoice_settings={"default_payment_method": request.payment_method_id},
    )

    # 3. Resolve a price for the chosen interval
    price_id = await stripe_service.ensure_stripe_price(
        db=db, plan=plan, billing_period=request.billing_period
    )

    # 4. Create the Stripe subscription
    stripe_subscription = await asyncio.to_thread(
        stripe.Subscription.create,
        customer=stripe_customer_id,
        items=[{"price": price_id}],
        expand=["latest_invoice.payment_intent"],
        metadata={"organization_id": str(org_id), "plan_id": str(plan.id)},
    )

    # 5. Persist
    subscription = Subscription(
        organization_id=org_id,
        plan_id=plan.id,
        stripe_subscription_id=stripe_subscription.id,
        stripe_customer_id=stripe_customer_id,
        status=stripe_subscription.status,
        billing_period=request.billing_period,
        current_period_start=datetime.fromtimestamp(
            stripe_subscription.current_period_start
        ),
        current_period_end=datetime.fromtimestamp(
            stripe_subscription.current_period_end
        ),
    )
    db.add(subscription)

    await _mark_onboarding_done(db, org_id)
    await db.commit()
    await db.refresh(subscription)

    return SubscriptionResponse(
        id=subscription.id,
        plan_id=subscription.plan_id,
        plan_name=plan.name,
        status=subscription.status,
        billing_period=subscription.billing_period,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        trial_end=subscription.trial_end,
        canceled_at=subscription.canceled_at,
        current_period_minutes=subscription.current_period_minutes,
        current_period_calls=subscription.current_period_calls,
    )
