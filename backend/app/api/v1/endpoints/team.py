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
from app.core import permissions as perms
from app.core.dependencies import (
    get_current_user,
    get_current_org_id,
    get_workspace,
    require_permission,
)
from app.core.workspace import WorkspaceContext
from app.models.user import User, OrganizationMember, Organization
from app.models.invitation import Invitation
from app.schemas.invitation import InviteRequest, InvitationResponse
from app.services.team import invitation_service

router = APIRouter()

ROLE_HIERARCHY = perms.ROLE_HIERARCHY
#: "owner" is never assignable through an invite or a role change — ownership
#: moves only via POST /workspaces/current/transfer-ownership, which is
#: owner-only. This is what stops an admin from promoting themselves.
ASSIGNABLE_ROLES = perms.ASSIGNABLE_ROLES


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


def _require_can_act_on(actor: OrganizationMember, target: OrganizationMember) -> None:
    """Guard every action that changes another member's standing.

    Rank decides: you may only act on someone strictly below you, and acting on
    an admin or the owner additionally needs ``team:manage_admins``, which only
    the owner has. So an admin can manage members and viewers, but cannot
    demote, remove, or otherwise touch a fellow admin or the owner.
    """
    if perms.can_act_on(actor.role, target.role):
        return

    if target.role == perms.ROLE_OWNER:
        detail = "Only the workspace owner can change the owner's membership."
    elif target.role == actor.role:
        detail = f"You cannot manage another {target.role}."
    else:
        detail = f"Only the owner can manage a {target.role}."
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


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
    workspace: WorkspaceContext = Depends(require_permission(perms.TEAM_READ)),
    db: AsyncSession = Depends(get_db),
):
    """List every member of the current workspace. Any member may look."""
    org_id = workspace.organization_id
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
    workspace: WorkspaceContext = Depends(require_permission(perms.TEAM_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Invite someone to the current workspace by email (owner/admin only).

    Creates a pending invitation, emails the invitee Accept/Reject links, and —
    if they already have an account — drops an in-app notification. No membership
    is created until they accept.

    Inviting *as an admin* is itself an owner-level act: an admin who could mint
    admins could manufacture allies, so the role being handed out is checked
    against the inviter's own rank.
    """
    org_id = workspace.organization_id
    role = (payload.role or perms.ROLE_MEMBER).lower()
    if role not in ASSIGNABLE_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    if perms.role_rank(role) >= perms.role_rank(perms.ROLE_ADMIN) and not workspace.has(
        perms.TEAM_MANAGE_ADMINS
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the workspace owner can invite an admin.",
        )

    try:
        invitation = await invitation_service.create_invitation(
            db,
            organization=workspace.organization,
            inviter=workspace.user,
            email=payload.email,
            role=role,
        )
    except ValueError as exc:
        code = getattr(exc, "code", "")
        http_status = (
            status.HTTP_409_CONFLICT
            if code in ("already_member", "already_invited")
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=http_status, detail=str(exc))

    return _invitation_response(invitation, workspace.user)


@router.get("/invitations", response_model=List[InvitationResponse])
async def list_invitations(
    workspace: WorkspaceContext = Depends(require_permission(perms.TEAM_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """List pending invitations for the workspace (owner/admin only)."""
    org_id = workspace.organization_id
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
    workspace: WorkspaceContext = Depends(require_permission(perms.TEAM_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending invitation (owner/admin only)."""
    org_id = workspace.organization_id
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
    workspace: WorkspaceContext = Depends(require_permission(perms.TEAM_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Change a member's role (owner/admin only).

    Three separate guards, each closing a different escalation:
      * "owner" is not an assignable role — ownership moves only by transfer;
      * you cannot act on a peer or a superior, so an admin cannot demote the
        owner or another admin;
      * promoting someone *to* admin needs owner rank, so an admin cannot
        manufacture a peer.
    """
    org_id = workspace.organization_id
    role = payload.role.lower()
    if role not in ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Ownership can only be moved with a workspace ownership transfer."
                if role == perms.ROLE_OWNER
                else "Invalid role"
            ),
        )

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

    if target.id == workspace.membership.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot change your own role"
        )

    _require_can_act_on(workspace.membership, target)

    if perms.role_rank(role) >= perms.role_rank(perms.ROLE_ADMIN) and not workspace.has(
        perms.TEAM_MANAGE_ADMINS
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the workspace owner can promote someone to admin.",
        )

    target.role = role
    await db.commit()
    await db.refresh(target, attribute_names=["user"])
    return _to_response(target)


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    member_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(perms.TEAM_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member from the workspace (owner/admin only).

    The owner can never be removed — not by an admin, and not by themselves.
    An admin also cannot remove a fellow admin; that is the owner's call.
    """
    org_id = workspace.organization_id
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

    if target.role == perms.ROLE_OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The workspace owner cannot be removed. Transfer ownership first.",
        )

    if target.id == workspace.membership.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use POST /workspaces/current/leave to remove yourself.",
        )

    _require_can_act_on(workspace.membership, target)

    # Anyone whose active workspace was this one gets re-resolved on their next
    # request; clearing it here avoids a dangling pointer in the meantime.
    removed_user = target.user
    if removed_user is not None and removed_user.active_organization_id == org_id:
        removed_user.active_organization_id = None

    await db.delete(target)
    await db.commit()
