"""
User profile endpoints — the "Settings → Profile" surface.

Covers the current user's own account: read/update profile, change email
(verified by a code sent to the new address), change password, and deactivate
the account. Organization-scoped concerns (team,
API keys) live in their own routers.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select, and_, update
from sqlalchemy.exc import IntegrityError
import asyncio
import logging

from app.database import get_db
from app.core.dependencies import get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_account_deactivation_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    session_scope,
    verify_account_deactivation_token,
    verify_password,
    SCOPE_APP,
)
from app.core.urls import public_base_url
from app.models.user import User, Organization
from app.models.subscription import Subscription
from app.schemas.auth import LoginResponse, SendEmailCodeResponse
from app.schemas.user import (
    DeactivationConfirm,
    DeactivationResult,
    DeactivationTerms,
    DeactivationVerify,
    EmailChangeConfirm,
    EmailChangeRequest,
    PasswordChange,
    UserResponse,
    UserUpdate,
)
from app.services.auth import login_throttle
from app.services.auth.verification import (
    CODE_TTL_MINUTES,
    PURPOSE_ACCOUNT_DEACTIVATION,
    PURPOSE_EMAIL_CHANGE,
    RateLimited,
    VerificationError,
    confirm_code,
    issue_code,
    normalize_email,
)
from app.services.email.service import email_service
from app.services.account_deletion import deactivate_account, retention_days, support_email
from app.services.billing import StripeService
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
    Email is intentionally not editable here: it changes only through the
    verified flow below (``UserUpdate`` has no ``email`` field).
    """
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)
    return current_user


# ---------------------------------------------------------------------------
# Changing the account's email address
#
# Two steps, and the account does not move until the second one succeeds:
#   1. /me/email/change-request  emails a code to the NEW address.
#   2. /me/email/change-confirm  takes that code and changes the address.
# Until then the current address keeps working and nothing on the account has
# changed, so abandoning the flow needs no cleanup.
# ---------------------------------------------------------------------------

EMAIL_TAKEN = "That email address is already used by another account."


def _refuse_api_key(request: Request) -> None:
    """An API key acts for a workspace; it must not be able to move the login
    of the person who created it."""
    principal = getattr(request.state, "principal", None)
    if principal is not None and getattr(principal, "api_key", None) is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sign in to change your email address. An API key cannot do this.",
        )


def _session_scope_of(request: Request) -> str:
    """The scope of the session making the request, so the replacement tokens
    are issued for the same front door."""
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if not token:
        return SCOPE_APP
    try:
        return session_scope(decode_token(token) or {})
    except Exception:
        return SCOPE_APP


async def _email_taken(db: AsyncSession, email: str, user: User) -> bool:
    result = await db.execute(
        select(User.id).where(and_(User.email == email, User.id != user.id))
    )
    return result.first() is not None


@router.post("/me/email/change-request", response_model=SendEmailCodeResponse)
async def request_email_change(
    payload: EmailChangeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Email a code to the address the account should move to.

    Also serves "resend": asking again retires the earlier code and sends a new
    one, within the per-address cooldown and hourly cap.
    """
    _refuse_api_key(request)
    new_email = normalize_email(str(payload.new_email))

    if new_email == normalize_email(current_user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That is already your email address.",
        )

    if current_user.hashed_password:
        if not payload.current_password or not verify_password(
            payload.current_password, current_user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your password is incorrect.",
            )

    if await _email_taken(db, new_email, current_user):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN)

    try:
        code, _ = await issue_code(
            db, new_email, PURPOSE_EMAIL_CHANGE, subject=str(current_user.id)
        )
    except RateLimited as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=e.public_message,
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    except VerificationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.public_message)

    sent = await email_service.send_verification_code(
        to_email=new_email,
        code=code,
        expires_minutes=CODE_TTL_MINUTES,
        purpose="email_change",
        recipient_name=current_user.full_name,
    )
    if not sent and email_service.delivery_enabled:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="We couldn't send the confirmation email. Please try again.",
        )

    expose = settings.DEBUG and not email_service.delivery_enabled
    return SendEmailCodeResponse(
        message=f"We sent a code to {new_email}.",
        expires_in_minutes=CODE_TTL_MINUTES,
        debug_code=code if expose else None,
    )


async def _sync_stripe_customer_email(customer_ids: list, old_email: str, new_email: str) -> None:
    """Point billing receipts at the new address. Best effort: the account has
    already changed, and a Stripe outage must not undo or fail that."""
    try:
        import stripe

        if not stripe.api_key:
            return
        for customer_id in customer_ids:
            customer = await asyncio.to_thread(stripe.Customer.retrieve, customer_id)
            # A customer given a separate billing address keeps it.
            if (getattr(customer, "email", None) or "").lower() == old_email:
                await asyncio.to_thread(stripe.Customer.modify, customer_id, email=new_email)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Could not update Stripe customer email: {e}")


@router.post("/me/email/change-confirm", response_model=LoginResponse)
async def confirm_email_change(
    payload: EmailChangeConfirm,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the account's email, given the code sent to the new address.

    Every other session is signed out, because a change of address is also how
    an account is taken over. The caller gets fresh tokens in the response and
    stays signed in.
    """
    _refuse_api_key(request)
    new_email = normalize_email(str(payload.new_email))
    old_email = normalize_email(current_user.email)

    if new_email == old_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That is already your email address.",
        )

    try:
        await confirm_code(
            db, new_email, PURPOSE_EMAIL_CHANGE, payload.code, subject=str(current_user.id)
        )
    except VerificationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.public_message)

    # Someone may have registered the address while the code was in the inbox.
    if await _email_taken(db, new_email, current_user):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN)

    user_id = current_user.id
    scope = _session_scope_of(request)
    current_user.email = new_email
    current_user.is_verified = True
    current_user.email_verified_at = datetime.utcnow()
    current_user.token_version = (current_user.token_version or 0) + 1

    # Workspaces billed to the old address follow the owner to the new one.
    await db.execute(
        update(Organization)
        .where(
            and_(
                Organization.owner_id == user_id,
                Organization.billing_email == old_email,
            )
        )
        .values(billing_email=new_email)
    )

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN)
    await db.refresh(current_user)

    # Failed sign-ins are counted per address; the old address is no longer
    # this account's, so its count must not follow the user.
    login_throttle.clear(old_email)
    logger.info(f"User {user_id} changed email from {old_email} to {new_email}")

    await email_service.send_email_changed_notice(
        old_email=old_email,
        new_email=new_email,
        recipient_name=current_user.full_name,
    )

    customers = await db.execute(
        select(Subscription.stripe_customer_id)
        .join(Organization, Organization.id == Subscription.organization_id)
        .where(
            and_(
                Organization.owner_id == user_id,
                Subscription.stripe_customer_id.is_not(None),
            )
        )
    )
    customer_ids = sorted({c for c in customers.scalars().all() if c})
    if customer_ids:
        await _sync_stripe_customer_email(customer_ids, old_email, new_email)

    return LoginResponse(
        access_token=create_access_token(
            subject=str(current_user.id),
            token_version=current_user.token_version,
            scope=scope,
        ),
        refresh_token=create_refresh_token(
            subject=str(current_user.id),
            token_version=current_user.token_version,
            scope=scope,
        ),
        token_type="bearer",
        user={
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "avatar_url": current_user.avatar_url,
            "is_verified": current_user.is_verified,
            "auth_provider": current_user.auth_provider,
            "is_new": False,
        },
    )


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


# ---------------------------------------------------------------------------
# Deactivating the account
#
# Three steps, and nothing happens to the account until the last one:
#   1. /me/deactivation/code     (accounts with no password only) emails a code.
#   2. /me/deactivation/verify   checks the password, or that code, and returns
#                                the terms plus a short-lived token.
#   3. /me/deactivate            takes that token and deactivates.
#
# The token is what ties step 3 to step 2: the confirmation cannot be sent by a
# client that skipped the identity check. The account is then recoverable by
# support until its deletion date (see services/account_deletion).
# ---------------------------------------------------------------------------

def _deactivation_throttle_key(user: User) -> str:
    """Separate from the sign-in lockout: mistyping here must not lock the
    person out of signing in, and vice versa."""
    return f"deactivate:{user.id}"


def _refuse_platform_admin(user: User) -> None:
    """A staff account is never swept up by the automatic deletion, so it must
    not be able to enter the state that leads there."""
    if user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Platform admin accounts cannot be deactivated here. "
                   "Ask another admin to revoke admin access first.",
        )


def _deactivation_terms(user: User) -> DeactivationTerms:
    days = retention_days()
    return DeactivationTerms(
        deactivation_token=create_account_deactivation_token(str(user.id), user.token_version),
        retention_days=days,
        deletion_date=datetime.utcnow() + timedelta(days=days),
        support_email=support_email(),
    )


@router.post("/me/deactivation/code", response_model=SendEmailCodeResponse)
async def send_deactivation_code(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Email a confirmation code to an account that has no password to ask for
    (one that signs in with Google or Apple)."""
    _refuse_api_key(request)
    if current_user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter your password to continue.",
        )

    try:
        code, _ = await issue_code(
            db, current_user.email, PURPOSE_ACCOUNT_DEACTIVATION, subject=str(current_user.id)
        )
    except RateLimited as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=e.public_message,
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    except VerificationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.public_message)

    sent = await email_service.send_verification_code(
        to_email=current_user.email,
        code=code,
        expires_minutes=CODE_TTL_MINUTES,
        purpose="account_deactivation",
        recipient_name=current_user.full_name,
    )
    if not sent and email_service.delivery_enabled:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="We couldn't send the confirmation email. Please try again.",
        )

    expose = settings.DEBUG and not email_service.delivery_enabled
    return SendEmailCodeResponse(
        message=f"We sent a code to {current_user.email}.",
        expires_in_minutes=CODE_TTL_MINUTES,
        debug_code=code if expose else None,
    )


@router.post("/me/deactivation/verify", response_model=DeactivationTerms)
async def verify_deactivation(
    payload: DeactivationVerify,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check it is really the account holder, and return what they are agreeing to.

    Changes nothing on the account. Someone at an unlocked laptop must not be
    able to close an account, so a signed-in session alone is not enough.
    """
    _refuse_api_key(request)
    _refuse_platform_admin(current_user)

    if current_user.hashed_password:
        key = _deactivation_throttle_key(current_user)
        locked_for = login_throttle.seconds_until_unlocked(key)
        if locked_for:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many incorrect attempts. Please try again shortly.",
                headers={"Retry-After": str(locked_for)},
            )
        if not payload.password or not verify_password(
            payload.password, current_user.hashed_password
        ):
            login_throttle.record_failure(key)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your password is incorrect.",
            )
        login_throttle.clear(key)
    else:
        if not payload.code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Enter the code we emailed you.",
            )
        try:
            await confirm_code(
                db,
                current_user.email,
                PURPOSE_ACCOUNT_DEACTIVATION,
                payload.code,
                subject=str(current_user.id),
            )
        except VerificationError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.public_message)

    return _deactivation_terms(current_user)


@router.post("/me/deactivate", response_model=DeactivationResult)
async def deactivate_my_account(
    payload: DeactivationConfirm,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate the account, after the terms from ``/me/deactivation/verify``
    have been shown and accepted.

    Nothing is erased. The account is signed out everywhere and cannot sign in,
    the workspaces it owns are switched off and their subscriptions cancelled,
    and it is permanently deleted on the returned date unless support
    reactivates it first.
    """
    _refuse_api_key(request)
    if not verify_account_deactivation_token(
        payload.deactivation_token, str(current_user.id), current_user.token_version
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That confirmation has expired. Please verify it's you again.",
        )
    _refuse_platform_admin(current_user)

    now = datetime.utcnow()
    email = current_user.email
    name = current_user.full_name
    days = retention_days()
    scheduled = await deactivate_account(db, current_user, now)
    await db.commit()

    # After the commit and never fatal: the account is deactivated either way.
    try:
        await email_service.send_account_deactivated(
            to_email=email, deletion_date=scheduled, retention_days=days, recipient_name=name
        )
    except Exception:
        logger.exception("Could not send the deactivation notice to user %s", current_user.id)

    return DeactivationResult(
        deactivated_at=now,
        deletion_date=scheduled,
        retention_days=days,
        support_email=support_email(),
    )


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
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.public_message
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
