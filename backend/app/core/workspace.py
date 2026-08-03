"""
Workspace (organization) context for a request.

A user can belong to several workspaces — their own personal one plus any they
were invited to. Every organization-scoped endpoint needs to know *which* one
the request is acting inside, and what the caller is allowed to do there. That
resolution happens once, here, and is exposed as :class:`WorkspaceContext`.

Resolution order (first match wins):

1. ``X-Organization-Id`` request header — an explicit, per-request override.
   Lets a second browser tab stay in a different workspace, and makes the
   choice auditable. A header naming a workspace the user is not a member of
   is a hard 403; we never silently fall back to a different workspace than the
   one the client asked for.
2. ``user.active_organization_id`` — the workspace they last switched to.
3. A deterministic default: the workspace they own, else the one they joined
   first. Never an arbitrary ``LIMIT 1``, so a user with two memberships lands
   in the same place on every request.

The resolved choice is written back to ``active_organization_id`` when it
differs, so a stale or dangling pointer (membership revoked, workspace deleted)
heals itself on the next request instead of 404-ing forever.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from dataclasses import dataclass
from typing import FrozenSet, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import permissions as perms
from app.models.user import Organization, OrganizationMember, User

logger = logging.getLogger(__name__)

ORG_HEADER = "X-Organization-Id"


@dataclass(frozen=True)
class WorkspaceContext:
    """The workspace a request is acting inside, and the caller's standing in it."""

    user: User
    organization: Organization
    membership: OrganizationMember

    @property
    def organization_id(self) -> _uuid.UUID:
        return self.organization.id

    @property
    def role(self) -> str:
        return self.membership.role

    @property
    def permissions(self) -> FrozenSet[str]:
        return perms.permissions_for(self.role)

    @property
    def is_owner(self) -> bool:
        return self.role == perms.ROLE_OWNER

    def has(self, permission: str) -> bool:
        return permission in self.permissions

    def require(self, permission: str) -> None:
        """Raise 403 unless the caller's role grants ``permission``."""
        if not self.has(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Your role ({self.role}) does not permit this action "
                    f"in {self.organization.name}."
                ),
            )


def parse_org_header(raw: Optional[str]) -> Optional[_uuid.UUID]:
    if not raw or not raw.strip():
        return None
    try:
        return _uuid.UUID(raw.strip())
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{ORG_HEADER} is not a valid workspace id",
        )


async def get_membership(
    db: AsyncSession, user_id: _uuid.UUID, org_id: _uuid.UUID
) -> Optional[OrganizationMember]:
    """The user's membership row in ``org_id``, or None if they don't belong."""
    result = await db.execute(
        select(OrganizationMember)
        .options(selectinload(OrganizationMember.organization))
        .where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == org_id,
        )
    )
    return result.scalar_one_or_none()


async def list_memberships(db: AsyncSession, user_id: _uuid.UUID) -> list[OrganizationMember]:
    """All of the user's memberships, owned workspaces first, then oldest first.

    The ordering is the tie-break for the default workspace, so it must be
    stable: a user's own workspace should stay their default after they accept
    an invitation to someone else's.
    """
    result = await db.execute(
        select(OrganizationMember)
        .options(selectinload(OrganizationMember.organization))
        .where(OrganizationMember.user_id == user_id)
        .order_by(OrganizationMember.joined_at.asc(), OrganizationMember.id.asc())
    )
    memberships = list(result.scalars().all())
    memberships.sort(key=lambda m: (0 if m.role == perms.ROLE_OWNER else 1,))
    return memberships


async def resolve_workspace(
    db: AsyncSession,
    user: User,
    requested_org_id: Optional[_uuid.UUID] = None,
) -> WorkspaceContext:
    """Resolve the workspace for this request. See the module docstring."""
    # 1. Explicit override — must be a workspace the caller actually belongs to.
    if requested_org_id is not None:
        membership = await get_membership(db, user.id, requested_org_id)
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
        await _remember(db, user, membership.organization_id)
        return WorkspaceContext(user=user, organization=membership.organization, membership=membership)

    # 2. The workspace they last switched to, if it still checks out.
    if user.active_organization_id is not None:
        membership = await get_membership(db, user.id, user.active_organization_id)
        if (
            membership is not None
            and membership.organization is not None
            and membership.organization.is_active
        ):
            return WorkspaceContext(
                user=user, organization=membership.organization, membership=membership
            )
        # Dangling pointer (removed from the org, or the org went away): fall
        # through and re-derive, then heal the stored value below.
        logger.info(
            "Clearing stale active workspace %s for user %s",
            user.active_organization_id,
            user.id,
        )

    # 3. Deterministic default.
    memberships = await list_memberships(db, user.id)
    usable = [m for m in memberships if m.organization is not None and m.organization.is_active]
    if not usable:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User has no organization",
        )

    membership = usable[0]
    await _remember(db, user, membership.organization_id)
    return WorkspaceContext(user=user, organization=membership.organization, membership=membership)


async def _remember(db: AsyncSession, user: User, org_id: _uuid.UUID) -> None:
    """Persist the resolved workspace as the user's active one (no-op if unchanged)."""
    if user.active_organization_id == org_id:
        return
    user.active_organization_id = org_id
    await db.commit()


# The FastAPI wiring (``get_workspace``, ``require_permission``, ``require_role``)
# lives in app.core.dependencies, which owns ``get_current_user``. Keeping this
# module free of that import keeps the two files acyclic.
