"""Affiliate program administration: partners, program rules, commissions, payouts."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin import audit, require_platform_admin
from app.database import get_db
from app.models.affiliate import (
    AFFILIATE_ACTIVE,
    AFFILIATE_INVITED,
    AFFILIATE_SUSPENDED,
    COMMISSION_APPROVED,
    COMMISSION_PENDING,
    COMMISSION_REJECTED,
    DISCOUNT_ONCE,
    DISCOUNT_REPEATING,
    DISCOUNT_YEARLY_ONLY,
    KIND_ADJUSTMENT,
    Affiliate,
    AffiliateCommission,
    AffiliatePayout,
    AffiliateReferral,
)
from app.models.subscription import SubscriptionPlan
from app.models.user import Organization, OrganizationMember, User
from app.services.affiliates import commissions, invites, payouts, views
from app.services.affiliates.program import (
    coupon_code_problem,
    get_program,
    money,
    normalize_coupon_code,
    normalize_referral_code,
    referral_code_problem,
    unique_coupon_code,
    unique_referral_code,
)
from app.services.auth.verification import normalize_email
from app.services.auth.workspaces import unique_org_slug
from app.services.billing import providers

from ._common import PageParams, iso, like, paginated, parse_uuid, utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/affiliates")

# ==================== Program rules ====================


class ProgramUpdate(BaseModel):
    enabled: bool
    default_commission_percent: Decimal = Field(ge=0, le=100)
    hold_days: int = Field(ge=0, le=365)
    min_payout_amount: Decimal = Field(ge=0, le=100000)
    cookie_days: int = Field(ge=1, le=365)
    referral_window_days: Optional[int] = Field(None, ge=1, le=3650)
    max_commission_payments: Optional[int] = Field(None, ge=1, le=100)
    max_monthly_commission_payments: Optional[int] = Field(None, ge=1, le=240)
    eligible_plan_slugs: List[str] = Field(default_factory=list, max_length=50)


def _program_view(program, plans: List[SubscriptionPlan]) -> dict:
    return {
        "enabled": program.enabled,
        "default_commission_percent": float(program.default_commission_percent),
        "hold_days": program.hold_days,
        "min_payout_amount": float(program.min_payout_amount),
        "cookie_days": program.cookie_days,
        "referral_window_days": program.referral_window_days,
        "max_commission_payments": program.max_commission_payments,
        "max_monthly_commission_payments": program.max_monthly_commission_payments,
        "eligible_plan_slugs": list(program.eligible_plan_slugs or []),
        # Retired plans still listed as eligible stay visible, so saving the
        # form never silently drops them.
        "plans": [
            {"slug": p.slug, "name": p.name, "has_yearly": bool(p.price_yearly), "is_active": p.is_active}
            for p in plans
            if p.slug and (p.is_active or p.slug in (program.eligible_plan_slugs or []))
        ],
        "stripe_connect_ready": payouts.connect_ready(),
        "payment_provider": providers.active_provider(),
        "updated_at": iso(program.updated_at),
    }


async def _plans(db: AsyncSession) -> List[SubscriptionPlan]:
    return list(
        (await db.execute(select(SubscriptionPlan).order_by(SubscriptionPlan.sort_order))).scalars().all()
    )


@router.get("/program")
async def get_program_rules(db: AsyncSession = Depends(get_db)):
    program = await get_program(db)
    await db.commit()
    return _program_view(program, await _plans(db))


@router.put("/program")
async def update_program_rules(
    body: ProgramUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    program = await get_program(db)
    plans = await _plans(db)
    known = {p.slug for p in plans if p.slug}
    unknown = [s for s in body.eligible_plan_slugs if s not in known]
    if unknown:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown plan(s): {', '.join(unknown)}")
    before = _program_view(program, plans)
    for field, value in body.model_dump().items():
        setattr(program, field, value)
    program.updated_by = admin.id
    audit(
        db, admin, "affiliate_program.update", target_type="affiliate_program", target_id=1,
        summary="Updated affiliate program rules",
        details={"before": {k: before[k] for k in body.model_dump()}, "after": body.model_dump(mode="json")},
        request=request,
    )
    await db.commit()
    return _program_view(program, plans)


# ==================== Affiliates ====================


class AffiliateTerms(BaseModel):
    """Fields shared by create and update."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    #: Which payments earn: yearly only, monthly only, or both.
    commission_billing_periods: Optional[Literal["yearly", "monthly", "both"]] = None
    #: Rate on yearly payments.
    commission_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    #: Rate on monthly payments; null = same as ``commission_percent``.
    commission_percent_monthly: Optional[Decimal] = Field(None, ge=0, le=100)
    referral_code: Optional[str] = Field(None, max_length=40)
    coupon_code: Optional[str] = Field(None, max_length=40)
    discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    discount_applies_to: Optional[Literal["yearly", "all"]] = None
    discount_duration: Optional[Literal["once", "forever", "repeating"]] = None
    discount_duration_months: Optional[int] = Field(None, ge=1, le=36)
    custom_max_payments: Optional[bool] = None
    max_commission_payments: Optional[int] = Field(None, ge=1, le=100)
    max_monthly_commission_payments: Optional[int] = Field(None, ge=1, le=240)
    notes: Optional[str] = Field(None, max_length=5000)


class AffiliateCreate(AffiliateTerms):
    email: str = Field(..., min_length=3, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    send_invite: bool = True

    @model_validator(mode="after")
    def _email_shape(self):
        if "@" not in self.email:
            raise ValueError("Enter a valid email address.")
        return self


class AffiliateUpdate(AffiliateTerms):
    #: Clear the coupon entirely (``coupon_code: null`` alone means "unchanged").
    remove_coupon: bool = False


def _bad(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


async def _check_codes(db: AsyncSession, affiliate: Optional[Affiliate], referral: Optional[str], coupon: Optional[str]):
    """Refuse malformed codes, and codes another affiliate holds in either role.

    Links and coupons are looked up in both columns (``find_by_code``), so a
    referral code may not collide with someone else's coupon either.
    """
    own_id = affiliate.id if affiliate else None
    for code, problem, label in (
        (referral, referral_code_problem(referral) if referral is not None else None, "referral code"),
        (coupon, coupon_code_problem(coupon) if coupon is not None else None, "coupon code"),
    ):
        if code is None:
            continue
        if problem:
            raise _bad(problem)
        query = select(Affiliate.id).where(
            or_(
                Affiliate.referral_code == normalize_referral_code(code),
                Affiliate.coupon_code == normalize_coupon_code(code),
            )
        )
        if own_id is not None:
            query = query.where(Affiliate.id != own_id)
        if await db.scalar(query.limit(1)) is not None:
            raise _bad(f"The {label} '{code}' is already used by another affiliate.")


def _apply_terms(affiliate: Affiliate, body: AffiliateTerms) -> None:
    data = body.model_dump(exclude_unset=True)
    for field in (
        "name", "company", "commission_billing_periods", "commission_percent", "discount_percent",
        "discount_applies_to", "discount_duration", "custom_max_payments", "notes",
    ):
        if field in data and data[field] is not None:
            setattr(affiliate, field, data[field])
    if "company" in data and data["company"] is not None:
        affiliate.company = data["company"].strip() or None
    if "discount_duration_months" in data:
        affiliate.discount_duration_months = data["discount_duration_months"]
    if "max_commission_payments" in data:
        affiliate.max_commission_payments = data["max_commission_payments"]
    if "max_monthly_commission_payments" in data:
        affiliate.max_monthly_commission_payments = data["max_monthly_commission_payments"]
    if "commission_percent_monthly" in data:
        affiliate.commission_percent_monthly = data["commission_percent_monthly"]
    if affiliate.discount_duration != DISCOUNT_REPEATING:
        affiliate.discount_duration_months = None
    elif not affiliate.discount_duration_months:
        raise _bad("Choose how many months a repeating discount lasts.")
    if not affiliate.custom_max_payments:
        affiliate.max_commission_payments = None
        affiliate.max_monthly_commission_payments = None


async def _affiliate_or_404(db: AsyncSession, affiliate_id: str) -> Affiliate:
    affiliate = await db.get(Affiliate, parse_uuid(affiliate_id, "affiliate"))
    if affiliate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Affiliate not found")
    return affiliate


def _affiliate_view(a: Affiliate, *, balance=None, refs=None, clicks=None) -> dict:
    return {
        "id": str(a.id),
        "user_id": str(a.user_id),
        "email": a.user.email if a.user else None,
        "name": a.name,
        "company": a.company,
        "status": a.status,
        "referral_code": a.referral_code,
        "links": views.links(a),
        "coupon": views.coupon_view(a),
        "commission_billing_periods": a.commission_billing_periods,
        "commission_percent": float(a.commission_percent),
        "commission_percent_monthly": float(a.commission_percent_monthly)
        if a.commission_percent_monthly is not None
        else None,
        "custom_max_payments": a.custom_max_payments,
        "max_commission_payments": a.max_commission_payments,
        "max_monthly_commission_payments": a.max_monthly_commission_payments,
        "discount_percent": float(a.discount_percent or 0),
        "discount_applies_to": a.discount_applies_to,
        "discount_duration": a.discount_duration,
        "discount_duration_months": a.discount_duration_months,
        "stripe": views.stripe_view(a),
        "notes": a.notes,
        "has_password": bool(a.user and a.user.hashed_password),
        "invited_at": iso(a.invited_at),
        "activated_at": iso(a.activated_at),
        "created_at": iso(a.created_at),
        "balance": views.balance_view(balance or commissions.empty_balance()),
        "stats": {
            "referrals": (refs or {}).get("referrals", 0),
            "conversions": (refs or {}).get("conversions", 0),
            "clicks": (clicks or {}).get("clicks", 0),
            "clicks_30d": (clicks or {}).get("clicks_30d", 0),
        },
    }


async def _full_view(db: AsyncSession, a: Affiliate) -> dict:
    balance = (await commissions.balances(db, [a.id])).get(a.id)
    refs = (await commissions.referral_stats(db, [a.id])).get(a.id)
    clicks = (await views.click_counts(db, [a.id])).get(a.id)
    view = _affiliate_view(a, balance=balance, refs=refs, clicks=clicks)
    program = await get_program(db)
    available = Decimal(str(view["balance"]["available"]))
    in_flight = await db.scalar(
        select(func.count()).where(AffiliatePayout.affiliate_id == a.id, AffiliatePayout.status == "processing")
    )
    view["payout"] = {
        "available": float(available),
        "min_payout_amount": float(program.min_payout_amount),
        "meets_minimum": available >= Decimal(program.min_payout_amount),
        "stripe_ready": payouts.connect_state(a) == "ready",
        "processing": int(in_flight or 0),
    }
    return view


@router.get("")
async def list_affiliates(
    search: Optional[str] = Query(None, max_length=200),
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(invited|active|suspended)$"),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    await commissions.mature(db)
    await db.commit()
    query = select(Affiliate).join(User, User.id == Affiliate.user_id)
    if search:
        term = like(search.strip())
        query = query.where(
            or_(
                Affiliate.name.ilike(term),
                Affiliate.company.ilike(term),
                User.email.ilike(term),
                Affiliate.referral_code.ilike(term),
                Affiliate.coupon_code.ilike(term),
            )
        )
    if status_filter:
        query = query.where(Affiliate.status == status_filter)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await db.execute(query.order_by(Affiliate.created_at.desc()).offset(params.offset).limit(params.page_size))
    ).scalars().all()
    ids = [a.id for a in rows]
    balances = await commissions.balances(db, ids)
    refs = await commissions.referral_stats(db, ids)
    clicks = await views.click_counts(db, ids)
    items = [
        _affiliate_view(a, balance=balances.get(a.id), refs=refs.get(a.id), clicks=clicks.get(a.id)) for a in rows
    ]
    return paginated(items, total or 0, params)


async def _user_for_new_affiliate(db: AsyncSession, email: str, name: str) -> User:
    """The login for a new affiliate: an existing account, or a new one with its own workspace.

    A new account gets a personal workspace like every other sign-up, so the
    same person can later use the product without hitting "no workspace".
    """
    user = await db.scalar(select(User).where(User.email == email))
    if user is not None:
        if not user.is_active or user.deleted_at is not None:
            raise _bad("That account is disabled. Re-enable it or use another email address.")
        return user
    user = User(email=email, hashed_password=None, full_name=name, auth_provider="email", is_verified=False)
    db.add(user)
    await db.flush()
    organization = Organization(
        name=f"{name}'s Workspace", slug=await unique_org_slug(db, email), owner_id=user.id
    )
    db.add(organization)
    await db.flush()
    db.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    return user


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_affiliate(
    body: AffiliateCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    email = normalize_email(body.email)
    name = body.name.strip()
    program = await get_program(db)

    referral = normalize_referral_code(body.referral_code) or await unique_referral_code(db, name)
    discount = Decimal(body.discount_percent or 0)
    coupon = normalize_coupon_code(body.coupon_code) or None
    if discount > 0 and coupon is None:
        coupon = await unique_coupon_code(db, referral)
    await _check_codes(db, None, referral, coupon)

    user = await _user_for_new_affiliate(db, email, name)
    if await db.scalar(select(Affiliate.id).where(Affiliate.user_id == user.id)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This person is already an affiliate.")

    affiliate = Affiliate(
        user_id=user.id,
        name=name,
        status=AFFILIATE_INVITED,
        referral_code=referral,
        coupon_code=coupon,
        commission_percent=body.commission_percent
        if body.commission_percent is not None
        else program.default_commission_percent,
        commission_billing_periods=body.commission_billing_periods or "yearly",
        discount_applies_to=body.discount_applies_to or DISCOUNT_YEARLY_ONLY,
        discount_duration=body.discount_duration or DISCOUNT_ONCE,
        custom_max_payments=bool(body.custom_max_payments),
        created_by=admin.id,
    )
    _apply_terms(affiliate, body)
    affiliate.discount_percent = discount if discount > 0 else None
    db.add(affiliate)
    await db.flush()
    await db.refresh(affiliate, ["user"])

    invite_link = invites.invite_url(affiliate)
    if body.send_invite:
        affiliate.invited_at = utcnow()
    audit(
        db, admin, "affiliate.create", target_type="affiliate", target_id=affiliate.id,
        summary=(
            f"Created affiliate {name} <{email}> at {float(affiliate.commission_percent):g}% "
            f"({affiliate.commission_billing_periods} payments)"
        ),
        details={"referral_code": referral, "coupon_code": coupon, "discount_percent": float(discount)},
        request=request,
    )
    await db.commit()
    sent = await invites.send_invite(affiliate) if body.send_invite else False
    view = await _full_view(db, affiliate)
    view["invite_url"] = invite_link
    view["invite_sent"] = sent
    return view


# Static sub-paths are declared before ``/{affiliate_id}`` so they are not
# swallowed by it.


@router.get("/commissions")
async def list_commissions(
    affiliate_id: Optional[str] = None,
    status_filter: Optional[str] = Query(
        None, alias="status", pattern="^(pending|approved|paid|reversed|rejected)$"
    ),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    await commissions.mature(db)
    await db.commit()
    query = select(AffiliateCommission)
    if affiliate_id:
        query = query.where(AffiliateCommission.affiliate_id == parse_uuid(affiliate_id, "affiliate"))
    if status_filter:
        query = query.where(AffiliateCommission.status == status_filter)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await db.execute(
            query.order_by(AffiliateCommission.earned_at.desc()).offset(params.offset).limit(params.page_size)
        )
    ).scalars().all()
    affiliates = {
        a.id: a
        for a in (
            await db.execute(select(Affiliate).where(Affiliate.id.in_({c.affiliate_id for c in rows})))
        ).scalars().all()
    }
    org_names = dict(
        (
            await db.execute(
                select(Organization.id, Organization.name).where(
                    Organization.id.in_({c.organization_id for c in rows if c.organization_id})
                )
            )
        ).all()
    )
    customers = dict(
        (
            await db.execute(
                select(AffiliateReferral.id, User.email)
                .join(User, User.id == AffiliateReferral.user_id)
                .where(AffiliateReferral.id.in_({c.referral_id for c in rows if c.referral_id}))
            )
        ).all()
    )
    items = [
        views.commission_view(
            c,
            customer=customers.get(c.referral_id),
            extra={
                "affiliate_id": str(c.affiliate_id),
                "affiliate_name": affiliates[c.affiliate_id].name if c.affiliate_id in affiliates else None,
                "organization_id": str(c.organization_id) if c.organization_id else None,
                "organization_name": org_names.get(c.organization_id),
                "external_ref": c.external_ref,
            },
        )
        for c in rows
    ]
    return paginated(items, total or 0, params)


class AdjustmentCreate(BaseModel):
    affiliate_id: str
    amount: Decimal = Field(..., ge=-100000, le=100000)
    note: str = Field(..., min_length=3, max_length=2000)


@router.post("/commissions", status_code=status.HTTP_201_CREATED)
async def create_adjustment(
    body: AdjustmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """A manual credit or debit — e.g. a commission a webhook missed. Payable at once."""
    affiliate = await _affiliate_or_404(db, body.affiliate_id)
    amount = money(body.amount)
    if amount == 0:
        raise _bad("Enter a non-zero amount.")
    now = utcnow()
    row = AffiliateCommission(
        affiliate_id=affiliate.id,
        kind=KIND_ADJUSTMENT,
        provider="manual",
        base_amount=Decimal("0"),
        rate_percent=Decimal("0"),
        amount=amount,
        original_amount=amount,
        currency="usd",
        status=COMMISSION_APPROVED,
        earned_at=now,
        available_at=now,
        approved_at=now,
        note=body.note.strip(),
        created_by=admin.id,
    )
    db.add(row)
    await db.flush()
    audit(
        db, admin, "affiliate_commission.adjust", target_type="affiliate", target_id=affiliate.id,
        summary=f"Adjustment of {amount} for {affiliate.name}", details={"note": row.note, "commission_id": str(row.id)},
        request=request,
    )
    await db.commit()
    return views.commission_view(row)


async def _commission_or_404(db: AsyncSession, commission_id: str) -> AffiliateCommission:
    row = await db.get(AffiliateCommission, parse_uuid(commission_id, "commission"))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commission not found")
    return row


@router.post("/commissions/{commission_id}/approve")
async def approve_commission(
    commission_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Skip the rest of the hold period and make a pending commission payable now."""
    row = await _commission_or_404(db, commission_id)
    if row.status != COMMISSION_PENDING:
        raise _bad("Only a pending commission can be approved early.")
    row.status = COMMISSION_APPROVED
    row.approved_at = utcnow()
    audit(
        db, admin, "affiliate_commission.approve", target_type="affiliate_commission", target_id=row.id,
        summary=f"Approved commission {row.amount} before its hold ended", request=request,
    )
    await db.commit()
    return views.commission_view(row)


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)


@router.post("/commissions/{commission_id}/reject")
async def reject_commission(
    commission_id: str,
    body: RejectRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Void a commission that has not been paid (fraud, self-referral, a mistake)."""
    row = await _commission_or_404(db, commission_id)
    if row.status not in (COMMISSION_PENDING, COMMISSION_APPROVED) or row.payout_id is not None:
        raise _bad("Only an unpaid commission that isn't in a payout can be rejected.")
    previous = row.status
    row.status = COMMISSION_REJECTED
    row.note = f"{row.note}\nRejected: {body.reason.strip()}" if row.note else f"Rejected: {body.reason.strip()}"
    audit(
        db, admin, "affiliate_commission.reject", target_type="affiliate_commission", target_id=row.id,
        summary=f"Rejected commission {row.amount}", details={"from": previous, "reason": body.reason},
        request=request,
    )
    await db.commit()
    return views.commission_view(row)


@router.get("/payouts")
async def list_payouts(
    affiliate_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(processing|paid|failed)$"),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    query = select(AffiliatePayout)
    if affiliate_id:
        query = query.where(AffiliatePayout.affiliate_id == parse_uuid(affiliate_id, "affiliate"))
    if status_filter:
        query = query.where(AffiliatePayout.status == status_filter)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await db.execute(
            query.order_by(AffiliatePayout.created_at.desc()).offset(params.offset).limit(params.page_size)
        )
    ).scalars().all()
    names = dict(
        (
            await db.execute(
                select(Affiliate.id, Affiliate.name).where(Affiliate.id.in_({p.affiliate_id for p in rows}))
            )
        ).all()
    )
    items = []
    for p in rows:
        view = views.payout_view(p, staff=True)
        view["affiliate_name"] = names.get(p.affiliate_id)
        items.append(view)
    return paginated(items, total or 0, params)


@router.post("/payouts/{payout_id}/resume")
async def resume_payout(
    payout_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    try:
        payout = await payouts.resume_payout(db, parse_uuid(payout_id, "payout"))
    except payouts.PayoutError as exc:
        raise _bad(exc.public_message)
    audit(
        db, admin, "affiliate_payout.resume", target_type="affiliate_payout", target_id=payout.id,
        summary=f"Resumed payout {payout.amount} {payout.currency.upper()}: {payout.status}", request=request,
    )
    await db.commit()
    return views.payout_view(payout, staff=True)


@router.get("/{affiliate_id}")
async def get_affiliate(affiliate_id: str, db: AsyncSession = Depends(get_db)):
    affiliate = await _affiliate_or_404(db, affiliate_id)
    await commissions.mature(db)
    await db.commit()
    return await _full_view(db, affiliate)


@router.patch("/{affiliate_id}")
async def update_affiliate(
    affiliate_id: str,
    body: AffiliateUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    affiliate = await _affiliate_or_404(db, affiliate_id)
    before = _affiliate_view(affiliate)
    data = body.model_dump(exclude_unset=True)

    referral = normalize_referral_code(body.referral_code) if body.referral_code else None
    coupon = normalize_coupon_code(body.coupon_code) if body.coupon_code else None
    await _check_codes(db, affiliate, referral, coupon)
    _apply_terms(affiliate, body)
    if referral:
        affiliate.referral_code = referral
    if body.remove_coupon:
        affiliate.coupon_code = None
        affiliate.discount_percent = None
    elif coupon:
        affiliate.coupon_code = coupon
    if "discount_percent" in data and not body.remove_coupon:
        discount = Decimal(body.discount_percent or 0)
        affiliate.discount_percent = discount if discount > 0 else None
        if discount > 0 and not affiliate.coupon_code:
            affiliate.coupon_code = await unique_coupon_code(db, affiliate.referral_code)

    after = _affiliate_view(affiliate)
    changed = {
        k: {"from": before[k], "to": after[k]}
        for k in (
            "name", "company", "commission_percent", "referral_code", "coupon", "custom_max_payments",
            "max_commission_payments", "notes", "commission_billing_periods", "commission_percent_monthly",
            "max_monthly_commission_payments",
        )
        if before[k] != after[k]
    }
    audit(
        db, admin, "affiliate.update", target_type="affiliate", target_id=affiliate.id,
        summary=f"Updated affiliate {affiliate.name}", details=changed, request=request,
    )
    await db.commit()
    return await _full_view(db, affiliate)


class StatusChange(BaseModel):
    status: Literal["active", "suspended"]


@router.post("/{affiliate_id}/status")
async def change_status(
    affiliate_id: str,
    body: StatusChange,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Suspend (links, coupon and new commissions stop) or reinstate an affiliate."""
    affiliate = await _affiliate_or_404(db, affiliate_id)
    previous = affiliate.status
    if body.status == "suspended":
        affiliate.status = AFFILIATE_SUSPENDED
    else:
        affiliate.status = AFFILIATE_ACTIVE if affiliate.activated_at else AFFILIATE_INVITED
    if previous == affiliate.status:
        return await _full_view(db, affiliate)
    audit(
        db, admin, "affiliate.status", target_type="affiliate", target_id=affiliate.id,
        summary=f"Affiliate {affiliate.name}: {previous} -> {affiliate.status}", request=request,
    )
    await db.commit()
    return await _full_view(db, affiliate)


@router.post("/{affiliate_id}/invite")
async def resend_invite(
    affiliate_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Email a fresh portal invitation. The link is returned too, for sharing by hand."""
    affiliate = await _affiliate_or_404(db, affiliate_id)
    if affiliate.status == AFFILIATE_SUSPENDED:
        raise _bad("Reinstate this affiliate before inviting them.")
    affiliate.invited_at = utcnow()
    audit(
        db, admin, "affiliate.invite", target_type="affiliate", target_id=affiliate.id,
        summary=f"Sent affiliate invite to {affiliate.user.email}", request=request,
    )
    await db.commit()
    link = invites.invite_url(affiliate)
    sent = await invites.send_invite(affiliate)
    return {"invite_url": link, "invite_sent": sent}


@router.get("/{affiliate_id}/referrals")
async def list_affiliate_referrals(
    affiliate_id: str,
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    affiliate = await _affiliate_or_404(db, affiliate_id)
    query = select(AffiliateReferral).where(AffiliateReferral.affiliate_id == affiliate.id)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await db.execute(
            query.order_by(AffiliateReferral.created_at.desc()).offset(params.offset).limit(params.page_size)
        )
    ).scalars().all()
    users = {
        u.id: u
        for u in (
            await db.execute(select(User).where(User.id.in_([r.user_id for r in rows if r.user_id])))
        ).scalars().all()
    }
    orgs = {
        o.id: o
        for o in (
            await db.execute(select(Organization).where(Organization.id.in_([r.organization_id for r in rows])))
        ).scalars().all()
    }
    subs = await views.latest_subscriptions(db, [r.organization_id for r in rows])
    earned = await views.earned_by_referral(db, [r.id for r in rows])
    items = [
        {
            "id": str(r.id),
            "organization_id": str(r.organization_id),
            "organization_name": orgs[r.organization_id].name if r.organization_id in orgs else None,
            "email": users[r.user_id].email if r.user_id in users else None,
            "source": r.source,
            "status": views.referral_status(subs.get(r.organization_id)),
            "signed_up_at": iso(r.created_at),
            "converted_at": iso(r.converted_at),
            "earned": float(earned.get(r.id, 0)),
        }
        for r in rows
    ]
    return paginated(items, total or 0, params)


class PayoutCreate(BaseModel):
    method: Literal["stripe", "manual"]
    reference: Optional[str] = Field(None, max_length=255)
    note: Optional[str] = Field(None, max_length=2000)
    ignore_minimum: bool = False

    @model_validator(mode="after")
    def _manual_needs_reference(self):
        if self.method == "manual" and not (self.reference or "").strip():
            raise ValueError("Enter the payment reference for a manual payout.")
        return self


@router.post("/{affiliate_id}/payouts", status_code=status.HTTP_201_CREATED)
async def create_payout(
    affiliate_id: str,
    body: PayoutCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Pay the affiliate's whole approved balance, by Stripe transfer or recorded as paid by hand."""
    affiliate = await _affiliate_or_404(db, affiliate_id)
    try:
        payout = await payouts.create_payout(
            db,
            affiliate.id,
            method=body.method,
            actor_id=admin.id,
            reference=body.reference,
            note=body.note,
            ignore_minimum=body.ignore_minimum,
        )
    except payouts.PayoutError as exc:
        await db.rollback()
        raise _bad(exc.public_message)
    audit(
        db, admin, "affiliate_payout.create", target_type="affiliate", target_id=affiliate.id,
        summary=f"{body.method.title()} payout of {payout.amount} {payout.currency.upper()} to {affiliate.name}: {payout.status}",
        details={"payout_id": str(payout.id), "failure_reason": payout.failure_reason},
        request=request,
    )
    await db.commit()
    return views.payout_view(payout, staff=True)

