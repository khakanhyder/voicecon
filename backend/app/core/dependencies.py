"""
FastAPI dependencies for authentication, authorization, and common operations.
"""
from typing import Optional, Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.database import get_db
from app.core.config import settings
from app.core.security import decode_token
from app.core.exceptions import credentials_exception

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
    # Import here to avoid circular imports
    from app.models.user import User

    result = await db.execute(select(User).where(User.id == user_id))
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


async def get_current_user_organization(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's organization.

    Returns:
        Organization model instance

    Raises:
        HTTPException: If user has no organization
    """
    from app.models.user import Organization, OrganizationMember
    from sqlalchemy.orm import selectinload

    # Get user's organization membership
    result = await db.execute(
        select(OrganizationMember)
        .options(selectinload(OrganizationMember.organization))
        .where(OrganizationMember.user_id == current_user.id)
        .limit(1)
    )
    membership = result.scalar_one_or_none()

    if membership is None or membership.organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User has no organization"
        )

    return membership.organization


def require_role(required_role: str):
    """
    Dependency factory to require a specific organization role.

    Usage:
        @app.get("/admin")
        async def admin_endpoint(
            current_user = Depends(require_role("admin"))
        ):
            ...
    """
    async def role_checker(
        current_user = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        from app.models.user import OrganizationMember

        # Check user's role in organization
        result = await db.execute(
            select(OrganizationMember)
            .where(OrganizationMember.user_id == current_user.id)
            .limit(1)
        )
        membership = result.scalar_one_or_none()

        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no organization membership"
            )

        # Define role hierarchy
        role_hierarchy = {
            "viewer": 0,
            "member": 1,
            "admin": 2,
            "owner": 3
        }

        user_role_level = role_hierarchy.get(membership.role, 0)
        required_role_level = role_hierarchy.get(required_role, 0)

        if user_role_level < required_role_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role} role or higher"
            )

        return current_user

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
