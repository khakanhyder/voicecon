"""
Team management endpoints — the "Settings → Team" surface.

Lists members of the current user's organization and lets owners/admins invite
new members, change roles, and remove members. Roles: owner > admin > member >
viewer (see ``role_hierarchy`` in core.dependencies).

Inviting creates a *pending* Invitation (see services.team.invitation_service):
an email with Accept/Reject links is sent and, if the invitee already has an
account, an in-app notification is created. A membership is only created when
the invite is accepted, so pending invites don't appear in the member list —
they're returned by ``GET /team/invitations``.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.dependencies import get_current_user, get_current_org_id
from app.models.user import User, OrganizationMember, Organization
from app.models.invitation import Invitation
from app.schemas.invitation import InviteRequest, InvitationResponse
from app.services.team import invitation_service

router = APIRouter()

ROLE_HIERARCHY = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}
ASSIGNABLE_ROLES = {"admin", "member", "viewer"}  # "owner" is not assignable via invite/patch


# ---- Schemas ----
class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: Optional[str] = None
    email: str
    role: str
    status: str
    joined_at: datetime


class UpdateMemberRequest(BaseModel):
    role: str


# ---- Helpers ----
async def _require_membership(db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID) -> OrganizationMember:
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == org_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this organization")
    return membership


def _require_min_role(membership: OrganizationMember, minimum: str) -> None:
    if ROLE_HIERARCHY.get(membership.role, 0) < ROLE_HIERARCHY[minimum]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires {minimum} role or higher",
        )


def _status_for(user: User, membership: OrganizationMember) -> str:
    if not user.is_active:
        return "Inactive"
    if user.auth_provider == "invited" and user.last_login_at is None:
        return "Invited"
    return "Active"


def _to_response(member: OrganizationMember) -> TeamMemberResponse:
    return TeamMemberResponse(
        id=member.id,
        user_id=member.user_id,
        name=member.user.full_name,
        email=member.user.email,
        role=member.role,
        status=_status_for(member.user, member),
        joined_at=member.joined_at,
    )


# ---- Endpoints ----
@router.get("/members", response_model=List[TeamMemberResponse])
async def list_members(
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """List all members of the current user's organization."""
    result = await db.execute(
        select(OrganizationMember)
        .options(selectinload(OrganizationMember.user))
        .where(OrganizationMember.organization_id == org_id)
        .order_by(OrganizationMember.joined_at)
    )
    members = result.scalars().all()
    return [_to_response(m) for m in members]


def _invitation_response(inv: Invitation, inviter: Optional[User]) -> InvitationResponse:
    return InvitationResponse(
        id=inv.id,
        email=inv.email,
        role=inv.role,
        status=inv.status,
        invited_by_name=(inviter.full_name or inviter.email) if inviter else None,
        expires_at=inv.expires_at,
        created_at=inv.created_at,
    )


@router.post("/invite", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    payload: InviteRequest,
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Invite someone to the organization by email (owner/admin only).

    Creates a pending invitation, emails the invitee Accept/Reject links, and —
    if they already have an account — drops an in-app notification. No membership
    is created until they accept.
    """
    membership = await _require_membership(db, current_user.id, org_id)
    _require_min_role(membership, "admin")

    org = (
        await db.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one()

    try:
        invitation = await invitation_service.create_invitation(
            db, organization=org, inviter=current_user, email=payload.email, role=payload.role
        )
    except ValueError as exc:
        code = getattr(exc, "code", "")
        http_status = (
            status.HTTP_409_CONFLICT
            if code in ("already_member", "already_invited")
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=http_status, detail=str(exc))

    return _invitation_response(invitation, current_user)


@router.get("/invitations", response_model=List[InvitationResponse])
async def list_invitations(
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """List pending invitations for the organization (owner/admin only)."""
    membership = await _require_membership(db, current_user.id, org_id)
    _require_min_role(membership, "admin")

    result = await db.execute(
        select(Invitation)
        .options(selectinload(Invitation.inviter))
        .where(Invitation.organization_id == org_id, Invitation.status == "pending")
        .order_by(Invitation.created_at.desc())
    )
    invitations = result.scalars().all()
    return [_invitation_response(inv, inv.inviter) for inv in invitations]


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invitation(
    invitation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending invitation (owner/admin only)."""
    membership = await _require_membership(db, current_user.id, org_id)
    _require_min_role(membership, "admin")

    result = await db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id, Invitation.organization_id == org_id
        )
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    await invitation_service.cancel_invitation(db, invitation)


@router.patch("/members/{member_id}", response_model=TeamMemberResponse)
async def update_member_role(
    member_id: uuid.UUID,
    payload: UpdateMemberRequest,
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Change a member's role (owner/admin only). The owner's role is immutable."""
    membership = await _require_membership(db, current_user.id, org_id)
    _require_min_role(membership, "admin")

    role = payload.role.lower()
    if role not in ASSIGNABLE_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    result = await db.execute(
        select(OrganizationMember)
        .options(selectinload(OrganizationMember.user))
        .where(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == org_id,
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if target.role == "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change the owner's role")

    target.role = role
    await db.commit()
    await db.refresh(target, attribute_names=["user"])
    return _to_response(target)


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    member_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member from the organization (owner/admin only). The owner cannot be removed."""
    membership = await _require_membership(db, current_user.id, org_id)
    _require_min_role(membership, "admin")

    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == org_id,
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if target.role == "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the organization owner")

    await db.delete(target)
    await db.commit()
