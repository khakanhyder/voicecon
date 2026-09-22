"""Plans, payment failures, the billing ledger, and the reconciler."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin import audit, require_platform_admin
from app.core.config import settings
from app.database import get_db
from app.models.subscription import (
    LIVE_STATUSES,
    Invoice,
    PaymentFailure,
    Subscription,
    SubscriptionEvent,
    SubscriptionPlan,
)
from app.models.user import Organization
from app.services.billing import catalog
from app.services.billing.entitlements import get_entitlement_service

from ._common import PageParams, iso, num, paginated, parse_uuid, utcnow

router = APIRouter()


def _plan_view(plan: SubscriptionPlan, subscribers: int = 0) -> Dict[str, Any]:
    document = plan.entitlements or {}
    return {
        "id": str(plan.id),
        "slug": plan.slug,
        "name": plan.name,
        "description": plan.description,
        "tier": plan.tier,
        "price_monthly": num(plan.price_monthly),
        "price_yearly": num(plan.price_yearly),
        "currency": plan.currency,
        "stripe_product_id": plan.stripe_product_id,
        "stripe_price_id": plan.stripe_price_id,
        "stripe_price_id_yearly": plan.stripe_price_id_yearly,
        "polar_product_id": plan.polar_product_id,
        "polar_product_id_yearly": plan.polar_product_id_yearly,
        "trial_days": plan.trial_days,
        "is_trialable": plan.is_trialable,
        "is_active": plan.is_active,
        "is_public": plan.is_public,
        "sort_order": plan.sort_order,
        "admin_managed": plan.admin_managed,
        "highlights": list((plan.features or {}).get("highlights") or []),
        "features": dict(document.get("features") or {}),
        "limits": dict(document.get("limits") or {}),
        "subscribers": subscribers,
        "created_at": iso(plan.created_at),
    }


@router.get("/plans")
async def list_plans(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    plans = (
        await db.execute(select(SubscriptionPlan).order_by(SubscriptionPlan.sort_order, SubscriptionPlan.tier))
    ).scalars().all()
    counts = {
        pid: int(n)
        for pid, n in (
            await db.execute(
                select(Subscription.plan_id, func.count(Subscription.id))
                .where(Subscription.status.in_(LIVE_STATUSES))
                .group_by(Subscription.plan_id)
            )
        ).all()
    }
    from app.services.billing import providers

    return {
        "plans": [_plan_view(p, counts.get(p.id, 0)) for p in plans],
        "stripe_configured": settings.stripe_configured,
        "polar_configured": settings.polar_configured,
        "payment_provider": providers.active_provider(),
    }


class TrialLength(BaseModel):
    days: int = Field(..., ge=1, le=365)


@router.put("/plans/trial")
async def set_trial_length(
    body: TrialLength,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Set the free-trial length on every plan at once.

    A trial runs on whichever trialable plan it is started on, so one value for
    all plans is what "the trial length" means to an operator. Written to every
    row (trialable or not) so a plan made trialable later already agrees. Not
    marked ``admin_managed``: the seed job no longer touches ``trial_days``, and
    flagging the rows would also stop their entitlement backfills. Trials that
    already started keep their end date; use Extend trial on an organization.
    """
    plans = (await db.execute(select(SubscriptionPlan))).scalars().all()
    before = sorted({p.trial_days for p in plans})
    for plan in plans:
        plan.trial_days = body.days
    audit(db, admin, "plan.trial_length", target_type="plan",
          summary=f"Set the free trial to {body.days} days on all plans",
          details={"before": before, "after": body.days}, request=request)
    await db.commit()
    get_entitlement_service().invalidate_all()
    return {"days": body.days, "plans_updated": len(plans)}


class PlanPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    price_monthly: Optional[Decimal] = Field(None, ge=0)
    price_yearly: Optional[Decimal] = Field(None, ge=0)
    trial_days: Optional[int] = Field(None, ge=1, le=365)
    is_trialable: Optional[bool] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    sort_order: Optional[int] = None
    highlights: Optional[List[str]] = None
    features: Optional[Dict[str, bool]] = None
    limits: Optional[Dict[str, int]] = None
    #: Polar product ids; an empty string clears one.
    polar_product_id: Optional[str] = Field(None, max_length=255)
    polar_product_id_yearly: Optional[str] = Field(None, max_length=255)


async def _sync_stripe_price(plan: SubscriptionPlan, interval: str, amount: Decimal) -> Optional[str]:
    """Create (or find) the Stripe price for a new amount. None when Stripe is
    not set up or the product does not exist yet — checkout creates it then."""
    if not settings.stripe_configured or not (plan.stripe_product_id or "").startswith("prod_"):
        return None
    from app.services.billing.stripe_service import get_stripe_service

    service = await get_stripe_service()
    return await service.get_or_create_price(
        product_id=plan.stripe_product_id,
        unit_amount_cents=int(Decimal(amount) * 100),
        interval=interval,
        currency=plan.currency or "usd",
    )


@router.patch("/plans/{plan_id}")
async def update_plan(
    plan_id: str,
    body: PlanPatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    plan = await db.get(SubscriptionPlan, parse_uuid(plan_id, "plan"))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return _plan_view(plan)

    unknown = [k for k in (changes.get("features") or {}) if k not in catalog.ALL_FEATURES]
    unknown += [k for k in (changes.get("limits") or {}) if k not in catalog.LIMIT_LABELS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown feature or limit: {', '.join(unknown)}")
    if any(v < catalog.UNLIMITED for v in (changes.get("limits") or {}).values()):
        raise HTTPException(status_code=422, detail="Limits must be -1 (unlimited) or a positive number.")

    before = _plan_view(plan)

    from app.services.billing import polar_service

    for key in ("polar_product_id", "polar_product_id_yearly"):
        if key in changes:
            value = (changes[key] or "").strip() or None
            if value:
                clash = (
                    await db.execute(
                        select(SubscriptionPlan.id).where(
                            SubscriptionPlan.id != plan.id,
                            (SubscriptionPlan.polar_product_id == value)
                            | (SubscriptionPlan.polar_product_id_yearly == value),
                        )
                    )
                ).first()
                other = plan.polar_product_id_yearly if key == "polar_product_id" else plan.polar_product_id
                other = changes.get("polar_product_id_yearly" if key == "polar_product_id" else "polar_product_id", other)
                if clash or (other and other.strip() == value):
                    raise HTTPException(status_code=422, detail="Each Polar product can belong to only one plan and one billing period.")
            setattr(plan, key, value)

    # Prices first: a Stripe failure must leave the row untouched.
    try:
        if "price_monthly" in changes and Decimal(changes["price_monthly"]) != Decimal(plan.price_monthly):
            price_id = await _sync_stripe_price(plan, "month", changes["price_monthly"])
            if price_id:
                plan.stripe_price_id = price_id
            plan.price_monthly = changes["price_monthly"]
        if "price_yearly" in changes and changes["price_yearly"] != plan.price_yearly:
            if changes["price_yearly"]:
                price_id = await _sync_stripe_price(plan, "year", changes["price_yearly"])
                if price_id:
                    plan.stripe_price_id_yearly = price_id
            plan.price_yearly = changes["price_yearly"]
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe rejected the new price, so nothing was changed: {type(exc).__name__}",
        )

    # Polar products carry their own price. Push a changed price there too, so
    # new Polar checkouts charge what the pricing page shows.
    if settings.polar_configured:
        try:
            if "price_monthly" in changes and plan.polar_product_id and before["price_monthly"] != num(plan.price_monthly):
                await polar_service.push_price(plan.polar_product_id, plan.price_monthly, plan.currency)
            if "price_yearly" in changes and plan.polar_product_id_yearly and plan.price_yearly and before["price_yearly"] != num(plan.price_yearly):
                await polar_service.push_price(plan.polar_product_id_yearly, plan.price_yearly, plan.currency)
        except polar_service.PolarError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Polar rejected the new price, so nothing was changed. {exc.detail or exc.public_message}",
            )

    for key in ("name", "description", "trial_days", "is_trialable", "is_active", "is_public", "sort_order"):
        if key in changes:
            setattr(plan, key, changes[key])

    if "highlights" in changes:
        features = dict(plan.features or {})
        features["highlights"] = [h.strip() for h in changes["highlights"] if h and h.strip()]
        plan.features = features  # JSON column: reassign

    if "features" in changes or "limits" in changes:
        document = dict(plan.entitlements or {})
        if "features" in changes:
            document["features"] = {**dict(document.get("features") or {}), **changes["features"]}
        if "limits" in changes:
            limits = {**dict(document.get("limits") or {}), **changes["limits"]}
            document["limits"] = limits
            # Keep the legacy columns (pricing copy, seed backfill) in step.
            plan.max_agents = limits.get(catalog.LIMIT_AGENTS, plan.max_agents)
            plan.max_phone_numbers = limits.get(catalog.LIMIT_PHONE_NUMBERS, plan.max_phone_numbers)
            plan.max_knowledge_bases = limits.get(catalog.LIMIT_KNOWLEDGE_BASES, plan.max_knowledge_bases)
        plan.entitlements = document

    # From now on the startup backfill leaves this row alone.
    plan.admin_managed = True

    after = _plan_view(plan)
    diff = {k: {"before": before[k], "after": after[k]} for k in after if before.get(k) != after[k] and k != "admin_managed"}
    audit(db, admin, "plan.update", target_type="plan", target_id=plan.id,
          summary=f"Edited plan {plan.name}: {', '.join(sorted(diff)) or 'no changes'}",
          details=diff, request=request)
    await db.commit()
    # Every org on this plan resolves from the row we just changed.
    get_entitlement_service().invalidate_all()
    return _plan_view(plan)


@router.post("/plans/{plan_id}/polar-sync")
async def sync_plan_to_polar(
    plan_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Create this plan's Polar products (monthly, and yearly when priced), or
    refresh their name and price when they already exist."""
    from app.services.billing import polar_service

    plan = await db.get(SubscriptionPlan, parse_uuid(plan_id, "plan"))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    if not settings.polar_configured:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Add the Polar access token under API Keys & Providers first.")

    before = {"monthly": plan.polar_product_id, "yearly": plan.polar_product_id_yearly}
    try:
        products = await polar_service.sync_plan_products(plan)
    except polar_service.PolarError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{exc.public_message} {exc.detail}".strip(),
        )
    plan.polar_product_id = products.get("monthly") or plan.polar_product_id
    plan.polar_product_id_yearly = products.get("yearly") or plan.polar_product_id_yearly
    audit(db, admin, "plan.polar_sync", target_type="plan", target_id=plan.id,
          summary=f"Synced plan {plan.name} to Polar",
          details={"before": before, "after": products}, request=request)
    await db.commit()
    return _plan_view(plan)


@router.get("/billing/payment-failures")
async def list_payment_failures(
    resolved: bool = False,
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    query = (
        select(PaymentFailure, Organization.name, Invoice)
        .join(Organization, Organization.id == PaymentFailure.organization_id)
        .outerjoin(Invoice, Invoice.id == PaymentFailure.invoice_id)
        .where(PaymentFailure.resolved.is_(resolved))
    )
    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0)
    rows = (
        await db.execute(query.order_by(PaymentFailure.created_at.desc()).offset(params.offset).limit(params.page_size))
    ).all()
    items = [
        {
            "id": str(f.id),
            "organization_id": str(f.organization_id),
            "organization_name": org_name,
            "failure_code": f.failure_code,
            "failure_message": f.failure_message,
            "amount_due": num(inv.amount_due) if inv else None,
            "currency": inv.currency if inv else None,
            "hosted_invoice_url": inv.hosted_invoice_url if inv else None,
            "customer_notified": f.customer_notified,
            "resolved": f.resolved,
            "resolved_at": iso(f.resolved_at),
            "resolution_notes": f.resolution_notes,
            "created_at": iso(f.created_at),
        }
        for f, org_name, inv in rows
    ]
    return paginated(items, total, params)


class ResolveBody(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


@router.post("/billing/payment-failures/{failure_id}/resolve")
async def resolve_payment_failure(
    failure_id: str,
    body: ResolveBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    failure = await db.get(PaymentFailure, parse_uuid(failure_id, "payment failure"))
    if failure is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment failure not found")
    failure.resolved = True
    failure.resolved_at = utcnow()
    failure.resolution_notes = body.notes
    audit(db, admin, "payment_failure.resolve", target_type="organization", target_id=failure.organization_id,
          summary="Marked a payment failure resolved", details={"failure_id": failure_id, "notes": body.notes},
          request=request)
    await db.commit()
    return {"resolved": True}


@router.get("/billing/events")
async def list_billing_events(
    organization_id: Optional[str] = None,
    event_type: Optional[str] = Query(None, max_length=50),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    query = select(SubscriptionEvent, Organization.name).join(
        Organization, Organization.id == SubscriptionEvent.organization_id
    )
    if organization_id:
        query = query.where(SubscriptionEvent.organization_id == parse_uuid(organization_id, "organization"))
    if event_type:
        query = query.where(SubscriptionEvent.event_type == event_type)
    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0)
    rows = (
        await db.execute(
            query.order_by(SubscriptionEvent.created_at.desc()).offset(params.offset).limit(params.page_size)
        )
    ).all()
    items = [
        {
            "id": str(e.id),
            "organization_id": str(e.organization_id),
            "organization_name": name,
            "event_type": e.event_type,
            "from_status": e.from_status,
            "to_status": e.to_status,
            "actor_type": e.actor_type,
            "stripe_event_id": e.stripe_event_id,
            "created_at": iso(e.created_at),
        }
        for e, name in rows
    ]
    return paginated(items, total, params)


@router.post("/billing/reconcile")
async def run_reconciler(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Run the subscription sweep now instead of waiting for the 15-minute tick."""
    from app.services.billing.reconciler import reconcile_subscriptions

    report = await reconcile_subscriptions(db)
    audit(db, admin, "billing.reconcile", summary=f"Ran billing reconciler: {report}", request=request)
    await db.commit()
    return {"report": str(report), "changed": report.changed}
