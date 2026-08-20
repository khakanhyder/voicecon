"""
FastAPI dependencies for authentication, authorization, and common operations.

Two credentials reach this module and both end up as the same thing — a
:class:`Principal` naming the acting user:

* a **login token** (JWT) from ``/auth/login``, used by the dashboard;
* an **API key** (``vcon_...``) minted in Settings → API Keys, used by servers
  and integrations that can't sit through a login.

Either may be presented as ``Authorization: Bearer <credential>``; a key may
also come in as ``X-API-Key`` for clients that reserve ``Authorization`` for
something else. Endpoints depend on ``get_current_user`` / ``get_workspace``
and don't care which was used — the difference is enforced in one place, by
:meth:`WorkspaceContext.permissions`, which narrows an API key to its scopes
and refuses the escalation permissions outright.
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Generator
import uuid as _uuid
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.database import get_db
from app.core.config import settings
from app.core.security import decode_token, token_version_matches
from app.core.exceptions import credentials_exception
from app.core import permissions as perms
from app.core.api_keys import API_KEY_HEADER, authenticate_api_key, looks_like_api_key
from app.core.workspace import (
    ORG_HEADER,
    WorkspaceContext,
    parse_org_header,
    resolve_api_key_workspace,
    resolve_workspace,
)

# OAuth2 scheme for JWT tokens.
# ``auto_error=False`` so a request carrying only ``X-API-Key`` isn't rejected
# before we get a chance to look at it; the 401 for "no credential at all" is
# raised by ``get_principal`` instead.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=False
)

# HTTP Bearer scheme
bearer_scheme = HTTPBearer()


if TYPE_CHECKING:  # models import this module's siblings; keep the cycle out of runtime
    from app.models.user import ApiKey, User


@dataclass(frozen=True)
class Principal:
    """Who is making this request, and with what kind of credential."""

    user: "User"
    api_key: Optional["ApiKey"] = None

    @property
    def is_api_key(self) -> bool:
        return self.api_key is not None


async def _user_from_jwt(token: str, db: AsyncSession):
    """Resolve a login token to its user, or raise 401."""
    from app.models.user import User

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception()

    user_id: str = payload.get("sub")
    token_type: str = payload.get("type")
    if user_id is None or token_type != "access":
        raise credentials_exception()

    try:
        user_uuid = _uuid.UUID(user_id)
    except (ValueError, AttributeError):
        raise credentials_exception()

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception()
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    if not token_version_matches(payload, user):
        # Signed out everywhere, password changed, or password reset since this
        # token was issued. Indistinguishable from any other invalid credential
        # on purpose — the client's job is to re-authenticate either way.
        raise credentials_exception()
    return user


def _presented_key(token: Optional[str], x_api_key: Optional[str]) -> Optional[str]:
    """The API key this request presented, if any.

    An ``X-API-Key`` header is unambiguous, so it wins. Otherwise the bearer
    credential is routed by its shape: ``vcon_...`` is a key, anything else is
    a JWT. Presenting a key both ways is a mistake worth surfacing rather than
    silently resolving.
    """
    if x_api_key and token and looks_like_api_key(token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Send an API key either as {API_KEY_HEADER} or as a bearer token, not both",
        )
    return x_api_key or (token if looks_like_api_key(token) else None)


async def get_principal(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    x_api_key: Optional[str] = Header(default=None, alias=API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    """Authenticate the request by API key or login token, in that order.

    The result is stashed on ``request.state`` so ``get_optional_api_key`` can
    reuse it instead of bcrypt-verifying the same key a second time.
    """
    raw_key = _presented_key(token, x_api_key)
    if raw_key:
        api_key = await authenticate_api_key(db, raw_key)
        principal = Principal(user=api_key.user, api_key=api_key)
    else:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        principal = Principal(user=await _user_from_jwt(token, db))

    request.state.principal = principal
    return principal


async def get_optional_api_key(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    x_api_key: Optional[str] = Header(default=None, alias=API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
):
    """The :class:`ApiKey` behind this request, or None if it used a login token.

    Deliberately *not* built on ``get_principal``. Authentication is the job of
    ``get_current_user``, which every protected endpoint already depends on —
    and which tests override to inject an acting user. Routing this through
    ``get_principal`` too would make that override unreachable and 401 every
    such test, so this only speaks up when a key was actually presented and
    stays silent otherwise.
    """
    cached: Optional[Principal] = getattr(request.state, "principal", None)
    if cached is not None:
        return cached.api_key

    raw_key = _presented_key(token, x_api_key)
    if not raw_key:
        return None

    api_key = await authenticate_api_key(db, raw_key)
    request.state.principal = Principal(user=api_key.user, api_key=api_key)
    return api_key


async def get_current_user_id(
    principal: Principal = Depends(get_principal),
) -> str:
    """The acting user's id, however they authenticated."""
    return str(principal.user.id)


async def get_current_user(
    principal: Principal = Depends(get_principal),
):
    """
    Get current user from database.

    Returns:
        User model instance

    Raises:
        HTTPException: If the credential is invalid, or the user is inactive
    """
    return principal.user


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
    api_key = Depends(get_optional_api_key),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceContext:
    """Resolve the workspace this request acts inside, plus the caller's role in it.

    An API key is bound to the workspace it was minted in, so there is nothing
    to resolve and nothing to switch — see ``resolve_api_key_workspace``. Only
    a login token gets the header → active → default resolution chain.

    Depends on ``get_current_user`` rather than ``get_principal`` so that
    remains the one place authentication can be swapped out (tests override it
    to choose the acting user); ``get_optional_api_key`` adds the key on top
    without taking over who the caller is.
    """
    requested = parse_org_header(x_organization_id)
    if api_key is not None:
        return await resolve_api_key_workspace(db, api_key, requested)
    return await resolve_workspace(db, current_user, requested)


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


async def require_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate an endpoint that accepts *only* an API key, never a session.

    Ordinary endpoints should depend on ``get_current_user``/``get_workspace``,
    which take either credential. Reach for this only where a session must be
    refused outright — a machine-to-machine surface that should not be callable
    from a logged-in browser tab.
    """
    return await authenticate_api_key(db, credentials.credentials)


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    x_api_key: Optional[str] = Header(default=None, alias=API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the acting user if the request carries a valid credential, else None.
    Useful for endpoints that serve both authenticated and anonymous callers.

    Anything malformed is treated as "anonymous" rather than an error — the
    caller opted into optional auth, so a bad credential must not 401 a request
    that would otherwise have been served.
    """
    raw_key = x_api_key or (token if looks_like_api_key(token) else None)
    if raw_key:
        try:
            api_key = await authenticate_api_key(db, raw_key)
        except HTTPException:
            return None
        return api_key.user

    if not token:
        return None

    try:
        return await _user_from_jwt(token, db)
    except HTTPException:
        return None


def get_optional_user_id(
    token: Optional[str] = Depends(oauth2_scheme)
):
    """
    Get the user id from a login token if present, otherwise None.
    Kept for call sites that only need the subject claim, with no DB round trip.
    """
    if token is None or looks_like_api_key(token):
        return None

    payload = decode_token(token)
    if payload is None:
        return None

    return payload.get("sub")
