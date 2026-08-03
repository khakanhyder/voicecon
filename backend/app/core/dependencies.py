"""
FastAPI dependencies for authentication, authorization, and common operations.
"""
from typing import Optional, Generator
import uuid as _uuid
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.database import get_db
from app.core.config import settings
from app.core.security import decode_token
from app.core.exceptions import credentials_exception
from app.core import permissions as perms
from app.core.workspace import (
    ORG_HEADER,
    WorkspaceContext,
    parse_org_header,
    resolve_workspace,
)

# OAuth2 scheme for JWT tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

# HTTP Bearer scheme
bearer_scheme = HTTPBearer()


async def get_current_user_id(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> str:
    """
    Get current user ID from JWT token.

    Raises:
        HTTPException: If token is invalid or user not found
    """
    payload = decode_token(token)

    if payload is None:
        raise credentials_exception()

    user_id: str = payload.get("sub")
    token_type: str = payload.get("type")

    if user_id is None or token_type != "access":
        raise credentials_exception()

    return user_id


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user from database.

    Returns:
        User model instance

    Raises:
        HTTPException: If user not found or inactive
    """
    from app.models.user import User

    try:
        user_uuid = _uuid.UUID(user_id)
    except (ValueError, AttributeError):
        raise credentials_exception()

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    return user


async def get_current_active_user(
    current_user = Depends(get_current_user)
):
    """
    Get current active user.
    Alias for get_current_user for clarity.
    """
    return current_user


async def get_current_verified_user(
    current_user = Depends(get_current_user)
):
    """
    Get current verified user (email verified).

    Raises:
        HTTPException: If user email is not verified
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified"
        )
    return current_user


# ---- Workspace (organization) context ----
# Every organization-scoped endpoint hangs off ``get_workspace``. The resolution
# rules (header override → active workspace → deterministic default) live in
# app.core.workspace; this is just the FastAPI wiring.


async def get_workspace(
    x_organization_id: Optional[str] = Header(default=None, alias=ORG_HEADER),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceContext:
    """Resolve the workspace this request acts inside, plus the caller's role in it."""
    return await resolve_workspace(
        db, current_user, parse_org_header(x_organization_id)
    )


async def get_current_user_organization(
    workspace: WorkspaceContext = Depends(get_workspace),
):
    """The Organization the request is acting inside."""
    return workspace.organization


async def get_current_org_id(
    workspace: WorkspaceContext = Depends(get_workspace),
) -> _uuid.UUID:
    """The id of the organization the request is acting inside.

    This is the workspace the user has switched to — not merely "some org they
    belong to" — so an invited member's calls land in the shared workspace
    rather than their own.
    """
    return workspace.organization_id


async def get_current_membership(
    workspace: WorkspaceContext = Depends(get_workspace),
):
    """The caller's OrganizationMember row in the current workspace."""
    return workspace.membership


def require_permission(permission: str):
    """Dependency factory: 403 unless the caller's role grants ``permission``.

    Returns the :class:`WorkspaceContext`, so an endpoint gets the authorization
    check and the resolved organization id from a single dependency.
    """

    async def permission_checker(
        workspace: WorkspaceContext = Depends(get_workspace),
    ) -> WorkspaceContext:
        workspace.require(permission)
        return workspace

    return permission_checker


#: HTTP methods that only read. Everything else mutates and needs write rights.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def workspace_guard(read_permission: str, write_permission: str):
    """Router-level guard: reads need ``read_permission``, writes ``write_permission``.

    Attached once per router in ``app.api.v1.api`` so authorization can't be
    forgotten on a newly added endpoint — the default for any route in a
    guarded router is "protected", not "open". Endpoints needing something
    finer (billing, team) still add their own :func:`require_permission`.
    """

    async def guard(
        request: Request,
        workspace: WorkspaceContext = Depends(get_workspace),
    ) -> WorkspaceContext:
        required = (
            read_permission if request.method in SAFE_METHODS else write_permission
        )
        workspace.require(required)
        return workspace

    return guard


def require_workspace_role(minimum_role: str):
    """Dependency factory requiring a minimum role in the *current* workspace."""

    async def role_checker(
        workspace: WorkspaceContext = Depends(get_workspace),
    ) -> WorkspaceContext:
        if perms.role_rank(workspace.role) < perms.role_rank(minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {minimum_role} role or higher",
            )
        return workspace

    return role_checker


def require_role(required_role: str):
    """Legacy alias: require a minimum role, returning the *user*.

    Kept so existing call sites keep working; new code should depend on
    :func:`require_permission` instead, which is explicit about the capability
    rather than the rank.
    """

    async def role_checker(
        workspace: WorkspaceContext = Depends(require_workspace_role(required_role)),
    ):
        return workspace.user

    return role_checker


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> str:
    """
    Verify API key from request header.

    Returns:
        user_id: ID of the user who owns the API key

    Raises:
        HTTPException: If API key is invalid or inactive
    """
    from app.models.user import ApiKey
    from app.core.security import verify_api_key as verify_key
    from datetime import datetime

    token = credentials.credentials

    if not token.startswith("vcon_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format"
        )

    # Get API key from database
    prefix = token[:12]  # e.g., "vcon_abc..."
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_prefix == prefix)
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    # Verify the full key
    if not verify_key(token, api_key.key_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    # Check if active
    if not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is inactive"
        )

    # Check expiration
    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired"
        )

    # Update last used timestamp
    api_key.last_used_at = datetime.utcnow()
    await db.commit()

    return str(api_key.user_id)


def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme)
):
    """
    Get user if authenticated, otherwise return None.
    Useful for optional authentication endpoints.
    """
    if token is None:
        return None

    payload = decode_token(token)
    if payload is None:
        return None

    return payload.get("sub")
