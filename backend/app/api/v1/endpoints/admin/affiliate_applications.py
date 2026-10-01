"""Affiliate requests: review what came in through the public form.

Approving has no endpoint here on purpose. Staff create the affiliate with the
normal form (``POST /admin/affiliates`` with ``application_id``), so a request
never gets terms by a different path than any other affiliate.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin import audit, require_platform_admin
from app.database import get_db
from app.models.affiliate import (
    APPLICATION_PENDING,
    APPLICATION_REJECTED,
    Affiliate,
    AffiliateApplication,
)
from app.models.user import User
from app.services.affiliates import applications

from ._common import PageParams, iso, like, paginated, parse_uuid, utcnow

router = APIRouter(prefix="/affiliates/applications")


async def _existing_affiliates(db: AsyncSession, emails: List[str]) -> Dict[str, Affiliate]:
    """Affiliates whose login already uses one of these addresses, by address."""
    if not emails:
        return {}
    rows = (
        await db.execute(select(Affiliate).join(User, User.id == Affiliate.user_id).where(User.email.in_(emails)))
    ).scalars().all()
    return {a.user.email: a for a in rows if a.user}


def _view(a: AffiliateApplication, existing: Optional[Affiliate], reviewer: Optional[str] = None) -> dict:
    return {
        "id": str(a.id),
        "name": a.name,
        "email": a.email,
        "company": a.company,
        "website": a.website,
        "message": a.message,
        "status": a.status,
        "affiliate_id": str(a.affiliate_id) if a.affiliate_id else None,
        # Someone with this address is an affiliate already, from this request
        # or not. Creating another would be refused, so the console says so.
        "existing_affiliate": {"id": str(existing.id), "name": existing.name} if existing else None,
        "review_note": a.review_note,
        "reviewed_by": reviewer,
        "reviewed_at": iso(a.reviewed_at),
        "created_at": iso(a.created_at),
    }


async def _application_or_404(db: AsyncSession, application_id: str) -> AffiliateApplication:
    row = await db.get(AffiliateApplication, parse_uuid(application_id, "affiliate request"))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Affiliate request not found")
    return row


async def _full_view(db: AsyncSession, a: AffiliateApplication) -> dict:
    existing = (await _existing_affiliates(db, [a.email])).get(a.email)
    reviewer = await db.scalar(select(User.email).where(User.id == a.reviewed_by)) if a.reviewed_by else None
    return _view(a, existing, reviewer)


@router.get("")
async def list_applications(
    search: Optional[str] = Query(None, max_length=200),
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(pending|approved|rejected)$"),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    query = select(AffiliateApplication)
    if search:
        term = like(search.strip())
        query = query.where(
            or_(
                AffiliateApplication.name.ilike(term),
                AffiliateApplication.email.ilike(term),
                AffiliateApplication.company.ilike(term),
                AffiliateApplication.website.ilike(term),
            )
        )
    if status_filter:
        query = query.where(AffiliateApplication.status == status_filter)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await db.execute(
            query.order_by(AffiliateApplication.created_at.desc()).offset(params.offset).limit(params.page_size)
        )
    ).scalars().all()
    existing = await _existing_affiliates(db, [a.email for a in rows])
    reviewers = dict(
        (
            await db.execute(
                select(User.id, User.email).where(User.id.in_({a.reviewed_by for a in rows if a.reviewed_by}))
            )
        ).all()
    )
    items = [_view(a, existing.get(a.email), reviewers.get(a.reviewed_by)) for a in rows]
    return paginated(items, total or 0, params)


@router.get("/count")
async def count_applications(db: AsyncSession = Depends(get_db)):
    """How many requests are waiting, for the sidebar badge."""
    pending = await db.scalar(
        select(func.count()).where(AffiliateApplication.status == APPLICATION_PENDING)
    )
    return {"pending": int(pending or 0)}


@router.get("/{application_id}")
async def get_application(application_id: str, db: AsyncSession = Depends(get_db)):
    return await _full_view(db, await _application_or_404(db, application_id))


class RejectRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=2000)


@router.post("/{application_id}/reject")
async def reject_application(
    application_id: str,
    body: RejectRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Turn a waiting request down. The applicant is not told; the reason is for staff."""
    row = await _application_or_404(db, application_id)
    if row.status != APPLICATION_PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only a pending request can be rejected."
        )
    row.status = APPLICATION_REJECTED
    row.review_note = (body.reason or "").strip() or None
    row.reviewed_by = admin.id
    row.reviewed_at = utcnow()
    await applications.resolve_notifications(db, row.id)
    audit(
        db, admin, "affiliate_application.reject", target_type="affiliate_application", target_id=row.id,
        summary=f"Rejected affiliate request from {row.name} <{row.email}>",
        details={"reason": row.review_note}, request=request,
    )
    await db.commit()
    return await _full_view(db, row)


@router.post("/{application_id}/reopen")
async def reopen_application(
    application_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Put a rejected request back in the queue, e.g. after rejecting the wrong one."""
    row = await _application_or_404(db, application_id)
    if row.status != APPLICATION_REJECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only a rejected request can be reopened."
        )
    row.status = APPLICATION_PENDING
    row.review_note = None
    row.reviewed_by = None
    row.reviewed_at = None
    audit(
        db, admin, "affiliate_application.reopen", target_type="affiliate_application", target_id=row.id,
        summary=f"Reopened affiliate request from {row.name} <{row.email}>", request=request,
    )
    await db.commit()
    return await _full_view(db, row)
