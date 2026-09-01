"""
User profile endpoints — the "Settings → Profile" surface.

Covers the current user's own account: read/update profile, change password,
and delete (deactivate) the account. Organization-scoped concerns (team,
API keys) live in their own routers.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select, and_
import logging

from app.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import get_password_hash, verify_password
from app.core.urls import public_base_url
from app.models.user import User, Organization
from app.models.subscription import Subscription, LIVE_STATUSES, STATUS_CANCELED
from app.schemas.user import UserResponse, UserUpdate, PasswordChange
from app.services.billing import StripeService, get_stripe_service
from app.services.storage import (
    MAX_AVATAR_BYTES,
    StorageError,
    delete_avatar,
    store_avatar,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's profile fields.

    Only the fields present in the request body are changed (partial update).
    Email is intentionally not editable here.
    """
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_my_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password.

    Users who already have a password must supply the correct current password.
    Social-login users (no local password) can set one without a current password.
    """
    if current_user.hashed_password:
        if not payload.current_password or not verify_password(
            payload.current_password, current_user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

    current_user.hashed_password = get_password_hash(payload.new_password)
    # Changing a password is how someone responds to "I think another person
    # has access to my account", so it has to end that access. Without this the
    # old password stopped working while every session it had already opened
    # carried on untouched for up to 30 days.
    #
    # The caller's own token is invalidated too, so the client must sign in
    # again with the new password — which is the expected outcome of this
    # action, not a side effect.
    current_user.token_version = (current_user.token_version or 0) + 1
    await db.commit()


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate (soft-delete) the current user's account.

    We deactivate rather than hard-delete so historical calls/agents remain
    attributable and the action is reversible by support. The user can no longer
    authenticate once ``is_active`` is False.
    
    This also bumps the token version to immediately invalidate any outstanding sessions,
    and deactivates any organizations where the user is the owner, canceling any active 
    subscriptions on those organizations to prevent further billing.
    """
    now = datetime.utcnow()
    current_user.is_active = False
    current_user.deleted_at = now
    
    # Invalidate all existing tokens immediately
    current_user.token_version = (current_user.token_version or 0) + 1

    # Find organizations where this user is the owner
    result = await db.execute(
        select(Organization).where(Organization.owner_id == current_user.id)
    )
    organizations = result.scalars().all()
    
    for org in organizations:
        org.is_active = False
        org.updated_at = now
        
        # Check for live subscriptions in this organization
        sub_result = await db.execute(
            select(Subscription).where(
                and_(
                    Subscription.organization_id == org.id,
                    Subscription.status.in_(LIVE_STATUSES),
                )
            )
        )
        subscriptions = sub_result.scalars().all()
        for subscription in subscriptions:
            trial_without_stripe = subscription.stripe_subscription_id is None
            if trial_without_stripe:
                subscription.status = STATUS_CANCELED
                subscription.canceled_at = now
                subscription.ended_at = now
                subscription.current_period_end = min(subscription.current_period_end, now)
            else:
                try:
                    stripe_service = await get_stripe_service()
                    await stripe_service.cancel_subscription(
                        db=db, subscription_id=subscription.id, immediate=True
                    )
                    await db.refresh(subscription)
                    subscription.canceled_at = subscription.canceled_at or now
                    subscription.cancel_at_period_end = False
                except Exception as e:
                    logger.error("Failed to cancel Stripe subscription %s for org %s: %s", subscription.id, org.id, e)

    await db.commit()


@router.post("/me/avatar", response_model=UserResponse)
async def upload_my_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Replace the authenticated user's profile picture with an uploaded image.

    The upload is decoded, flattened, resized and re-encoded before it is
    stored, so what lands in the bucket is a plain PNG built from pixels — no
    EXIF (a phone photo carries GPS), no trailing payload, no SVG.

    Reading is capped rather than trusting ``Content-Length``, which the client
    controls: we stop at one byte past the limit instead of buffering whatever
    arrives.
    """
    raw = await file.read(MAX_AVATAR_BYTES + 1)
    if len(raw) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Image is too large. Choose one under "
                f"{MAX_AVATAR_BYTES // (1024 * 1024)}MB."
            ),
        )

    previous = current_user.avatar_url
    try:
        current_user.avatar_url = store_avatar(
            current_user.id,
            raw,
            file.content_type,
            # This API's own origin. The locally-stored file is served by *this*
            # app, not by the frontend, so the URL has to be absolute or the
            # browser looks for it on the frontend's origin and gets a 404 —
            # and it has to carry the scheme the *browser* used, or an https
            # dashboard refuses to load an http image.
            public_base=public_base_url(request),
        )
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    current_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)

    # Only after the new one is committed — a failed delete must not cost the
    # user the picture they just uploaded.
    delete_avatar(previous)
    return current_user


@router.delete("/me/avatar", response_model=UserResponse)
async def delete_my_avatar(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove the profile picture and fall back to the initials placeholder."""
    previous = current_user.avatar_url
    current_user.avatar_url = None
    current_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)

    delete_avatar(previous)
    return current_user
