"""
Pydantic schemas for authentication.
"""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data extracted from JWT token."""
    user_id: Optional[str] = None
    scopes: list[str] = []


class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RegisterRequest(BaseModel):
    """Registration request schema."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    phone_number: Optional[str] = None


class RegisterResponse(BaseModel):
    """Registration response schema."""
    message: str
    user: dict


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""
    refresh_token: str


class GoogleAuthRequest(BaseModel):
    """Google sign-in request (authorization-code flow)."""
    code: str = Field(..., description="Authorization code from Google (popup auth-code flow)")
    redirect_uri: str = Field(default="postmessage", description="Redirect URI used by the client")


class AppleAuthRequest(BaseModel):
    """Apple sign-in request (Sign in with Apple JS)."""
    id_token: str = Field(..., description="Identity token returned by AppleID.auth.signIn")
    full_name: Optional[str] = Field(default=None, description="Name (only sent by Apple on first sign-in)")
    nonce: Optional[str] = Field(default=None, description="Nonce to match against the token, if used")


class PasswordResetRequest(BaseModel):
    """Password reset request schema."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema."""
    token: str
    new_password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""
    current_password: str
    new_password: str = Field(..., min_length=8)


class EmailVerificationRequest(BaseModel):
    """Email verification request schema."""
    token: str
