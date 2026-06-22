"""
Authentication endpoints for user login, registration, and token management.
"""
from datetime import datetime
import uuid as _uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.exceptions import credentials_exception, bad_request_exception
from app.models.user import User, Organization, OrganizationMember
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    RefreshTokenRequest,
)
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user account.

    Creates a new user and their personal organization.
    """
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise bad_request_exception("Email already registered")

    # Create user
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        company_name=user_data.company_name,
    )

    db.add(user)
    await db.flush()  # Flush to get user.id

    # Create personal organization
    org_slug = user_data.email.split("@")[0].lower().replace(".", "-")
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
        message="User registered successfully. Please verify your email.",
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
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
    # Find user by email
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user:
        raise credentials_exception()

    # Verify password
    if not verify_password(credentials.password, user.hashed_password):
        raise credentials_exception()

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.commit()

    # Create tokens
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

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

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == _uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise credentials_exception()

    # Create new tokens
    access_token = create_access_token(subject=str(user.id))
    new_refresh_token = create_refresh_token(subject=str(user.id))

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


@router.post("/logout")
async def logout():
    """
    Logout user.

    Note: With JWT, logout is primarily handled client-side by removing tokens.
    This endpoint is provided for consistency and future enhancements (e.g., token blacklisting).
    """
    return {"message": "Successfully logged out"}
