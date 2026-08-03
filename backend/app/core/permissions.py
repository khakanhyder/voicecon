"""
Workspace roles and the permission matrix they grant.

One place decides what each role may do, so the API, the tests, and the
frontend (via ``GET /workspaces/current``) can never drift apart.

Roles are a strict hierarchy — ``owner > admin > member > viewer`` — but
permissions are *not* purely hierarchical: a few owner-only capabilities
(deleting the workspace, transferring ownership, touching another owner or
admin) are deliberately withheld from admins. Anything that mutates who holds
power in the workspace belongs to the owner alone.
"""
from __future__ import annotations

from typing import Dict, FrozenSet

# ---- Roles ----
ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLE_VIEWER = "viewer"

ROLE_HIERARCHY: Dict[str, int] = {
    ROLE_VIEWER: 0,
    ROLE_MEMBER: 1,
    ROLE_ADMIN: 2,
    ROLE_OWNER: 3,
}

ALL_ROLES = frozenset(ROLE_HIERARCHY)

#: Roles that may be handed out via invite or a role change. "owner" is never
#: assignable — it moves only through an explicit ownership transfer.
ASSIGNABLE_ROLES = frozenset({ROLE_ADMIN, ROLE_MEMBER, ROLE_VIEWER})


# ---- Permissions ----
# Resource permissions. ":read" is view-only; ":write" covers create/update;
# ":delete" is split out where destroying data deserves its own gate.
AGENTS_READ = "agents:read"
AGENTS_WRITE = "agents:write"
AGENTS_DELETE = "agents:delete"

CALLS_READ = "calls:read"
CALLS_WRITE = "calls:write"

PHONE_NUMBERS_READ = "phone_numbers:read"
PHONE_NUMBERS_WRITE = "phone_numbers:write"

WORKFLOWS_READ = "workflows:read"
WORKFLOWS_WRITE = "workflows:write"
WORKFLOWS_EXECUTE = "workflows:execute"

TOOLS_READ = "tools:read"
TOOLS_WRITE = "tools:write"

KNOWLEDGE_READ = "knowledge:read"
KNOWLEDGE_WRITE = "knowledge:write"

INTEGRATIONS_READ = "integrations:read"
INTEGRATIONS_WRITE = "integrations:write"

ANALYTICS_READ = "analytics:read"

# Workspace administration.
TEAM_READ = "team:read"
TEAM_MANAGE = "team:manage"  # invite, change roles, remove members
TEAM_MANAGE_ADMINS = "team:manage_admins"  # act on a member who is admin/owner

BILLING_READ = "billing:read"
BILLING_MANAGE = "billing:manage"

API_KEYS_READ = "api_keys:read"
API_KEYS_MANAGE = "api_keys:manage"

WORKSPACE_READ = "workspace:read"
WORKSPACE_MANAGE = "workspace:manage"  # rename, settings
WORKSPACE_DELETE = "workspace:delete"
WORKSPACE_TRANSFER_OWNERSHIP = "workspace:transfer_ownership"


_READ_ONLY: FrozenSet[str] = frozenset(
    {
        AGENTS_READ,
        CALLS_READ,
        PHONE_NUMBERS_READ,
        WORKFLOWS_READ,
        TOOLS_READ,
        KNOWLEDGE_READ,
        INTEGRATIONS_READ,
        ANALYTICS_READ,
        TEAM_READ,
        WORKSPACE_READ,
    }
)

_CONTRIBUTOR: FrozenSet[str] = _READ_ONLY | {
    AGENTS_WRITE,
    AGENTS_DELETE,
    CALLS_WRITE,
    PHONE_NUMBERS_WRITE,
    WORKFLOWS_WRITE,
    WORKFLOWS_EXECUTE,
    TOOLS_WRITE,
    KNOWLEDGE_WRITE,
    INTEGRATIONS_WRITE,
    API_KEYS_READ,
}

_ADMIN: FrozenSet[str] = _CONTRIBUTOR | {
    TEAM_MANAGE,
    API_KEYS_MANAGE,
    BILLING_READ,
    WORKSPACE_MANAGE,
}

#: Owner-only. Admins are intentionally excluded: these either transfer power
#: or destroy the workspace.
_OWNER_ONLY: FrozenSet[str] = frozenset(
    {
        TEAM_MANAGE_ADMINS,
        BILLING_MANAGE,
        WORKSPACE_DELETE,
        WORKSPACE_TRANSFER_OWNERSHIP,
    }
)

_OWNER: FrozenSet[str] = _ADMIN | _OWNER_ONLY

ROLE_PERMISSIONS: Dict[str, FrozenSet[str]] = {
    ROLE_VIEWER: _READ_ONLY,
    ROLE_MEMBER: _CONTRIBUTOR,
    ROLE_ADMIN: _ADMIN,
    ROLE_OWNER: _OWNER,
}

ALL_PERMISSIONS: FrozenSet[str] = _OWNER


def permissions_for(role: str) -> FrozenSet[str]:
    """Permissions granted by ``role``. Unknown roles get nothing."""
    return ROLE_PERMISSIONS.get((role or "").lower(), frozenset())


def has_permission(role: str, permission: str) -> bool:
    return permission in permissions_for(role)


def role_rank(role: str) -> int:
    """Numeric rank for hierarchy comparisons. Unknown roles rank lowest."""
    return ROLE_HIERARCHY.get((role or "").lower(), -1)


def outranks(actor_role: str, target_role: str) -> bool:
    """True when ``actor_role`` sits strictly above ``target_role``."""
    return role_rank(actor_role) > role_rank(target_role)


def can_act_on(actor_role: str, target_role: str) -> bool:
    """Whether ``actor_role`` may change or remove a member holding ``target_role``.

    Managing a peer or a superior is forbidden — that is what stops an admin
    from demoting or removing the owner, or from turning on a fellow admin.
    The owner is above everyone, so only the owner may act on an admin.
    """
    if not has_permission(actor_role, TEAM_MANAGE):
        return False
    if role_rank(target_role) >= role_rank(ROLE_ADMIN):
        return has_permission(actor_role, TEAM_MANAGE_ADMINS)
    return outranks(actor_role, target_role)
