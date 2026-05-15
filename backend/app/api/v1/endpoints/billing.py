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

from app.core.dependencies import get_current_active_user, get_db
from app.models.user import User
from app.models.subscription import (
    SubscriptionPlan,
    Subscription,
    UsageRecord,
    Invoice,
    PaymentFailure,
)
from app.services.billing import StripeService, get_stripe_service

router = APIRouter()


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
                Subscription.organization_id == current_user.organization_id,
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
                Subscription.organization_id == current_user.organization_id,
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
        organization_id=current_user.organization_id,
    )

    # Attach payment method
    import stripe

    await stripe_service.api_key  # Ensure API key is set
    await stripe.PaymentMethod.attach(
        request.payment_method_id, customer=stripe_customer_id
    )
    await stripe.Customer.modify(
        stripe_customer_id,
        invoice_settings={"default_payment_method": request.payment_method_id},
    )

    # Create subscription
    subscription = await stripe_service.create_subscription(
        db=db,
        organization_id=current_user.organization_id,
        plan_id=request.plan_id,
        stripe_customer_id=stripe_customer_id,
        trial_days=request.trial_days,
    )

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
                Subscription.organization_id == current_user.organization_id,
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
                Subscription.organization_id == current_user.organization_id,
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
                Subscription.organization_id == current_user.organization_id,
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
        db=db, organization_id=current_user.organization_id
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
        .where(Invoice.organization_id == current_user.organization_id)
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
