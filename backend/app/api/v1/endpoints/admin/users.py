"""Cross-tenant user management."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin import audit, require_platform_admin
from app.database import get_db
from app.models.user import Organization, OrganizationMember, User
from app.services.auth import login_throttle

from ._common import PageParams, iso, like, paginated, parse_uuid, utcnow

router = APIRouter()


def _user_view(user: User, orgs: int = 0) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "auth_provider": user.auth_provider,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_platform_admin": user.is_platform_admin,
        "organizations": orgs,
        "locked_for_seconds": login_throttle.seconds_until_unlocked(user.email),
        "created_at": iso(user.created_at),
        "last_login_at": iso(user.last_login_at),
        "deleted_at": iso(user.deleted_at),
    }


async def _user_or_404(db: AsyncSession, user_id: str) -> User:
    user = await db.get(User, parse_uuid(user_id, "user"))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/users")
async def list_users(
    search: Optional[str] = Query(None, max_length=200),
    filter: Optional[str] = Query(None, pattern="^(active|disabled|unverified|admins)$"),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    query = select(User)
    if search:
        term = like(search.strip())
        query = query.where(or_(User.email.ilike(term), User.full_name.ilike(term), User.company_name.ilike(term)))
    if filter == "active":
        query = query.where(User.is_active.is_(True))
    elif filter == "disabled":
        query = query.where(User.is_active.is_(False))
    elif filter == "unverified":
        query = query.where(User.is_verified.is_(False))
    elif filter == "admins":
        query = query.where(User.is_platform_admin.is_(True))

    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0)
    users = (
        await db.execute(query.order_by(User.created_at.desc()).offset(params.offset).limit(params.page_size))
    ).scalars().all()

    counts = {}
    if users:
        counts = {
            uid: int(n)
            for uid, n in (
                await db.execute(
                    select(OrganizationMember.user_id, func.count(OrganizationMember.id))
                    .where(OrganizationMember.user_id.in_([u.id for u in users]))
                    .group_by(OrganizationMember.user_id)
                )
            ).all()
        }
    return paginated([_user_view(u, counts.get(u.id, 0)) for u in users], total, params)


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    user = await _user_or_404(db, user_id)
    rows = (
        await db.execute(
            select(OrganizationMember, Organization)
            .join(Organization, Organization.id == OrganizationMember.organization_id)
            .where(OrganizationMember.user_id == user.id)
            .order_by(OrganizationMember.joined_at)
        )
    ).all()
    view = _user_view(user, len(rows))
    view.update(
        {
            "company_name": user.company_name,
            "phone_number": user.phone_number,
            "timezone": user.timezone,
            "email_verified_at": iso(user.email_verified_at),
            "memberships": [
                {
                    "organization_id": str(org.id),
                    "organization_name": org.name,
                    "organization_active": org.is_active,
                    "role": m.role,
                    "joined_at": iso(m.joined_at),
                }
                for m, org in rows
            ],
        }
    )
    return view


class UserPatch(BaseModel):
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_platform_admin: Optional[bool] = None
    reason: Optional[str] = None


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UserPatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    user = await _user_or_404(db, user_id)
    changes = body.model_dump(exclude_unset=True, exclude={"reason"})
    if not changes:
        return _user_view(user)

    if user.id == admin.id and (changes.get("is_active") is False or changes.get("is_platform_admin") is False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot disable or demote your own account. Ask another admin.",
        )
    if changes.get("is_platform_admin") is False and user.is_platform_admin:
        admins = int(
            (await db.execute(select(func.count(User.id)).where(User.is_platform_admin.is_(True)))).scalar() or 0
        )
        if admins <= 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="At least one platform admin must remain.")

    before = {k: getattr(user, k) for k in changes}
    for key, value in changes.items():
        setattr(user, key, value)
    if changes.get("is_verified") and not user.email_verified_at:
        user.email_verified_at = utcnow()
    if changes.get("is_active") is False:
        # Disabling already refuses new requests; this also kills refresh tokens.
        user.token_version = (user.token_version or 0) + 1

    parts = []
    if "is_active" in changes:
        parts.append("enabled" if changes["is_active"] else "disabled")
    if "is_verified" in changes:
        parts.append("marked verified" if changes["is_verified"] else "marked unverified")
    if "is_platform_admin" in changes:
        parts.append("granted platform admin" if changes["is_platform_admin"] else "revoked platform admin")
    audit(db, admin, "user.update", target_type="user", target_id=user.id,
          summary=f"{user.email}: {', '.join(parts)}",
          details={"before": before, "after": changes, "reason": body.reason}, request=request)
    await db.commit()
    await db.refresh(user)
    return _user_view(user)


@router.post("/users/{user_id}/sign-out")
async def sign_out_everywhere(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Invalidate every session and refresh token the user holds."""
    user = await _user_or_404(db, user_id)
    user.token_version = (user.token_version or 0) + 1
    audit(db, admin, "user.sign_out", target_type="user", target_id=user.id,
          summary=f"Signed {user.email} out of every session", request=request)
    await db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/unlock")
async def unlock_login(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Clear failed-login lockout. Counters are per server process, so with
    several replicas this clears only the one that handled this request."""
    user = await _user_or_404(db, user_id)
    login_throttle.clear(user.email)
    audit(db, admin, "user.unlock", target_type="user", target_id=user.id,
          summary=f"Cleared login lockout for {user.email}", request=request)
    await db.commit()
    return {"ok": True}
