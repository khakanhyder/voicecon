"""
API key management endpoints — the "Settings → API Keys" surface.

Keys are scoped to the current user's organization. The full secret is shown
exactly once (on create/regenerate); afterwards only the ``vcon_...`` prefix is
returned for display. Storage keeps a bcrypt hash of the full key (never the
plaintext), matching ``core.security.generate_api_key``.

Authenticating *with* a key is the other half of the feature and lives in
:mod:`app.core.api_keys`. Note that this router is deliberately unreachable by
an API key: minting and revoking credentials requires ``api_keys:manage``,
which :data:`permissions.API_KEY_FORBIDDEN` withholds from keys, so a leaked
key cannot mint replacements for itself.
"""
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.api_keys import KEY_PREFIX_LEN
from app.core.dependencies import get_current_user, get_current_org_id
from app.core import permissions as perms
from app.core.security import generate_api_key
from app.models.user import User, ApiKey
from app.schemas.user import (
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeyCreateResponse,
    ApiKeyUpdate,
)

router = APIRouter()


async def _get_owned_key(db: AsyncSession, key_id: uuid.UUID, org_id: uuid.UUID) -> ApiKey:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.organization_id == org_id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    return api_key


def _validate_scopes(scopes: List[str]) -> List[str]:
    """Reject unknown or forbidden scopes at the door.

    A key silently carrying a scope the authorizer will never honour looks like
    a working key and fails mysteriously in production, so a typo has to be an
    error here rather than a surprise later.
    """
    if not scopes:
        return []
    unknown = sorted(set(scopes) - perms.ASSIGNABLE_SCOPES)
    if unknown:
        forbidden = [s for s in unknown if s in perms.API_KEY_FORBIDDEN]
        if forbidden:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"These scopes cannot be granted to an API key: "
                    f"{', '.join(forbidden)}"
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown scopes: {', '.join(unknown)}",
        )
    return sorted(set(scopes))


def _validate_expiry(expires_at: datetime | None) -> datetime | None:
    """A key that is already expired is a mistake, not a configuration."""
    if expires_at is not None and expires_at <= datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="expires_at must be in the future",
        )
    return expires_at


@router.get("/scopes", response_model=List[str])
async def list_assignable_scopes(
    current_user: User = Depends(get_current_user),
):
    """Every scope a key may be granted.

    Published so the UI builds its picker from the server's list and can't
    offer a scope creation would reject. Defined before ``/{key_id}`` routes so
    "scopes" is never parsed as a key id.
    """
    return sorted(perms.ASSIGNABLE_SCOPES)


@router.get("", response_model=List[ApiKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """List the organization's API keys (secrets are never returned)."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.organization_id == org_id)
        .order_by(ApiKey.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key. The full secret is returned once and never again."""
    scopes = _validate_scopes(payload.scopes)
    expires_at = _validate_expiry(payload.expires_at)
    plain_key, key_hash = generate_api_key()

    api_key = ApiKey(
        user_id=current_user.id,
        organization_id=org_id,
        name=payload.name.strip(),
        key_hash=key_hash,
        key_prefix=plain_key[:KEY_PREFIX_LEN],
        scopes=scopes,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyCreateResponse(**ApiKeyResponse.model_validate(api_key).model_dump(), key=plain_key)


@router.patch("/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: uuid.UUID,
    payload: ApiKeyUpdate,
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Rename a key, change its scopes or expiry, or disable/re-enable it.

    Disabling (``is_active: false``) is the reversible half of revoking: the
    key stops authenticating immediately but can be switched back on, which is
    what you want while chasing down which integration a key belongs to.
    """
    api_key = await _get_owned_key(db, key_id, org_id)
    updates = payload.model_dump(exclude_unset=True)

    if "scopes" in updates:
        updates["scopes"] = _validate_scopes(updates["scopes"] or [])
    if "expires_at" in updates and updates["expires_at"] is not None:
        updates["expires_at"] = _validate_expiry(updates["expires_at"])
    if "name" in updates and updates["name"] is not None:
        updates["name"] = updates["name"].strip()

    for field, value in updates.items():
        setattr(api_key, field, value)

    await db.commit()
    await db.refresh(api_key)
    return api_key


@router.post("/{key_id}/regenerate", response_model=ApiKeyCreateResponse)
async def regenerate_api_key(
    key_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Rotate an existing key: the old secret stops working, a new one is returned once."""
    api_key = await _get_owned_key(db, key_id, org_id)

    plain_key, key_hash = generate_api_key()
    api_key.key_hash = key_hash
    api_key.key_prefix = plain_key[:KEY_PREFIX_LEN]
    api_key.is_active = True
    api_key.last_used_at = None
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyCreateResponse(**ApiKeyResponse.model_validate(api_key).model_dump(), key=plain_key)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Permanently revoke (delete) an API key."""
    api_key = await _get_owned_key(db, key_id, org_id)
    await db.delete(api_key)
    await db.commit()
