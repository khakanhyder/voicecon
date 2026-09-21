"""Cross-tenant organization management: search, inspect, suspend, and adjust billing."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin import audit, require_platform_admin
from app.database import get_db
from app.models.agent import Agent
from app.models.call import Call, PhoneNumber
from app.models.integration import Workflow
from app.models.knowledge_base import KnowledgeBase
from app.models.subscription import (
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_TRIALING,
    LIVE_STATUSES,
    SOURCE_MANUAL,
    SOURCE_STRIPE,
    SOURCE_TRIAL,
    OrganizationEntitlementOverride,
    Subscription,
    SubscriptionEvent,
    SubscriptionPlan,
)
from app.models.user import Organization, OrganizationMember, User
from app.services.billing import catalog, events
from app.services.billing.entitlements import (
    effective_status,
    invalidate_entitlements,
    resolve_entitlements,
)

from ._common import (
    PageParams,
    iso,
    latest_subscriptions,
    like,
    paginated,
    parse_uuid,
    plans_by_id,
    subscription_view,
    utcnow,
)

router = APIRouter()

#: Ledger event for an admin pushing a trial deadline out.
TRIAL_EXTENDED = "trial_extended"

#: How many matching orgs a status filter will scan. Status is derived per row
#: (trial deadlines), so it cannot be a WHERE clause.
STATUS_FILTER_SCAN_LIMIT = 5000


async def _counts(db: AsyncSession, model, org_ids, *extra) -> Dict[Any, int]:
    if not org_ids:
        return {}
    query = (
        select(model.organization_id, func.count(model.id))
        .where(model.organization_id.in_(org_ids), *extra)
        .group_by(model.organization_id)
    )
    return {oid: int(n) for oid, n in (await db.execute(query)).all()}


async def _org_or_404(db: AsyncSession, org_id: str) -> Organization:
    org = await db.get(Organization, parse_uuid(org_id, "organization"))
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.get("/organizations")
async def list_organizations(
    search: Optional[str] = Query(None, max_length=200),
    subscription_status: Optional[str] = Query(None, alias="status"),
    suspended: Optional[bool] = None,
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    query = select(Organization, User).join(User, User.id == Organization.owner_id)
    if search:
        term = like(search.strip())
        query = query.where(
            or_(
                Organization.name.ilike(term),
                Organization.slug.ilike(term),
                User.email.ilike(term),
                User.full_name.ilike(term),
            )
        )
    if suspended is not None:
        query = query.where(Organization.is_active.is_(not suspended))
    query = query.order_by(Organization.created_at.desc())

    plans = await plans_by_id(db)
    now = utcnow()

    if subscription_status:
        rows = (await db.execute(query.limit(STATUS_FILTER_SCAN_LIMIT))).all()
        latest = await latest_subscriptions(db, [o.id for o, _ in rows])
        wanted = subscription_status.lower()
        rows = [
            r
            for r in rows
            if (effective_status(latest[r[0].id], now) if r[0].id in latest else "none") == wanted
        ]
        total = len(rows)
        rows = rows[params.offset : params.offset + params.page_size]
    else:
        total = int(
            (await db.execute(select(func.count()).select_from(query.order_by(None).subquery()))).scalar() or 0
        )
        rows = (await db.execute(query.offset(params.offset).limit(params.page_size))).all()
        latest = await latest_subscriptions(db, [o.id for o, _ in rows])

    ids = [o.id for o, _ in rows]
    members = await _counts(db, OrganizationMember, ids)
    agents = await _counts(db, Agent, ids, Agent.deleted_at.is_(None))
    numbers = await _counts(db, PhoneNumber, ids, PhoneNumber.status == "active")
    calls = await _counts(db, Call, ids, Call.created_at >= now - timedelta(days=30))

    items = [
        {
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "is_active": org.is_active,
            "created_at": iso(org.created_at),
            "owner": {"id": str(owner.id), "email": owner.email, "full_name": owner.full_name},
            "members": members.get(org.id, 0),
            "agents": agents.get(org.id, 0),
            "phone_numbers": numbers.get(org.id, 0),
            "calls_30d": calls.get(org.id, 0),
            "subscription": subscription_view(latest.get(org.id), plans, now),
        }
        for org, owner in rows
    ]
    return paginated(items, total, params)


@router.get("/organizations/{org_id}")
async def get_organization(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    org = await _org_or_404(db, org_id)
    now = utcnow()
    plans = await plans_by_id(db)
    owner = await db.get(User, org.owner_id)

    member_rows = (
        await db.execute(
            select(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .where(OrganizationMember.organization_id == org.id)
            .order_by(OrganizationMember.joined_at)
        )
    ).all()

    latest = (await latest_subscriptions(db, [org.id])).get(org.id)
    override = (
        await db.execute(
            select(OrganizationEntitlementOverride).where(OrganizationEntitlementOverride.organization_id == org.id)
        )
    ).scalar_one_or_none()

    recent_calls = (
        await db.execute(
            select(Call, Agent.name)
            .outerjoin(Agent, Agent.id == Call.agent_id)
            .where(Call.organization_id == org.id)
            .order_by(Call.created_at.desc())
            .limit(10)
        )
    ).all()
    recent_events = (
        await db.execute(
            select(SubscriptionEvent)
            .where(SubscriptionEvent.organization_id == org.id)
            .order_by(SubscriptionEvent.created_at.desc())
            .limit(20)
        )
    ).scalars().all()

    ids = [org.id]
    usage = {
        "agents": (await _counts(db, Agent, ids, Agent.deleted_at.is_(None))).get(org.id, 0),
        "phone_numbers": (await _counts(db, PhoneNumber, ids, PhoneNumber.status == "active")).get(org.id, 0),
        "workflows": (await _counts(db, Workflow, ids, Workflow.deleted_at.is_(None))).get(org.id, 0),
        "knowledge_bases": (await _counts(db, KnowledgeBase, ids)).get(org.id, 0),
        "calls_30d": (await _counts(db, Call, ids, Call.created_at >= now - timedelta(days=30))).get(org.id, 0),
    }

    try:
        ent = await resolve_entitlements(db, org.id, fresh=True)
        entitlements = {
            "status": ent.status,
            "plan_name": ent.plan_name,
            "features": sorted(ent.features),
            "limits": dict(ent.limits),
            "usage": dict(ent.usage),
        }
    except Exception:
        entitlements = None

    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "is_active": org.is_active,
        "billing_email": org.billing_email,
        "created_at": iso(org.created_at),
        "owner": {"id": str(owner.id), "email": owner.email, "full_name": owner.full_name} if owner else None,
        "members": [
            {
                "user_id": str(u.id),
                "email": u.email,
                "full_name": u.full_name,
                "role": m.role,
                "is_active": u.is_active,
                "joined_at": iso(m.joined_at),
                "last_login_at": iso(u.last_login_at),
            }
            for m, u in member_rows
        ],
        "subscription": subscription_view(latest, plans, now),
        "override": (
            {
                "overrides": override.overrides or {},
                "reason": override.reason,
                "expires_at": iso(override.expires_at),
                "active": override.expires_at is None or override.expires_at > now,
                "updated_at": iso(override.updated_at),
            }
            if override
            else None
        ),
        "entitlements": entitlements,
        "usage": usage,
        "recent_calls": [
            {
                "id": str(c.id),
                "direction": c.direction,
                "status": c.status,
                "from_number": c.from_number,
                "to_number": c.to_number,
                "agent_name": agent_name,
                "duration_seconds": c.duration_seconds,
                "created_at": iso(c.created_at),
            }
            for c, agent_name in recent_calls
        ],
        "events": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "from_status": e.from_status,
                "to_status": e.to_status,
                "actor_type": e.actor_type,
                "created_at": iso(e.created_at),
            }
            for e in recent_events
        ],
    }


class ReasonBody(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000)


@router.post("/organizations/{org_id}/suspend")
async def suspend_organization(
    org_id: str,
    body: ReasonBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Block every member from acting in this workspace, and its API keys."""
    org = await _org_or_404(db, org_id)
    if not org.is_active:
        return {"is_active": False}
    org.is_active = False
    audit(db, admin, "organization.suspend", target_type="organization", target_id=org.id,
          summary=f"Suspended {org.name}", details={"reason": body.reason}, request=request)
    await db.commit()
    invalidate_entitlements(org.id)
    return {"is_active": False}


@router.post("/organizations/{org_id}/activate")
async def activate_organization(
    org_id: str,
    body: ReasonBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    org = await _org_or_404(db, org_id)
    if org.is_active:
        return {"is_active": True}
    org.is_active = True
    audit(db, admin, "organization.activate", target_type="organization", target_id=org.id,
          summary=f"Reactivated {org.name}", details={"reason": body.reason}, request=request)
    await db.commit()
    invalidate_entitlements(org.id)
    return {"is_active": True}


class ExtendTrialBody(BaseModel):
    days: int = Field(..., ge=1, le=365)
    reason: Optional[str] = Field(None, max_length=1000)


@router.post("/organizations/{org_id}/extend-trial")
async def extend_trial(
    org_id: str,
    body: ExtendTrialBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Push the trial end out by ``days`` — from today if it already lapsed.

    Revives a trial the reconciler already expired. Side effects it ran at
    expiry (paused scheduled workflows, released pooled numbers) are not undone.
    """
    org = await _org_or_404(db, org_id)
    sub = (await latest_subscriptions(db, [org.id])).get(org.id)
    if sub is None or sub.source != SOURCE_TRIAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This organization is not on a free trial. Use 'Grant plan' or an entitlement override instead.",
        )
    now = utcnow()
    if sub.status not in (STATUS_TRIALING, "grace", STATUS_EXPIRED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot extend a trial in status '{sub.status}'.")

    if sub.status == STATUS_EXPIRED:
        # Reviving must not collide with another live row (partial unique index).
        other_live = (
            await db.execute(
                select(Subscription.id).where(
                    Subscription.organization_id == org.id,
                    Subscription.id != sub.id,
                    Subscription.status.in_(LIVE_STATUSES),
                )
            )
        ).first()
        if other_live:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The organization already has another live subscription.")

    before_status, before_end = sub.status, sub.trial_end
    start_from = max(now, sub.trial_end or now)
    sub.trial_end = start_from + timedelta(days=body.days)
    sub.current_period_end = max(sub.current_period_end or now, sub.trial_end)
    sub.status = STATUS_TRIALING
    sub.grace_period_end = None
    sub.expired_at = None

    await events.record_event(
        db, organization_id=org.id, event_type=TRIAL_EXTENDED,
        subscription=sub, from_status=before_status, to_status=STATUS_TRIALING,
        actor_type=events.ACTOR_ADMIN, actor_id=admin.id,
        payload={"days": body.days, "reason": body.reason, "previous_trial_end": iso(before_end)},
    )
    audit(db, admin, "organization.extend_trial", target_type="organization", target_id=org.id,
          summary=f"Extended {org.name}'s trial by {body.days} day(s) to {sub.trial_end:%Y-%m-%d}",
          details={"reason": body.reason, "previous_trial_end": iso(before_end), "trial_end": iso(sub.trial_end)},
          request=request)
    await db.commit()
    invalidate_entitlements(org.id)
    return {"trial_end": iso(sub.trial_end), "status": STATUS_TRIALING}


class GrantPlanBody(BaseModel):
    plan_id: str
    reason: Optional[str] = Field(None, max_length=1000)


@router.post("/organizations/{org_id}/grant-plan")
async def grant_plan(
    org_id: str,
    body: GrantPlanBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Put the organization on a plan at no charge (a manual subscription).

    Refused for a live Stripe subscription — changing that here would disagree
    with what Stripe bills. The comp renews monthly until ended.
    """
    org = await _org_or_404(db, org_id)
    plan = await db.get(SubscriptionPlan, parse_uuid(body.plan_id, "plan"))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    now = utcnow()
    sub = (await latest_subscriptions(db, [org.id])).get(org.id)
    live = sub is not None and sub.status in LIVE_STATUSES
    if live and sub.source == SOURCE_STRIPE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This organization pays through Stripe. Change or cancel the subscription in Stripe first.",
        )

    before = {"status": sub.status, "source": sub.source, "plan_id": str(sub.plan_id)} if sub else None
    if live:
        from_plan = sub.plan_id
        if sub.source == SOURCE_TRIAL:
            sub.trial_converted_at = now
    else:
        from_plan = sub.plan_id if sub else None
        sub = Subscription(organization_id=org.id, billing_period="monthly")
        db.add(sub)

    sub.plan_id = plan.id
    sub.source = SOURCE_MANUAL
    sub.status = STATUS_ACTIVE
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=30)
    sub.grace_period_end = None
    sub.expired_at = None
    sub.cancel_at_period_end = False
    sub.scheduled_plan_id = None
    await db.flush()

    await events.record_event(
        db, organization_id=org.id, event_type=events.ACTIVATED, subscription=sub,
        from_status=before["status"] if before else None, to_status=STATUS_ACTIVE,
        from_plan_id=from_plan, to_plan_id=plan.id,
        actor_type=events.ACTOR_ADMIN, actor_id=admin.id, payload={"reason": body.reason, "comp": True},
    )
    audit(db, admin, "organization.grant_plan", target_type="organization", target_id=org.id,
          summary=f"Granted {plan.name} to {org.name} at no charge",
          details={"reason": body.reason, "plan": plan.slug, "before": before}, request=request)
    await db.commit()
    invalidate_entitlements(org.id)
    return {"status": STATUS_ACTIVE, "plan": {"id": str(plan.id), "name": plan.name}}


@router.post("/organizations/{org_id}/end-manual-plan")
async def end_manual_plan(
    org_id: str,
    body: ReasonBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    org = await _org_or_404(db, org_id)
    sub = (await latest_subscriptions(db, [org.id])).get(org.id)
    if sub is None or sub.source != SOURCE_MANUAL or sub.status not in LIVE_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active complimentary plan to end.")
    now = utcnow()
    before = sub.status
    sub.status = STATUS_EXPIRED
    sub.expired_at = now
    sub.ended_at = now
    await events.record_event(
        db, organization_id=org.id, event_type=events.CANCELED, subscription=sub,
        from_status=before, to_status=STATUS_EXPIRED,
        actor_type=events.ACTOR_ADMIN, actor_id=admin.id, payload={"reason": body.reason},
    )
    audit(db, admin, "organization.end_manual_plan", target_type="organization", target_id=org.id,
          summary=f"Ended complimentary plan for {org.name}", details={"reason": body.reason}, request=request)
    await db.commit()
    invalidate_entitlements(org.id)
    return {"status": STATUS_EXPIRED}


class OverrideBody(BaseModel):
    features: Dict[str, bool] = Field(default_factory=dict)
    limits: Dict[str, int] = Field(default_factory=dict)
    reason: Optional[str] = Field(None, max_length=1000)
    expires_at: Optional[datetime] = None


@router.put("/organizations/{org_id}/override")
async def set_override(
    org_id: str,
    body: OverrideBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Grant (or withhold) individual features and limits on top of the plan."""
    org = await _org_or_404(db, org_id)
    unknown = [k for k in body.features if k not in catalog.ALL_FEATURES]
    unknown += [k for k in body.limits if k not in catalog.LIMIT_LABELS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown feature or limit: {', '.join(unknown)}")
    if any(v < catalog.UNLIMITED for v in body.limits.values()):
        raise HTTPException(status_code=422, detail="Limits must be -1 (unlimited) or a positive number.")
    expires_at = body.expires_at.replace(tzinfo=None) if body.expires_at else None

    document: Dict[str, Any] = {}
    if body.features:
        document["features"] = body.features
    if body.limits:
        document["limits"] = body.limits

    row = (
        await db.execute(
            select(OrganizationEntitlementOverride).where(OrganizationEntitlementOverride.organization_id == org.id)
        )
    ).scalar_one_or_none()
    before = row.overrides if row else None

    if not document:
        if row is not None:
            await db.delete(row)
    else:
        if row is None:
            row = OrganizationEntitlementOverride(organization_id=org.id)
            db.add(row)
        row.overrides = document
        row.reason = body.reason
        row.expires_at = expires_at
        row.created_by = admin.id

    audit(db, admin, "organization.override", target_type="organization", target_id=org.id,
          summary=f"{'Updated' if document else 'Removed'} entitlement override for {org.name}",
          details={"before": before, "after": document or None, "reason": body.reason, "expires_at": iso(expires_at)},
          request=request)
    await db.commit()
    invalidate_entitlements(org.id)
    return {"overrides": document or None, "expires_at": iso(expires_at)}


@router.post("/organizations/{org_id}/reset-usage")
async def reset_usage(
    org_id: str,
    body: ReasonBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    org = await _org_or_404(db, org_id)
    sub = (await latest_subscriptions(db, [org.id])).get(org.id)
    if sub is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No subscription to reset.")
    before = {
        "minutes": sub.current_period_minutes,
        "calls": sub.current_period_calls,
        "sms": sub.current_period_sms,
        "emails": sub.current_period_emails,
    }
    sub.current_period_minutes = 0
    sub.current_period_calls = 0
    sub.current_period_sms = 0
    sub.current_period_emails = 0
    audit(db, admin, "organization.reset_usage", target_type="organization", target_id=org.id,
          summary=f"Reset this period's usage counters for {org.name}",
          details={"before": before, "reason": body.reason}, request=request)
    await db.commit()
    invalidate_entitlements(org.id)
    return {"usage": {"minutes": 0, "calls": 0, "sms": 0, "emails": 0}}


@router.get("/catalog")
async def entitlement_catalog(_admin=Depends(require_platform_admin)):
    """Feature and limit keys, with labels, for the override and plan editors."""
    return {
        "features": [{"key": k, "label": catalog.FEATURE_LABELS.get(k, k)} for k in catalog.ALL_FEATURES],
        "limits": [{"key": k, "label": v} for k, v in catalog.LIMIT_LABELS.items()],
        "unlimited": catalog.UNLIMITED,
    }
