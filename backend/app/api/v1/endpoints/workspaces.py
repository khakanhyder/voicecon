"""
Workspace endpoints — "which workspace am I in, and which can I switch to?".

A user belongs to their own workspace plus any they were invited to. These
endpoints back the workspace switcher and expose the caller's role and
permission set so the UI can hide what the API would refuse anyway.

Ownership is deliberately narrow here: only the owner may delete the workspace,
and ownership never moves — the user who created a workspace owns it for its
whole life. An admin can run the team but cannot seize or destroy it.
"""
import logging
import re
import uuid
from datetime import datetime
from typing import FrozenSet, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import permissions as perms
from app.core.dependencies import get_current_user, get_workspace, require_permission
from app.core.workspace import WorkspaceContext, get_membership, list_memberships
from app.database import get_db
from app.models.user import Organization, OrganizationMember, User
from app.schemas._types import NonBlankName
from app.services.billing.entitlements import invalidate_entitlements
from app.services.billing.trial import TrialUnavailable, grant_trial
from app.core.time import UTCDatetime

router = APIRouter()

logger = logging.getLogger(__name__)


# ---- Schemas ----
class WorkspaceSummary(BaseModel):
    """One entry in the workspace switcher."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    role: str
    is_owner: bool
    is_current: bool
    member_count: int
    joined_at: UTCDatetime
    plan_type: str


class WorkspaceDetail(BaseModel):
    """The workspace the caller is currently acting inside."""

    id: uuid.UUID
    name: str
    slug: str
    plan_type: str
    role: str
    is_owner: bool
    permissions: List[str]
    member_count: int
    owner_email: Optional[str] = None
    created_at: UTCDatetime


class WorkspaceUpdate(BaseModel):
    # `min_length=1` counts characters, so a single space satisfied it and the
    # handler's own `.strip()` then stored "" — leaving the switcher and every
    # page header blank. NonBlankName trims first, so the check sees what will
    # actually be saved.
    name: NonBlankName


class SwitchResponse(BaseModel):
    workspace: WorkspaceDetail
    message: str


# ---- Helpers ----
async def _member_count(db: AsyncSession, org_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.organization_id == org_id
            )
        )
    ).scalar_one()


async def _detail(
    db: AsyncSession,
    organization: Organization,
    membership: OrganizationMember,
    effective_permissions: Optional[FrozenSet[str]] = None,
) -> WorkspaceDetail:
    """Render a workspace for the client.

    ``effective_permissions`` is what the *current request* may do, which is
    narrower than the role's grant when an API key made the call. Pass it
    wherever a WorkspaceContext is in hand so the answer describes the caller,
    not just their role; it falls back to the role's full grant for the
    listing views, which describe workspaces the caller isn't acting in.
    """
    owner_email = (
        await db.execute(select(User.email).where(User.id == organization.owner_id))
    ).scalar_one_or_none()
    if effective_permissions is None:
        effective_permissions = perms.permissions_for(membership.role)
    return WorkspaceDetail(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        plan_type=organization.plan_type,
        role=membership.role,
        is_owner=membership.role == perms.ROLE_OWNER,
        permissions=sorted(effective_permissions),
        member_count=await _member_count(db, organization.id),
        owner_email=owner_email,
        created_at=organization.created_at,
    )


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"
    return f"{base[:40]}-{uuid.uuid4().hex[:8]}"


# ---- Endpoints ----
@router.get("", response_model=List[WorkspaceSummary])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Every workspace the caller belongs to, with the current one flagged.

    This is what the switcher renders. Deliberately independent of the current
    workspace: a user who was just removed from their active one still needs a
    list to switch out of it, so this returns an empty list rather than 404ing.
    The ``is_current`` flag is authoritative — the client should not try to
    infer the active workspace itself.
    """
    active_id = current_user.active_organization_id
    memberships = await list_memberships(db, current_user.id)
    if active_id is None or not any(m.organization_id == active_id for m in memberships):
        # No valid pin: the default is whatever the resolver would pick.
        usable = [m for m in memberships if m.organization is not None and m.organization.is_active]
        active_id = usable[0].organization_id if usable else None

    out: List[WorkspaceSummary] = []
    for membership in memberships:
        org = membership.organization
        if org is None or not org.is_active:
            continue
        out.append(
            WorkspaceSummary(
                id=org.id,
                name=org.name,
                slug=org.slug,
                role=membership.role,
                is_owner=membership.role == perms.ROLE_OWNER,
                is_current=org.id == active_id,
                member_count=await _member_count(db, org.id),
                joined_at=membership.joined_at,
                plan_type=org.plan_type,
            )
        )
    return out


@router.get("/current", response_model=WorkspaceDetail)
async def get_current_workspace(
    workspace: WorkspaceContext = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    """The active workspace plus the caller's role and full permission list.

    The frontend gates its UI on ``permissions``, so this is the single source
    of truth for both sides — there is no second copy of the matrix to drift.
    """
    return await _detail(
        db, workspace.organization, workspace.membership, workspace.permissions
    )


@router.post("/{organization_id}/switch", response_model=SwitchResponse)
async def switch_workspace(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Make ``organization_id`` the caller's active workspace.

    Deliberately does *not* depend on the current workspace: a user whose
    active workspace was just deleted or revoked must still be able to switch
    out of it. Membership in the target is checked here instead.
    """
    membership = await get_membership(db, current_user.id, organization_id)
    if membership is None or membership.organization is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this workspace",
        )
    if not membership.organization.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This workspace is no longer active",
        )

    current_user.active_organization_id = organization_id
    await db.commit()

    detail = await _detail(db, membership.organization, membership)
    return SwitchResponse(
        workspace=detail,
        message=f"Switched to {membership.organization.name}.",
    )


@router.patch("/current", response_model=WorkspaceDetail)
async def update_current_workspace(
    payload: WorkspaceUpdate,
    workspace: WorkspaceContext = Depends(require_permission(perms.WORKSPACE_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Rename the current workspace (owner/admin)."""
    workspace.organization.name = payload.name.strip()
    await db.commit()
    await db.refresh(workspace.organization)
    return await _detail(
        db, workspace.organization, workspace.membership, workspace.permissions
    )


@router.post("", response_model=WorkspaceDetail, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new workspace owned by the caller, and switch into it."""
    name = payload.name.strip()
    organization = Organization(name=name, slug=_slugify(name), owner_id=current_user.id)
    db.add(organization)
    await db.flush()

    membership = OrganizationMember(
        organization_id=organization.id,
        user_id=current_user.id,
        role=perms.ROLE_OWNER,
    )
    db.add(membership)
    current_user.active_organization_id = organization.id

    # There's no onboarding step after this — unlike a fresh signup, the
    # sidebar "create workspace" action drops the caller straight into the new
    # workspace. Without a trial started here it would sit with zero
    # subscription rows and immediately look like a lapsed subscription
    # instead of a brand new one. Best-effort: eligibility is the same
    # per-account rule as the explicit "Start trial" button, so a caller who
    # already used theirs elsewhere just gets a plan-less workspace, same as
    # before this existed.
    granted_trial = False
    try:
        await grant_trial(db, organization_id=organization.id, user=current_user)
        granted_trial = True
    except TrialUnavailable as exc:
        logger.info(
            "No trial granted for new workspace %s (owner %s): %s",
            organization.id,
            current_user.id,
            exc.reason,
        )

    await db.commit()
    await db.refresh(organization)
    await db.refresh(membership)
    if granted_trial:
        invalidate_entitlements(organization.id)

    return await _detail(db, organization, membership)


@router.post("/current/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_workspace(
    workspace: WorkspaceContext = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Leave the current workspace.

    The owner cannot walk away — that would strand the workspace with no one
    able to manage billing or members, and ownership can't be handed on. The
    owner's only way out is deleting the workspace.
    """
    if workspace.is_owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The owner can't leave their own workspace. Delete the workspace instead.",
        )

    await db.delete(workspace.membership)
    # Point them somewhere valid so the next request doesn't dead-end.
    workspace.user.active_organization_id = None
    await db.commit()


@router.delete("/current", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_workspace(
    workspace: WorkspaceContext = Depends(require_permission(perms.WORKSPACE_DELETE)),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate the current workspace. Owner only.

    Soft-deactivated rather than dropped so calls, recordings, and invoices stay
    attributable. A user's last workspace is protected — deleting it would leave
    them with nowhere to work.
    """
    remaining = [
        m
        for m in await list_memberships(db, workspace.user.id)
        if m.organization is not None
        and m.organization.is_active
        and m.organization_id != workspace.organization_id
    ]
    if not remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your only workspace",
        )

    workspace.organization.is_active = False
    workspace.user.active_organization_id = remaining[0].organization_id
    await db.commit()
