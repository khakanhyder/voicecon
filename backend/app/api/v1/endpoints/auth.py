"""
Authentication endpoints for user login, registration, and token management.

Sign-up is two steps: the address is proved with a one-time code emailed to it
(`/auth/email/send-code` then `/auth/email/verify-code`), and the resulting
token is handed back on `/auth/register`. The same code machinery backs the
forgotten-password flow.
"""
from datetime import datetime
import logging
import uuid as _uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import (
    EMAIL_VERIFICATION_TOKEN_MINUTES,
    verify_password,
    get_password_hash,
    create_access_token,
    create_email_verification_token,
    create_refresh_token,
    decode_token,
    token_version_matches,
    verify_email_verification_token,
)
from app.core.exceptions import credentials_exception, bad_request_exception
from app.models.user import User, Organization, OrganizationMember
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    GoogleAuthRequest,
    AppleAuthRequest,
    SendEmailCodeRequest,
    SendEmailCodeResponse,
    VerifyEmailCodeRequest,
    VerifyEmailCodeResponse,
)
from app.schemas.user import UserResponse
from app.services.auth import get_oauth_service, OAuthError
from app.services.auth.verification import (
    CODE_TTL_MINUTES,
    PURPOSE_EMAIL_VERIFICATION,
    PURPOSE_PASSWORD_RESET,
    RateLimited,
    VerificationError,
    confirm_code,
    issue_code,
    normalize_email,
)
from app.services.auth import login_throttle
from app.services.auth.workspaces import unique_org_slug
from app.services.email.service import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _login_response_for(user: User, is_new: bool = False) -> LoginResponse:
    """Issue access + refresh tokens for an authenticated user."""
    return LoginResponse(
        access_token=create_access_token(
            subject=str(user.id), token_version=user.token_version
        ),
        refresh_token=create_refresh_token(
            subject=str(user.id), token_version=user.token_version
        ),
        token_type="bearer",
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "is_verified": user.is_verified,
            "auth_provider": user.auth_provider,
            "is_new": is_new,
        },
    )


async def _email_is_registered(db: AsyncSession, email: str) -> bool:
    result = await db.execute(select(User).where(User.email == normalize_email(email)))
    return result.scalar_one_or_none() is not None


def _code_delivery_response(code: str, message: str) -> SendEmailCodeResponse:
    """
    Build the response for a code that was just sent.

    Locally, with no mail transport configured, the code comes back in the body
    so the flow is usable without digging through the server log. This only
    happens with DEBUG on *and* no real provider — never in a deployment that
    can actually send mail.
    """
    expose = settings.DEBUG and not email_service.delivery_enabled
    return SendEmailCodeResponse(
        message=message,
        expires_in_minutes=CODE_TTL_MINUTES,
        debug_code=code if expose else None,
    )


@router.post("/email/send-code", response_model=SendEmailCodeResponse)
async def send_email_code(
    payload: SendEmailCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Email a one-time code to confirm an address before sign-up.

    Rejects addresses that are already registered — the caller is about to
    create an account, and `/auth/register` would refuse anyway, so failing here
    is the same disclosure with a clearer message.
    """
    email = normalize_email(payload.email)

    if payload.purpose == "password_reset":
        # Password reset has its own endpoint precisely because it must not
        # disclose whether an address exists.
        raise bad_request_exception(
            "Use /auth/password/forgot to reset a password."
        )

    if await _email_is_registered(db, email):
        raise bad_request_exception(
            "That email is already registered. Try signing in instead."
        )

    try:
        code, _ = await issue_code(db, email, PURPOSE_EMAIL_VERIFICATION)
    except RateLimited as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    except VerificationError as e:
        raise bad_request_exception(str(e))

    sent = await email_service.send_verification_code(
        to_email=email,
        code=code,
        expires_minutes=CODE_TTL_MINUTES,
        purpose="signup",
    )
    if not sent and email_service.delivery_enabled:
        # A configured mail server that failed is a real outage: say so rather
        # than leaving the user waiting for an email that will never arrive.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="We couldn't send the verification email. Please try again.",
        )

    return _code_delivery_response(code, f"We sent a code to {email}.")


@router.post("/email/verify-code", response_model=VerifyEmailCodeResponse)
async def verify_email_code(
    payload: VerifyEmailCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Check the code emailed to an address.

    On success returns a short-lived token that `/auth/register` requires, so
    an account can only be created for an address the caller has proved.
    """
    email = normalize_email(payload.email)

    try:
        await confirm_code(db, email, PURPOSE_EMAIL_VERIFICATION, payload.code)
    except VerificationError as e:
        raise bad_request_exception(str(e))

    return VerifyEmailCodeResponse(
        verified=True,
        email=email,
        email_verification_token=create_email_verification_token(email),
        expires_in_minutes=EMAIL_VERIFICATION_TOKEN_MINUTES,
    )


@router.post("/password/forgot", response_model=SendEmailCodeResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Email a code for resetting a forgotten password.

    Always reports success, whether or not the address has an account: the
    response must not tell an attacker which emails are registered.
    """
    email = normalize_email(payload.email)
    generic = "If that email has an account, we've sent a reset code to it."

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        logger.info(f"Password reset requested for unknown or inactive address {email}")
        return SendEmailCodeResponse(message=generic, expires_in_minutes=CODE_TTL_MINUTES)

    try:
        code, _ = await issue_code(db, email, PURPOSE_PASSWORD_RESET)
    except RateLimited as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    except VerificationError as e:
        raise bad_request_exception(str(e))

    await email_service.send_verification_code(
        to_email=email,
        code=code,
        expires_minutes=CODE_TTL_MINUTES,
        purpose="password_reset",
        recipient_name=user.full_name,
    )

    return _code_delivery_response(code, generic)


@router.post("/password/reset", response_model=LoginResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Set a new password using the emailed code, and sign the user in.

    Signing in immediately is the point of the flow — the user has just proved
    they control the address and chosen a password, so sending them back to the
    login form to type it again adds nothing.
    """
    email = normalize_email(payload.email)

    try:
        await confirm_code(db, email, PURPOSE_PASSWORD_RESET, payload.code)
    except VerificationError as e:
        raise bad_request_exception(str(e))

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        # Only reachable if the account was deleted between request and reset.
        raise bad_request_exception("That code is not valid. Request a new one.")

    user.hashed_password = get_password_hash(payload.new_password)
    # Whoever prompted this reset may already hold a token for the account —
    # that is the usual reason someone resets a password they still know. Bump
    # the version so every outstanding session dies with the old password.
    user.token_version = (user.token_version or 0) + 1
    # Someone who forgot their password has very likely just failed to sign in
    # five times, which is exactly what the lockout counts. Without this they
    # complete the reset, are handed a session, and are then refused at the
    # login form for another fifteen minutes — with a password they know is
    # correct. Proving control of the address is a stronger signal than the
    # failures that preceded it.
    login_throttle.clear(email)
    # Resetting through the emailed code proves the address, so an account that
    # never finished sign-up verification is verified now.
    if not user.is_verified:
        user.is_verified = True
        user.email_verified_at = datetime.utcnow()
    user.last_login_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)

    logger.info(f"Password reset completed for {email}")
    return _login_response_for(user)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user account.

    Creates a new user and their personal organization. The email must first be
    confirmed through `/auth/email/verify-code`, whose token is passed here.
    """
    email = normalize_email(user_data.email)

    # Check if user already exists
    result = await db.execute(select(User).where(User.email == email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise bad_request_exception("Email already registered")

    email_verified = bool(
        user_data.email_verification_token
        and verify_email_verification_token(user_data.email_verification_token, email)
    )

    if settings.REQUIRE_EMAIL_VERIFICATION and not email_verified:
        raise bad_request_exception(
            "Please verify your email address before creating your account."
        )

    # Create user
    user = User(
        email=email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        company_name=user_data.company_name,
        phone_number=user_data.phone_number,
        is_verified=email_verified,
        email_verified_at=datetime.utcnow() if email_verified else None,
    )

    db.add(user)
    await db.flush()  # Flush to get user.id

    # Create personal organization. The slug column is UNIQUE and the local
    # part of an address is not, so this has to be resolved against the table
    # rather than assumed free — two alices at different domains previously
    # collided here and the IntegrityError surfaced as a 500.
    org_slug = await unique_org_slug(db, email)
    organization = Organization(
        name=user_data.company_name or f"{user_data.full_name}'s Workspace",
        slug=org_slug,
        owner_id=user.id,
    )

    db.add(organization)
    await db.flush()

    # Add user as organization owner
    membership = OrganizationMember(
        organization_id=organization.id,
        user_id=user.id,
        role="owner",
    )

    db.add(membership)
    await db.commit()
    await db.refresh(user)

    return RegisterResponse(
        message="Account created successfully."
        if email_verified
        else "Account created. Please verify your email.",
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "is_verified": user.is_verified,
        }
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email and password.

    Returns access and refresh tokens.
    """
    # Registration stores the normalized address, so login has to normalize
    # too. Comparing the raw input meant anyone who typed a capital letter —
    # or whose keyboard autocapitalised the first one — got 401 on the very
    # address they had just signed up with.
    email = normalize_email(credentials.email)

    # Checked before the account is even looked up: a locked address must cost
    # a guesser nothing to discover, and must not cost us a bcrypt comparison.
    locked_for = login_throttle.seconds_until_unlocked(email)
    if locked_for:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-in attempts. Please try again shortly.",
            headers={"Retry-After": str(locked_for)},
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Counted even for an address with no account, so the lockout cannot be
        # used to tell registered addresses from unregistered ones.
        login_throttle.record_failure(email)
        raise credentials_exception()

    # Social-only accounts (Google/Apple) have no local password.
    if not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This account uses {user.auth_provider.title()} sign-in. "
                   f"Please continue with {user.auth_provider.title()}.",
        )

    # Verify password
    if not verify_password(credentials.password, user.hashed_password):
        login_throttle.record_failure(email)
        raise credentials_exception()

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # A correct password clears the record, so someone who mistypes twice and
    # then succeeds is never locked out by their own typos.
    login_throttle.clear(email)

    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.commit()

    # Create tokens
    access_token = create_access_token(
        subject=str(user.id), token_version=user.token_version
    )
    refresh_token = create_refresh_token(
        subject=str(user.id), token_version=user.token_version
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "is_verified": user.is_verified,
        }
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    token_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    """
    payload = decode_token(token_data.refresh_token)

    if payload is None:
        raise credentials_exception()

    user_id = payload.get("sub")
    token_type = payload.get("type")

    if user_id is None or token_type != "refresh":
        raise credentials_exception()

    # Verify user still exists and is active. A malformed `sub` means the
    # token is not one we issued, which is a 401 — letting ValueError escape
    # turned it into a 500.
    try:
        subject_id = _uuid.UUID(user_id)
    except (ValueError, AttributeError, TypeError):
        raise credentials_exception()

    result = await db.execute(select(User).where(User.id == subject_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise credentials_exception()

    # A refresh token outlives an access token many times over, so this is the
    # check that actually makes "sign out everywhere" and "reset my password"
    # mean something: without it a stolen refresh token keeps minting fresh
    # access tokens for its full 30 days regardless of what the owner does.
    if not token_version_matches(payload, user):
        raise credentials_exception()

    # Create new tokens
    access_token = create_access_token(
        subject=str(user.id), token_version=user.token_version
    )
    new_refresh_token = create_refresh_token(
        subject=str(user.id), token_version=user.token_version
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "is_verified": user.is_verified,
        }
    )


@router.post("/google", response_model=LoginResponse)
async def google_auth(
    payload: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Sign in / sign up with Google.

    Accepts an authorization code (popup auth-code flow), verifies it with
    Google, then finds-or-creates the matching user and returns our own tokens.
    """
    oauth = get_oauth_service()
    try:
        profile = await oauth.verify_google_code(payload.code, redirect_uri=payload.redirect_uri)
        user, is_new = await oauth.resolve_user(db, profile)
    except OAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    return _login_response_for(user, is_new=is_new)


@router.post("/apple", response_model=LoginResponse)
async def apple_auth(
    payload: AppleAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Sign in / sign up with Apple.

    Verifies the identity token from Sign in with Apple, then finds-or-creates
    the matching user and returns our own tokens.
    """
    oauth = get_oauth_service()
    try:
        profile = await oauth.verify_apple(
            payload.id_token, full_name=payload.full_name, nonce=payload.nonce
        )
        user, is_new = await oauth.resolve_user(db, profile)
    except OAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    return _login_response_for(user, is_new=is_new)


@router.get("/providers")
async def oauth_providers():
    """Report which social login providers are configured (for the frontend UI)."""
    return {
        "google": settings.google_oauth_enabled,
        "apple": settings.apple_oauth_enabled,
    }


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sign out of **every** session for this account.

    This used to return a message and do nothing at all, on the reasoning that
    a JWT is stateless so logout belongs to the client. That reasoning holds
    only while the client is the one you trust — it is exactly wrong for the
    case logout exists to cover, which is a token somewhere you no longer
    control: a shared machine, a stolen laptop, a session you don't recognise.
    Clearing localStorage in *this* browser does nothing about any of those.

    Incrementing ``token_version`` invalidates every token issued for this
    account, this one included, so the client must sign in again afterwards.

    That is a deliberate choice of "sign out everywhere" over per-device
    logout. Per-device would need server-side session records; this is one
    integer, and for an account-compromise response it is the behaviour you
    want anyway.
    """
    current_user.token_version = (current_user.token_version or 0) + 1
    await db.commit()

    logger.info(f"All sessions revoked for user {current_user.id}")
    return {"message": "Signed out of all sessions"}
