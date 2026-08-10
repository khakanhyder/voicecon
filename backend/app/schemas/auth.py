"""
Pydantic schemas for authentication.
"""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, model_validator

from app.core.passwords import PasswordPolicyError, validate_password
from app.schemas._types import NonBlankName, PersonName, PhoneNumberStr


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
    """
    Registration request schema.

    `full_name` is required. It used to be optional, and the sign-up form did
    not mark it required either, so an account could be created with no name at
    all — which then rendered as a blank entry in the account menu, the team
    list and every invitation that account sent.
    """
    email: EmailStr
    password: str
    full_name: PersonName
    company_name: Optional[NonBlankName] = None
    phone_number: Optional[PhoneNumberStr] = None
    email_verification_token: Optional[str] = Field(
        default=None,
        description=(
            "Token returned by /auth/email/verify-code, proving the address was "
            "confirmed. Required unless the server has email verification off."
        ),
    )


    @model_validator(mode="after")
    def _check_password(self):
        """
        Apply the password policy.

        Run as a model validator rather than a field one so it can see the
        address and the name — a password that is simply the user's own email
        local part is refused, and a field validator could not know that.
        """
        try:
            validate_password(
                self.password, email=str(self.email), full_name=self.full_name
            )
        except PasswordPolicyError as e:
            raise ValueError(str(e)) from e
        return self


class SendEmailCodeRequest(BaseModel):
    """Ask for a one-time code to be emailed to an address."""

    email: EmailStr
    purpose: str = Field(
        default="signup",
        description="'signup' to verify a new address, 'password_reset' to reset a password",
    )


class SendEmailCodeResponse(BaseModel):
    """Outcome of a code request."""

    message: str
    expires_in_minutes: int
    #: Only populated in debug mode with no mail transport configured, so local
    #: development does not require reading the server log.
    debug_code: Optional[str] = None


class VerifyEmailCodeRequest(BaseModel):
    """Submit the code that was emailed."""

    email: EmailStr
    code: str = Field(..., min_length=4, max_length=12)


class VerifyEmailCodeResponse(BaseModel):
    """Proof that an address was verified, to be passed to /auth/register."""

    verified: bool
    email: EmailStr
    email_verification_token: str
    expires_in_minutes: int


class ForgotPasswordRequest(BaseModel):
    """Start a password reset."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Finish a password reset with the emailed code."""

    email: EmailStr
    code: str = Field(..., min_length=4, max_length=12)
    new_password: str

    @model_validator(mode="after")
    def _check_password(self):
        """The reset form must not be a way round the sign-up policy."""
        try:
            validate_password(self.new_password, email=str(self.email))
        except PasswordPolicyError as e:
            raise ValueError(str(e)) from e
        return self


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
    new_password: str

    @model_validator(mode="after")
    def _check_password(self):
        try:
            validate_password(self.new_password)
        except PasswordPolicyError as e:
            raise ValueError(str(e)) from e
        return self


class EmailVerificationRequest(BaseModel):
    """Email verification request schema."""
    token: str
