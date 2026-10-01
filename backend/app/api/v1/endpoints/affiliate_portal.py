"""
Affiliate portal API, mounted at ``/api/v1/affiliate``.

Only an affiliate-scoped session (``POST /auth/affiliate/login``) reaches these
routes — ``_enforce_session_scope`` refuses app and admin sessions here, and
refuses affiliate sessions everywhere else. Referred customers are shown with
masked emails: an affiliate sees that someone signed up and paid, not who.

``public_router`` (``/api/v1/affiliate-public``) counts referral link visits
from anonymous browsers, and takes requests to join the program from the
public form.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.schemas._types import PersonName
from app.database import get_db
from app.models.affiliate import (
    AFFILIATE_SUSPENDED,
    Affiliate,
    AffiliateCommission,
    AffiliatePayout,
    AffiliateReferral,
)
from app.models.user import User
from app.services.affiliates import applications, attribution, commissions, invites, payouts, views
from app.services.affiliates.program import get_program, mask_email
from app.services.auth.verification import normalize_email
from app.core.time import utc_iso

router = APIRouter()
public_router = APIRouter()


async def require_affiliate(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Affiliate:
    affiliate = await db.scalar(select(Affiliate).where(Affiliate.user_id == current_user.id))
    if affiliate is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is not an affiliate.")
    if affiliate.status == AFFILIATE_SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your affiliate account is paused. Contact us if you think this is a mistake.",
        )
    return affiliate


def _page(items: list, total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


@router.get("/me")
async def get_me(
    affiliate: Affiliate = Depends(require_affiliate),
    db: AsyncSession = Depends(get_db),
):
    """Profile, links, coupon, rules, payout setup and headline numbers."""
    await commissions.mature(db)
    await db.commit()
    program = await get_program(db)
    balance = (await commissions.balances(db, [affiliate.id])).get(affiliate.id) or commissions.empty_balance()
    refs = (await commissions.referral_stats(db, [affiliate.id])).get(affiliate.id, {})
    clicks = (await views.click_counts(db, [affiliate.id])).get(affiliate.id, {})
    return {
        "id": str(affiliate.id),
        "name": affiliate.name,
        "company": affiliate.company,
        "email": affiliate.user.email if affiliate.user else None,
        "status": affiliate.status,
        "referral_code": affiliate.referral_code,
        "links": views.links(affiliate),
        "coupon": views.coupon_view(affiliate),
        "rules": views.rules_view(affiliate, program, await views.plan_names(db)),
        "program_enabled": program.enabled,
        "stripe": views.stripe_view(affiliate),
        "stats": {
            "clicks": clicks.get("clicks", 0),
            "clicks_30d": clicks.get("clicks_30d", 0),
            "referrals": refs.get("referrals", 0),
            "conversions": refs.get("conversions", 0),
        },
        "balance": views.balance_view(balance),
        "currency": "usd",
    }


@router.get("/referrals")
async def list_referrals(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    affiliate: Affiliate = Depends(require_affiliate),
    db: AsyncSession = Depends(get_db),
):
    base = select(AffiliateReferral).where(AffiliateReferral.affiliate_id == affiliate.id)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.execute(
            base.order_by(AffiliateReferral.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    users = {
        u.id: u
        for u in (
            await db.execute(select(User).where(User.id.in_([r.user_id for r in rows if r.user_id])))
        ).scalars().all()
    }
    subs = await views.latest_subscriptions(db, [r.organization_id for r in rows])
    earned = await views.earned_by_referral(db, [r.id for r in rows])
    items = [
        {
            "id": str(r.id),
            "customer": mask_email(users[r.user_id].email) if r.user_id in users else "—",
            "source": r.source,
            "status": views.referral_status(subs.get(r.organization_id)),
            "signed_up_at": utc_iso(r.created_at),
            "converted_at": utc_iso(r.converted_at),
            "earned": float(earned.get(r.id, 0)),
        }
        for r in rows
    ]
    return _page(items, total or 0, page, page_size)


@router.get("/commissions")
async def list_commissions(
    status_filter: Optional[str] = Query(
        None, alias="status", pattern="^(pending|approved|paid|reversed|rejected)$"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    affiliate: Affiliate = Depends(require_affiliate),
    db: AsyncSession = Depends(get_db),
):
    await commissions.mature(db)
    await db.commit()
    base = select(AffiliateCommission).where(AffiliateCommission.affiliate_id == affiliate.id)
    if status_filter:
        base = base.where(AffiliateCommission.status == status_filter)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.execute(
            base.order_by(AffiliateCommission.earned_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    referral_users = dict(
        (
            await db.execute(
                select(AffiliateReferral.id, User.email)
                .join(User, User.id == AffiliateReferral.user_id)
                .where(AffiliateReferral.id.in_([c.referral_id for c in rows if c.referral_id]))
            )
        ).all()
    )
    items = [
        views.commission_view(
            c, customer=mask_email(referral_users.get(c.referral_id)) if c.referral_id else None
        )
        for c in rows
    ]
    return _page(items, total or 0, page, page_size)


@router.get("/payouts")
async def list_payouts(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    affiliate: Affiliate = Depends(require_affiliate),
    db: AsyncSession = Depends(get_db),
):
    base = select(AffiliatePayout).where(AffiliatePayout.affiliate_id == affiliate.id)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.execute(
            base.order_by(AffiliatePayout.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return _page([views.payout_view(p) for p in rows], total or 0, page, page_size)


# ---- Stripe Connect ----


class ConnectRequest(BaseModel):
    #: ISO 3166-1 alpha-2 country of the bank account, e.g. "US".
    country: Optional[str] = Field(None, min_length=2, max_length=2)


def _payout_error(exc: payouts.PayoutError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.public_message)


@router.post("/stripe/connect")
async def connect_stripe(
    body: ConnectRequest,
    affiliate: Affiliate = Depends(require_affiliate),
    db: AsyncSession = Depends(get_db),
):
    """A Stripe-hosted onboarding link. Creates the Express account the first time."""
    try:
        url = await payouts.onboarding_link(
            db,
            affiliate,
            country=body.country,
            refresh_url=invites.portal_url("/affiliate/payouts?stripe=refresh"),
            return_url=invites.portal_url("/affiliate/payouts?stripe=return"),
        )
    except payouts.PayoutError as exc:
        raise _payout_error(exc)
    return {"url": url}


@router.post("/stripe/refresh")
async def refresh_stripe(
    affiliate: Affiliate = Depends(require_affiliate),
    db: AsyncSession = Depends(get_db),
):
    """Re-read the connected account's status from Stripe (after onboarding returns)."""
    await payouts.refresh_account(db, affiliate)
    await db.commit()
    return views.stripe_view(affiliate)


@router.post("/stripe/dashboard")
async def stripe_dashboard(affiliate: Affiliate = Depends(require_affiliate)):
    try:
        return {"url": await payouts.dashboard_link(affiliate)}
    except payouts.PayoutError as exc:
        raise _payout_error(exc)


# ---- Public: referral link visits ----


class ClickRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=60)
    landing_path: Optional[str] = Field(None, max_length=500)
    referrer: Optional[str] = Field(None, max_length=500)


class ClickResponse(BaseModel):
    valid: bool
    #: How long the browser should remember the code.
    cookie_days: int = 0
    kind: Optional[Literal["referral"]] = None


@public_router.post("/click", response_model=ClickResponse)
async def record_click(body: ClickRequest, db: AsyncSession = Depends(get_db)):
    """Count a visit through a referral link and say whether the code is live."""
    affiliate = await attribution.record_click(
        db, body.code, landing_path=body.landing_path, referrer=body.referrer
    )
    if affiliate is None:
        return ClickResponse(valid=False)
    program = await get_program(db)
    await db.commit()
    return ClickResponse(valid=True, cookie_days=program.cookie_days, kind="referral")


class ApplicationRequest(BaseModel):
    name: PersonName
    email: EmailStr
    company: Optional[str] = Field(None, max_length=255)
    #: Site, channel or profile where they would promote.
    website: Optional[str] = Field(None, max_length=500)
    #: Their audience and how they plan to promote.
    message: str = Field(..., min_length=10, max_length=3000)
    #: Honeypot: hidden from people, so only a bot fills it in.
    fax: Optional[str] = Field(None, max_length=255)

    @field_validator("name", "company", "website", mode="before")
    @classmethod
    def _one_line(cls, value):
        # These end up in an email subject and in table cells.
        return " ".join(value.split()) if isinstance(value, str) else value

    @field_validator("message", mode="before")
    @classmethod
    def _trimmed(cls, value):
        return value.strip() if isinstance(value, str) else value


class ApplicationResponse(BaseModel):
    success: bool = True
    message: str


_APPLICATION_RECEIVED = "Thanks — your request is in. We review every request and will email you with the next steps."


@public_router.post("/apply", response_model=ApplicationResponse)
async def apply_to_program(
    body: ApplicationRequest,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Ask to join the affiliate program. Staff review the request in the admin console.

    The answer is the same whether or not this address has applied before or is
    already an affiliate, so the form cannot be used to find out who is one.
    """
    if body.fax:
        return ApplicationResponse(message=_APPLICATION_RECEIVED)
    ip = request.client.host if request.client else None
    if not applications.allow_submission(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You've sent several requests already. Please try again in an hour.",
        )
    application, created = await applications.submit(
        db,
        name=body.name,
        email=normalize_email(str(body.email)),
        company=body.company or None,
        website=body.website or None,
        message=body.message,
        ip_address=ip,
    )
    admin_emails = await applications.notify_admins(db, application) if created else []
    await db.commit()
    if admin_emails:
        # After the response: the applicant should not wait on the mail server.
        background.add_task(applications.email_admins, application, admin_emails)
    return ApplicationResponse(message=_APPLICATION_RECEIVED)
