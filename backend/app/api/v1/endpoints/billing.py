"""
Billing and subscription management endpoints.

Covers the whole lifecycle: pick a plan or start a card-free trial, convert that
trial into a paid subscription, move between plans, cancel and reactivate — plus
the read surface (``/entitlements``, ``/events``) the dashboard gates its UI on.

The endpoints here are deliberately exempt from the entitlement guard (see
``app.core.entitlement_guard.EXEMPT_PREFIXES``): an organization that has
stopped paying must always be able to reach the page where it can start again.
"""

import logging
from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_current_org_id, get_db
from app.models.user import User
from app.models.company import CompanyProfile
from app.models.subscription import (
    LIVE_STATUSES,
    SOURCE_STRIPE,
    SOURCE_TRIAL,
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_TRIALING,
    SubscriptionPlan,
    Subscription,
    SubscriptionEvent,
    TrialGrant,
    UsageRecord,
    Invoice,
    PaymentFailure,
)
from app.services.billing import StripeService, catalog, get_stripe_service, get_usage_reader, events
from app.services.billing.entitlements import (
    get_entitlement_service,
    invalidate_entitlements,
)

logger = logging.getLogger(__name__)

router = APIRouter()

#: Routes that must stay reachable without a workspace context — carrier and
#: payment-provider webhooks, and the public embed surfaces. They live on their
#: own router so the authenticated router can carry a blanket permission guard
#: (see app.api.v1.api) without accidentally locking these out.
public_router = APIRouter()


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
    slug: Optional[str]
    tier: int
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
    #: Marketing copy for the pricing card.
    features: dict
    #: Machine-readable capabilities, so the UI can show exactly which features
    #: an upgrade would unlock instead of guessing from the bullet list.
    entitlements: dict
    trial_days: int
    is_trialable: bool
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
    #: Kept only so older clients still parse. **Ignored** — the length of a
    #: trial is not the client's decision, and a client-chosen
    #: ``trial_period_days`` here was a way around the one-trial-per-account
    #: rule that ``POST /billing/trial`` enforces. Anything non-zero is refused
    #: rather than silently dropped, so a caller relying on it finds out.
    trial_days: int = Field(
        0, ge=0, le=30, deprecated=True, description="Deprecated — use POST /billing/trial"
    )


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


@public_router.get("/plans", response_model=List[SubscriptionPlanResponse])
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
            slug=plan.slug,
            tier=plan.tier or 0,
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
            features=plan.features or {},
            entitlements=plan.entitlements or catalog.entitlements_for_plan(plan.slug),
            trial_days=plan.trial_days or catalog.DEFAULT_TRIAL_DAYS,
            is_trialable=bool(plan.is_trialable),
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
                Subscription.status.in_(LIVE_STATUSES),
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
    # Free trials are granted by POST /billing/trial and nowhere else, because
    # that is where the once-per-account rule lives. Honouring a client-supplied
    # trial length here would hand a fresh Stripe-side trial to an account whose
    # free trial has already run out — with no grant recorded to stop the next one.
    if request.trial_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "trial_days is no longer accepted here. Start a free trial with "
                "POST /billing/trial, which enforces one trial per account."
            ),
        )

    # Check if user already has an active subscription
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.organization_id == org_id,
                Subscription.status.in_(LIVE_STATUSES),
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

    # Create subscription. No trial: see the check at the top of this endpoint.
    subscription = await stripe_service.create_subscription(
        db=db,
        organization_id=org_id,
        plan_id=request.plan_id,
        stripe_customer_id=stripe_customer_id,
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
                Subscription.status.in_(LIVE_STATUSES),
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
    Cancel the current subscription.

    Defaults to cancelling **at the end of the paid period** — the customer paid
    for that period and should keep it. ``immediate=true`` ends it now, which is
    also what a trial cancellation does since there is nothing paid to run out.
    """
    subscription = await _existing_live_subscription(db, org_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    now = datetime.utcnow()
    previous_status = subscription.status
    trial_without_stripe = subscription.stripe_subscription_id is None

    if trial_without_stripe:
        # No Stripe object to cancel. A trial the user walks away from ends now.
        subscription.status = STATUS_CANCELED
        subscription.canceled_at = now
        subscription.ended_at = now
        subscription.current_period_end = min(subscription.current_period_end, now)
    else:
        await stripe_service.cancel_subscription(
            db=db, subscription_id=subscription.id, immediate=immediate
        )
        await db.refresh(subscription)
        subscription.canceled_at = subscription.canceled_at or now
        subscription.cancel_at_period_end = not immediate

    await events.record_event(
        db,
        organization_id=org_id,
        event_type=events.CANCELED,
        subscription=subscription,
        from_status=previous_status,
        to_status=subscription.status,
        actor_type=events.ACTOR_USER,
        actor_id=current_user.id,
        payload={
            "immediate": immediate or trial_without_stripe,
            "access_until": subscription.current_period_end.isoformat(),
        },
    )
    await db.commit()
    invalidate_entitlements(org_id)


@router.get("/usage", response_model=UsageResponse)
async def get_current_usage(
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    # Reads local usage rows only, so it must not require Stripe to be
    # configured — see get_usage_reader.
    stripe_service: StripeService = Depends(get_usage_reader),
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
                Subscription.status.in_(LIVE_STATUSES),
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
    # Reads local usage rows only, so it must not require Stripe to be
    # configured — see get_usage_reader.
    stripe_service: StripeService = Depends(get_usage_reader),
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


@public_router.post("/webhooks/stripe", status_code=status.HTTP_200_OK)
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
    """Start a free trial (no card required)."""

    plan_id: Optional[uuid.UUID] = Field(
        None, description="Optional plan to trial; defaults to the trialable plan"
    )
    billing_period: str = Field("monthly", description="monthly | yearly")


class CheckoutRequest(BaseModel):
    """Activate a paid subscription from the billing page."""

    plan_id: uuid.UUID = Field(..., description="Selected subscription plan")
    payment_method_id: str = Field(..., description="Stripe PaymentMethod id (pm_…)")
    billing_period: str = Field("monthly", description="monthly | yearly")


class ChangePlanRequest(BaseModel):
    """Move between paid plans."""

    plan_id: uuid.UUID = Field(..., description="Plan to move to")


class EntitlementsResponse(BaseModel):
    """Everything the dashboard needs to render the current billing state."""

    status: str
    plan_id: Optional[uuid.UUID]
    plan_slug: Optional[str]
    plan_name: Optional[str]
    plan_tier: int
    source: Optional[str]
    billing_period: Optional[str]

    is_live: bool
    is_read_only: bool
    is_trial: bool
    in_grace: bool
    has_subscription: bool

    trial_end: Optional[datetime]
    days_remaining: Optional[int]
    trial_expiring_soon: bool
    grace_period_end: Optional[datetime]
    grace_days_remaining: Optional[int]
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool

    features: List[str]
    limits: dict
    usage: dict
    overage_allowed: bool

    #: May this caller still start a free trial? Presentation only — the server
    #: re-checks on ``POST /billing/trial`` — but without it the UI offers a
    #: button whose only possible outcome is a 409.
    trial_available: bool = False
    #: The trial has been used up (by this workspace or this person). Distinct
    #: from ``not trial_available``, which is also false while a trial is *running*.
    trial_used: bool = False


class SubscriptionEventResponse(BaseModel):
    """One entry from the subscription history."""

    id: uuid.UUID
    event_type: str
    from_status: Optional[str]
    to_status: Optional[str]
    actor_type: str
    created_at: datetime
    payload: dict


@public_router.get("/config", response_model=BillingConfigResponse)
async def get_billing_config():
    """Expose the Stripe publishable key so the frontend can init Stripe.js."""
    from app.core.config import settings

    return BillingConfigResponse(
        publishable_key=settings.STRIPE_PUBLISHABLE_KEY,
        configured=settings.stripe_configured,
    )


@router.get("/entitlements", response_model=EntitlementsResponse)
async def get_entitlements(
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    refresh: bool = False,
):
    """What this organization may do right now, plus how much of it is left.

    The dashboard hydrates from this once and gates its UI on the result. The
    server enforces the same entitlements independently — this is presentation
    data, never the security boundary.

    Pass ``refresh=true`` immediately after a checkout, so the caller does not
    land on the dashboard still rendering the pre-upgrade state.
    """
    service = get_entitlement_service()
    ent = await service.resolve(db, org_id, fresh=refresh)
    ent = ent.with_usage(await service.usage_snapshot(db, org_id))

    # Only worth asking when there is nothing live to lose: an organization
    # that is running does not need a trial, so the common case costs no extra
    # queries at all.
    trial_used = False
    if not ent.is_live:
        trial_used = await _trial_already_used(db, current_user, org_id) is not None

    return EntitlementsResponse(
        status=ent.status,
        plan_id=ent.plan_id,
        plan_slug=ent.plan_slug,
        plan_name=ent.plan_name,
        plan_tier=ent.plan_tier,
        source=ent.source,
        billing_period=ent.billing_period,
        is_live=ent.is_live,
        is_read_only=ent.is_read_only,
        is_trial=ent.is_trial,
        in_grace=ent.in_grace,
        has_subscription=ent.has_subscription,
        trial_end=ent.trial_end,
        days_remaining=ent.days_remaining,
        trial_expiring_soon=ent.trial_expiring_soon,
        grace_period_end=ent.grace_period_end,
        grace_days_remaining=ent.grace_days_remaining,
        current_period_end=ent.current_period_end,
        cancel_at_period_end=ent.cancel_at_period_end,
        features=sorted(ent.features),
        limits=dict(ent.limits),
        usage=dict(ent.usage),
        overage_allowed=ent.overage_allowed,
        trial_available=not ent.is_live and not trial_used,
        trial_used=trial_used,
    )


@router.get("/events", response_model=List[SubscriptionEventResponse])
async def list_subscription_events(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """The subscription history for this organization, newest first.

    Support and finance use this to answer "why is this account in this state?";
    it is append-only, so it is the one record that cannot have been overwritten
    by a later transition.
    """
    result = await db.execute(
        select(SubscriptionEvent)
        .where(SubscriptionEvent.organization_id == org_id)
        .order_by(SubscriptionEvent.created_at.desc())
        .limit(min(limit, 200))
    )
    return [
        SubscriptionEventResponse(
            id=event.id,
            event_type=event.event_type,
            from_status=event.from_status,
            to_status=event.to_status,
            actor_type=event.actor_type,
            created_at=event.created_at,
            payload=event.payload or {},
        )
        for event in result.scalars().all()
    ]


async def _get_trial_plan(
    db: AsyncSession, plan_id: Optional[uuid.UUID]
) -> SubscriptionPlan:
    """The plan a free trial is attached to.

    Defaults to the *highest* trialable tier, not the cheapest plan. Trials
    convert on feature discovery: someone who never sees lead scoring or
    campaigns has no reason to choose the expensive plan, so trialling the cheap
    one caps our own conversion. Consumption is what actually costs us money,
    and ``catalog.TRIAL_ENTITLEMENTS`` caps that hard regardless of plan.
    """
    if plan_id is not None:
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        # A plan the operator marked non-trialable (or retired) is not something
        # a client gets to trial by naming its id. Fall through to the default
        # rather than erroring — the customer asked for a trial, and there is a
        # perfectly good plan to give them.
        if plan and plan.is_active and plan.is_trialable:
            return plan
        if plan is not None:
            logger.info(
                "Ignoring requested trial plan %s (active=%s, trialable=%s)",
                plan_id,
                plan.is_active,
                plan.is_trialable,
            )

    result = await db.execute(
        select(SubscriptionPlan)
        .where(
            SubscriptionPlan.is_active == True,  # noqa: E712 — SQL expression
            SubscriptionPlan.is_trialable == True,  # noqa: E712
        )
        .order_by(SubscriptionPlan.tier.desc(), SubscriptionPlan.price_monthly.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if plan:
        return plan

    # No plan is flagged trialable (a database seeded before that column
    # existed). Fall back to the highest tier rather than refusing the trial.
    result = await db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.is_active == True)  # noqa: E712
        .order_by(SubscriptionPlan.tier.desc(), SubscriptionPlan.price_monthly.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription plans are available",
        )
    return plan


async def _existing_live_subscription(
    db: AsyncSession, org_id: uuid.UUID
) -> Optional[Subscription]:
    return await get_entitlement_service().live_subscription(db, org_id)


def _email_domain(email: str) -> str:
    return (email or "").split("@")[-1].strip().lower()


#: Refuse a trial when another account at the same email domain has already had
#: one. Off by default, and deliberately so: a second team signing up at a large
#: company is a real and common case, and refusing them turns an anti-abuse
#: measure into lost revenue. Domain collisions are logged instead, so the
#: decision to tighten this can be made from evidence rather than a guess.
BLOCK_REPEAT_TRIALS_BY_DOMAIN = False


async def _trial_already_used(
    db: AsyncSession, user: User, organization_id: uuid.UUID
) -> Optional[str]:
    """Why this caller may not start a free trial, or ``None`` if they may.

    A free trial is once, and "once" has to be pinned to more than one thing —
    each arm below closes a different way of asking for a second one:

    * **This workspace has had one.** The trial belongs to the organization, not
      to whoever clicked the button. Without this arm a second owner or admin
      simply starts the trial again the day the first one's expires, forever.
    * **This person has had one**, in any workspace. Otherwise deleting the
      workspace and creating a new one resets the clock.
    * **This email domain has had one** — advisory only, because it cannot tell
      "the same person came back with a new address" apart from "a different
      team at the same company signed up". See
      :data:`BLOCK_REPEAT_TRIALS_BY_DOMAIN`.

    Returns a short machine-ish reason for the log; the caller turns it into a
    409. Cheap: every arm is a single indexed lookup with ``LIMIT 1``.
    """
    result = await db.execute(
        select(TrialGrant.id)
        .where(TrialGrant.organization_id == organization_id)
        .limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return "organization_already_trialed"

    # Belt and braces for rows the grant ledger never saw: a trial created
    # before ``trial_grants`` existed and missed by the backfill, or one whose
    # grant insert was rolled back. The subscription row itself is then the only
    # evidence the workspace has already had its trial, and it is enough.
    result = await db.execute(
        select(Subscription.id)
        .where(
            Subscription.organization_id == organization_id,
            Subscription.source == SOURCE_TRIAL,
        )
        .limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return "organization_has_prior_trial_subscription"

    result = await db.execute(
        select(TrialGrant.id).where(TrialGrant.user_id == user.id).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return "user_already_trialed"

    domain = _email_domain(user.email)
    if not domain or domain in _CONSUMER_EMAIL_DOMAINS:
        # A shared consumer domain says nothing about who the company is, so
        # matching on it would refuse every second gmail.com signup.
        return None

    result = await db.execute(
        select(TrialGrant).where(TrialGrant.email_domain == domain).limit(1)
    )
    domain_grant = result.scalar_one_or_none()
    if domain_grant is None:
        return None

    logger.info(
        "Trial domain collision: %s shares a domain with an earlier trial "
        "(grant %s, org %s). %s",
        user.email,
        domain_grant.id,
        domain_grant.organization_id,
        "Refusing." if BLOCK_REPEAT_TRIALS_BY_DOMAIN else "Allowing — see BLOCK_REPEAT_TRIALS_BY_DOMAIN.",
    )
    return "domain_already_trialed" if BLOCK_REPEAT_TRIALS_BY_DOMAIN else None


#: Domains where a shared suffix implies nothing about a shared company.
_CONSUMER_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "icloud.com",
        "me.com",
        "proton.me",
        "protonmail.com",
        "aol.com",
        "gmx.com",
        "mail.com",
        "yandex.com",
        "zoho.com",
    }
)


def _subscription_response(
    subscription: Subscription, plan: Optional[SubscriptionPlan]
) -> SubscriptionResponse:
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
    "/trial", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED
)
async def start_free_trial(
    request: StartTrialRequest,
    http_request: Request,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Start a free trial without requiring payment details.

    Records a ``trialing`` subscription with a real end date, marks onboarding
    complete, and lets the user reach the dashboard. Works with Stripe entirely
    unconfigured — a card-free trial has no Stripe object, which is why
    ``stripe_subscription_id`` is nullable rather than being given a fake id.

    The trial genuinely ends: the entitlement resolver compares ``trial_end`` to
    the clock on every request, and the reconciler moves the row through grace
    to expired and sends the notices.
    """
    from datetime import timedelta

    if await _existing_live_subscription(db, org_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This workspace already has an active subscription or trial",
        )

    reason = await _trial_already_used(db, current_user, org_id)
    if reason is not None:
        # Logged and refused. If this turns out to catch legitimate second teams
        # at the same company, the domain arm of the check is what to relax —
        # the per-user and per-organization arms should stay.
        logger.info(
            "Refused a second trial for user %s in org %s (%s)",
            current_user.id,
            org_id,
            reason,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A free trial has already been used for this account. "
                "Choose a plan to continue."
            ),
        )

    plan = await _get_trial_plan(db, request.plan_id)
    trial_days = plan.trial_days or catalog.DEFAULT_TRIAL_DAYS

    now = datetime.utcnow()
    trial_end = now + timedelta(days=trial_days)

    subscription = Subscription(
        organization_id=org_id,
        plan_id=plan.id,
        stripe_subscription_id=None,
        stripe_customer_id=None,
        status=STATUS_TRIALING,
        source=SOURCE_TRIAL,
        billing_period=request.billing_period,
        current_period_start=now,
        current_period_end=trial_end,
        trial_start=now,
        trial_end=trial_end,
        stripe_metadata={"source": "free_trial"},
    )
    db.add(subscription)
    await db.flush()

    db.add(
        TrialGrant(
            organization_id=org_id,
            user_id=current_user.id,
            email_domain=_email_domain(current_user.email),
            signup_ip=http_request.client.host if http_request.client else None,
            granted_at=now,
            expires_at=trial_end,
        )
    )
    await events.record_event(
        db,
        organization_id=org_id,
        event_type=events.TRIAL_STARTED,
        subscription=subscription,
        to_status=STATUS_TRIALING,
        to_plan_id=plan.id,
        actor_type=events.ACTOR_USER,
        actor_id=current_user.id,
        payload={"trial_days": trial_days, "trial_end": trial_end.isoformat()},
    )

    await _mark_onboarding_done(db, org_id)

    try:
        await db.commit()
    except IntegrityError:
        # The partial unique index caught a concurrent trial start. Whichever
        # request won, the caller now has exactly one trial.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This workspace already has an active subscription or trial",
        )

    await db.refresh(subscription)
    invalidate_entitlements(org_id)

    return _subscription_response(subscription, plan)


#: Stripe subscription statuses that mean the customer is paid up and running.
#: Anything else back from ``Subscription.create`` means the money did not move —
#: a card needing 3-D Secure comes back ``incomplete``, a declined one
#: ``incomplete_expired``.
STRIPE_LIVE_STATUSES = frozenset({"active", "trialing", "past_due"})


def apply_paid_conversion(
    subscription: Subscription,
    plan: SubscriptionPlan,
    *,
    stripe_subscription_id: str,
    stripe_customer_id: str,
    stripe_status: str,
    billing_period: str,
    period_start: datetime,
    period_end: datetime,
    now: datetime,
) -> bool:
    """Turn a trial — or a lapsed subscription — into the paid plan, in place.

    Returns ``True`` when what was converted was a trial.

    The trial is *ended*, not merely overwritten. ``status`` and ``source`` both
    leave their trial values, and ``trial_end`` is pulled back to ``now`` so no
    code path anywhere can still see a trial running into the future. That last
    part is what makes the switchover total: the entitlement resolver picks the
    trial's restrictive limits purely on ``status == trialing``, so a paying
    customer with a future-dated ``trial_end`` sitting in the row is one status
    write away from being handed 1-agent trial limits again. Clearing it means
    there is nothing left to go back to.

    What the trial *would* have run to is kept in ``stripe_metadata`` — the
    customer gave up those days by paying early, and conversion reporting should
    be able to see that rather than having it silently overwritten.
    """
    converting_trial = subscription.source == SOURCE_TRIAL

    subscription.plan_id = plan.id
    subscription.stripe_subscription_id = stripe_subscription_id
    subscription.stripe_customer_id = stripe_customer_id
    subscription.status = stripe_status
    subscription.source = SOURCE_STRIPE
    subscription.billing_period = billing_period
    subscription.current_period_start = period_start
    subscription.current_period_end = period_end
    subscription.cancel_at_period_end = False
    subscription.canceled_at = None
    subscription.expired_at = None
    subscription.grace_period_end = None
    #: Any downgrade the old subscription had queued is void — the customer has
    #: just chosen a plan explicitly, and that choice wins.
    subscription.scheduled_plan_id = None

    if converting_trial:
        if subscription.trial_converted_at is None:
            subscription.trial_converted_at = now
        scheduled_end = subscription.trial_end
        if scheduled_end is not None and scheduled_end > now:
            metadata = dict(subscription.stripe_metadata or {})
            metadata["trial_end_forfeited"] = scheduled_end.isoformat()
            subscription.stripe_metadata = metadata
        subscription.trial_end = now

    # A converted trial starts its paid allowance clean rather than inheriting
    # the trial's consumption.
    subscription.current_period_minutes = 0
    subscription.current_period_calls = 0
    subscription.current_period_sms = 0
    subscription.current_period_emails = 0

    return converting_trial


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
    Activate a paid subscription, or convert a free trial into one.

    Handles both entry points, because they are the same act from the customer's
    side. A trialing, grace or expired trial is converted **in place** — the same
    row gains the Stripe ids and flips to ``active`` — rather than inserting a
    second subscription. That keeps the one-live-subscription constraint
    satisfied and preserves the trial→paid link that conversion reporting needs.
    """
    import asyncio
    import stripe

    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == request.plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
        )

    # The row we may be converting: a live trial, or the most recent lapsed one.
    existing = await _existing_live_subscription(db, org_id)
    if existing is None:
        result = await db.execute(
            select(Subscription)
            .where(Subscription.organization_id == org_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()

    if existing is not None and existing.status == STATUS_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This workspace already has an active subscription. "
                "Use change-plan to move between plans."
            ),
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

    # 3. Resolve a price for the chosen interval. Never trust a client-supplied
    #    amount — the price is looked up from the plan, server-side.
    price_id = await stripe_service.ensure_stripe_price(
        db=db, plan=plan, billing_period=request.billing_period
    )

    # 4. Create the Stripe subscription. No ``trial_period_days``: any trial the
    #    customer had was ours, ran on our clock, and has already been used.
    stripe_subscription = await asyncio.to_thread(
        stripe.Subscription.create,
        customer=stripe_customer_id,
        items=[{"price": price_id}],
        expand=["latest_invoice.payment_intent"],
        metadata={"organization_id": str(org_id), "plan_id": str(plan.id)},
        idempotency_key=f"checkout:{org_id}:{plan.id}:{request.payment_method_id}",
    )

    # 4a. Refuse to convert onto a subscription Stripe has not actually started.
    #     A card needing 3-D Secure comes back ``incomplete``, and that status is
    #     in neither LIVE_STATUSES nor RUNTIME_STATUSES — writing it onto the row
    #     would resolve the workspace to EXPIRED entitlements: every feature off,
    #     every limit zero, read-only. That is strictly worse than the trial the
    #     customer walked in with, and the trial cannot be started again. So we
    #     leave their subscription untouched, bin the unpaid Stripe object rather
    #     than leaving it to linger, and tell them the payment did not go through.
    if stripe_subscription.status not in STRIPE_LIVE_STATUSES:
        try:
            await asyncio.to_thread(stripe.Subscription.delete, stripe_subscription.id)
        except Exception as exc:  # pragma: no cover - best effort cleanup
            logger.warning(
                f"Could not clean up unpaid Stripe subscription "
                f"{stripe_subscription.id} for org {org_id}: {exc}"
            )
        logger.warning(
            f"Checkout for org {org_id} left Stripe subscription in "
            f"'{stripe_subscription.status}'; subscription unchanged."
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                "Your card was not charged — the payment could not be completed. "
                "Nothing has changed on your account. Try a different card."
            ),
        )

    now = datetime.utcnow()
    period_start = datetime.fromtimestamp(stripe_subscription.current_period_start)
    period_end = datetime.fromtimestamp(stripe_subscription.current_period_end)

    if existing is not None:
        # 5a. Convert in place: the trial ends here and the paid plan takes over.
        previous_status = existing.status
        converting_trial = apply_paid_conversion(
            existing,
            plan,
            stripe_subscription_id=stripe_subscription.id,
            stripe_customer_id=stripe_customer_id,
            stripe_status=stripe_subscription.status,
            billing_period=request.billing_period,
            period_start=period_start,
            period_end=period_end,
            now=now,
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
            actor_type=events.ACTOR_USER,
            actor_id=current_user.id,
        )

        if converting_trial:
            grants = await db.execute(
                select(TrialGrant).where(TrialGrant.organization_id == org_id)
            )
            for grant in grants.scalars().all():
                grant.converted = True
    else:
        # 5b. First subscription for this workspace.
        subscription = Subscription(
            organization_id=org_id,
            plan_id=plan.id,
            stripe_subscription_id=stripe_subscription.id,
            stripe_customer_id=stripe_customer_id,
            status=stripe_subscription.status,
            source=SOURCE_STRIPE,
            billing_period=request.billing_period,
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
            actor_type=events.ACTOR_USER,
            actor_id=current_user.id,
        )

    await _mark_onboarding_done(db, org_id)
    await db.commit()
    await db.refresh(subscription)
    invalidate_entitlements(org_id)

    try:
        from app.services.email.service import email_service
        from app.core.config import settings

        base = (settings.FRONTEND_URL or "").rstrip("/")
        action_url = f"{base}/dashboard/settings/billing"

        import asyncio
        asyncio.create_task(
            email_service.send_subscription_confirmation(
                to_email=current_user.email,
                plan_name=plan.name,
                action_url=action_url,
            )
        )
    except Exception as exc:
        logger.error(f"Failed to send subscription confirmation email: {exc}")

    return _subscription_response(subscription, plan)


@router.post("/subscription/change-plan", response_model=SubscriptionResponse)
async def change_plan(
    request: ChangePlanRequest,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
):
    """
    Move between paid plans.

    **Upgrades apply immediately** and Stripe prorates the difference — the
    customer is paying more, so they should get the capacity at once.

    **Downgrades take effect at the end of the paid period**, because the
    customer already paid for the capacity they currently have. Before accepting
    one we check the workspace actually *fits* the smaller plan and refuse with
    an explicit list of what is over the limit. Silently deleting a customer's
    agents to make a downgrade fit would be indefensible.
    """
    subscription = await _existing_live_subscription(db, org_id)
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription found"
        )

    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == request.plan_id)
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    if target.id == subscription.plan_id and subscription.scheduled_plan_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You're already on {target.name}",
        )

    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
    )
    current_plan = result.scalar_one_or_none()
    is_upgrade = target.tier >= (current_plan.tier if current_plan else 0)

    if not is_upgrade:
        conflicts = await _downgrade_conflicts(db, org_id, target)
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "detail": (
                        f"Your workspace uses more than {target.name} allows. "
                        "Remove the items listed before downgrading."
                    ),
                    "code": "downgrade_blocked",
                    "conflicts": conflicts,
                },
            )

    previous_plan_id = subscription.plan_id

    if is_upgrade:
        if subscription.stripe_subscription_id:
            await stripe_service.update_subscription_plan(
                db=db,
                subscription_id=subscription.id,
                new_plan_id=target.id,
                prorate=True,
            )
            await db.refresh(subscription)
        else:
            # A trial has no Stripe object to prorate against; switching the
            # plan it trials is just a column change.
            subscription.plan_id = target.id
        subscription.scheduled_plan_id = None
        event_type = events.PLAN_CHANGED
    else:
        subscription.scheduled_plan_id = target.id
        event_type = events.PLAN_CHANGE_SCHEDULED

    await events.record_event(
        db,
        organization_id=org_id,
        event_type=event_type,
        subscription=subscription,
        from_plan_id=previous_plan_id,
        to_plan_id=target.id,
        actor_type=events.ACTOR_USER,
        actor_id=current_user.id,
        payload={
            "direction": "upgrade" if is_upgrade else "downgrade",
            "effective": "immediately"
            if is_upgrade
            else subscription.current_period_end.isoformat(),
        },
    )

    await db.commit()
    await db.refresh(subscription)
    invalidate_entitlements(org_id)

    if is_upgrade:
        try:
            from app.services.email.service import email_service
            from app.core.config import settings

            base = (settings.FRONTEND_URL or "").rstrip("/")
            action_url = f"{base}/dashboard/settings/billing"

            import asyncio
            asyncio.create_task(
                email_service.send_subscription_confirmation(
                    to_email=current_user.email,
                    plan_name=target.name,
                    action_url=action_url,
                )
            )
        except Exception as exc:
            logger.error(f"Failed to send subscription confirmation email on upgrade: {exc}")

    effective_plan = target if is_upgrade else current_plan
    return _subscription_response(subscription, effective_plan)


async def _downgrade_conflicts(
    db: AsyncSession, org_id: uuid.UUID, target: SubscriptionPlan
) -> List[dict]:
    """What the workspace would have to give up to fit ``target``."""
    document = target.entitlements or catalog.entitlements_for_plan(target.slug)
    limits = document.get("limits") or {}
    counts = await get_entitlement_service().usage_snapshot(db, org_id)

    conflicts = []
    for key in catalog.RESOURCE_LIMITS:
        cap = int(limits.get(key, 0))
        if cap == -1:
            continue
        current = counts.get(key, 0)
        if current > cap:
            conflicts.append(
                {
                    "resource": key,
                    "label": catalog.LIMIT_LABELS.get(key, key),
                    "current": current,
                    "allowed": cap,
                }
            )
    return conflicts


@router.post("/subscription/reactivate", response_model=SubscriptionResponse)
async def reactivate_subscription(
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
):
    """Undo a pending cancellation, before the paid period runs out."""
    subscription = await _existing_live_subscription(db, org_id)
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No subscription to reactivate"
        )
    if not subscription.cancel_at_period_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This subscription is not scheduled to cancel",
        )

    if subscription.stripe_subscription_id:
        import asyncio
        import stripe

        await asyncio.to_thread(
            stripe.Subscription.modify,
            subscription.stripe_subscription_id,
            cancel_at_period_end=False,
        )

    subscription.cancel_at_period_end = False
    subscription.canceled_at = None
    await events.record_event(
        db,
        organization_id=org_id,
        event_type=events.REACTIVATED,
        subscription=subscription,
        to_status=subscription.status,
        actor_type=events.ACTOR_USER,
        actor_id=current_user.id,
    )
    await db.commit()
    await db.refresh(subscription)
    invalidate_entitlements(org_id)

    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
    )
    return _subscription_response(subscription, result.scalar_one_or_none())
