"""
Pydantic schemas for User models.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# Base schemas
class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    phone_number: Optional[str] = None
    bio: Optional[str] = None
    timezone: str = "UTC"
    language: str = "en"


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    phone_number: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None


class PasswordChange(BaseModel):
    """Schema for changing the current user's password."""
    # Optional so social-login users (no existing password) can set one.
    current_password: Optional[str] = None
    new_password: str = Field(..., min_length=8, description="New password (min 8 chars)")


class UserInDB(UserBase):
    """User schema as stored in database."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    avatar_url: Optional[str] = None
    is_active: bool
    is_verified: bool
    email_verified_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class UserResponse(UserInDB):
    """User schema for API responses."""
    pass


# Organization schemas
class OrganizationBase(BaseModel):
    """Base organization schema."""
    name: str
    slug: str
    plan_type: str = "starter"
    billing_email: Optional[str] = None


class OrganizationCreate(BaseModel):
    """Schema for creating an organization."""
    name: str
    slug: str


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""
    name: Optional[str] = None
    billing_email: Optional[str] = None
    settings: Optional[dict] = None


class OrganizationInDB(OrganizationBase):
    """Organization schema as stored in database."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    is_active: bool
    settings: dict
    created_at: datetime
    updated_at: datetime


class OrganizationResponse(OrganizationInDB):
    """Organization schema for API responses."""
    pass


# Organization Member schemas
class OrganizationMemberBase(BaseModel):
    """Base organization member schema."""
    role: str = "member"
    permissions: dict = {}


class OrganizationMemberCreate(BaseModel):
    """Schema for adding a member to organization."""
    user_id: UUID
    role: str = "member"
    permissions: dict = {}


class OrganizationMemberUpdate(BaseModel):
    """Schema for updating member role/permissions."""
    role: Optional[str] = None
    permissions: Optional[dict] = None


class OrganizationMemberInDB(OrganizationMemberBase):
    """Organization member schema as stored in database."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    user_id: UUID
    invited_by: Optional[UUID] = None
    joined_at: datetime
    created_at: datetime


class OrganizationMemberResponse(OrganizationMemberInDB):
    """Organization member schema for API responses."""
    user: Optional[UserResponse] = None


# API Key schemas
class ApiKeyBase(BaseModel):
    """Base API key schema."""
    name: str
    scopes: list[str] = []


class ApiKeyCreate(ApiKeyBase):
    """Schema for creating an API key."""
    expires_at: Optional[datetime] = None


class ApiKeyUpdate(BaseModel):
    """Schema for updating an API key."""
    name: Optional[str] = None
    is_active: Optional[bool] = None
    scopes: Optional[list[str]] = None


class ApiKeyInDB(ApiKeyBase):
    """API key schema as stored in database."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    organization_id: UUID
    key_prefix: str
    is_active: bool
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ApiKeyResponse(ApiKeyInDB):
    """API key schema for API responses."""
    pass


class ApiKeyCreateResponse(ApiKeyResponse):
    """API key schema with full key (only returned on creation)."""
    key: str  # Full API key, only shown once
