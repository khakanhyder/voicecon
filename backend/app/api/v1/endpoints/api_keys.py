"""
API key management endpoints — the "Settings → API Keys" surface.

Keys are scoped to the current user's organization. The full secret is shown
exactly once (on create/regenerate); afterwards only the ``vcon_...`` prefix is
returned for display. Storage keeps a bcrypt hash of the full key (never the
plaintext), matching ``core.security.generate_api_key`` / ``verify_api_key``.
"""
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_current_user, get_current_org_id
from app.core.security import generate_api_key
from app.models.user import User, ApiKey
from app.schemas.user import ApiKeyCreate, ApiKeyResponse, ApiKeyCreateResponse

router = APIRouter()

# Length of the displayed key prefix; must match the lookup slice used by
# ``core.dependencies.verify_api_key`` (token[:12]).
KEY_PREFIX_LEN = 12


async def _get_owned_key(db: AsyncSession, key_id: uuid.UUID, org_id: uuid.UUID) -> ApiKey:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.organization_id == org_id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    return api_key


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
    plain_key, key_hash = generate_api_key()

    api_key = ApiKey(
        user_id=current_user.id,
        organization_id=org_id,
        name=payload.name,
        key_hash=key_hash,
        key_prefix=plain_key[:KEY_PREFIX_LEN],
        scopes=payload.scopes or [],
        expires_at=payload.expires_at,
        is_active=True,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyCreateResponse(**ApiKeyResponse.model_validate(api_key).model_dump(), key=plain_key)


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
