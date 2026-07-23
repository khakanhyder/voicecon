"""
Social login (OAuth) service.

Verifies Google and Apple sign-in assertions and maps them to a local User,
creating the account (and a personal organization) on first sign-in, or linking
to an existing account by verified email.

Design notes / security:
- Google uses the authorization-code flow (popup, redirect_uri="postmessage").
  We exchange the short-lived code server-side using the client secret, then
  cryptographically verify the returned ID token's signature, audience (our
  client id) and issuer via google-auth.
- Apple sends an ID token from the JS popup. We verify its signature against
  Apple's published JWKS, plus audience (our Services ID) and issuer.
- Accounts are linked by *verified* email only. We never trust an unverified
  email to take over an existing account.
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User, Organization, OrganizationMember

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"


class OAuthError(Exception):
    """Raised when a social sign-in assertion is invalid or cannot be processed."""


@dataclass
class OAuthProfile:
    """Normalized identity extracted from a verified provider assertion."""
    provider: str                 # "google" | "apple"
    subject: str                  # stable per-provider user id (the token `sub`)
    email: str
    email_verified: bool
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class OAuthService:
    """Verifies provider assertions and resolves them to local users."""

    # ------------------------------------------------------------------ #
    # Google
    # ------------------------------------------------------------------ #
    async def verify_google_code(self, code: str, redirect_uri: str = "postmessage") -> OAuthProfile:
        if not settings.google_oauth_enabled:
            raise OAuthError("Google sign-in is not configured on the server.")

        # 1) Exchange the authorization code for tokens.
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "code": code,
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
        except httpx.HTTPError as e:
            logger.error(f"Google token exchange transport error: {e}")
            raise OAuthError("Could not reach Google to verify your sign-in.")

        if resp.status_code != 200:
            logger.warning(f"Google token exchange failed ({resp.status_code}): {resp.text}")
            raise OAuthError("Google rejected the sign-in. Please try again.")

        id_token_str = resp.json().get("id_token")
        if not id_token_str:
            raise OAuthError("Google did not return an identity token.")

        # 2) Cryptographically verify the ID token (signature, aud, iss, exp).
        claims = await self._verify_google_id_token(id_token_str)

        if not claims.get("email"):
            raise OAuthError("Google account has no email address.")

        return OAuthProfile(
            provider="google",
            subject=str(claims["sub"]),
            email=claims["email"].lower(),
            email_verified=bool(claims.get("email_verified", False)),
            full_name=claims.get("name") or None,
            avatar_url=claims.get("picture") or None,
        )

    async def _verify_google_id_token(self, id_token_str: str) -> dict:
        # google-auth is synchronous and fetches Google's certs; run off the loop.
        def _verify() -> dict:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests

            return google_id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
                clock_skew_in_seconds=10,
            )

        try:
            claims = await asyncio.to_thread(_verify)
        except ValueError as e:
            logger.warning(f"Google ID token verification failed: {e}")
            raise OAuthError("Google sign-in could not be verified.")

        if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            raise OAuthError("Unexpected Google token issuer.")
        return claims

    # ------------------------------------------------------------------ #
    # Apple
    # ------------------------------------------------------------------ #
    async def verify_apple(
        self,
        id_token_str: str,
        full_name: Optional[str] = None,
        nonce: Optional[str] = None,
    ) -> OAuthProfile:
        if not settings.apple_oauth_enabled:
            raise OAuthError("Apple sign-in is not configured on the server.")

        claims = await self._verify_apple_id_token(id_token_str, nonce=nonce)

        email = claims.get("email")
        if not email:
            raise OAuthError("Apple account did not share an email address.")

        # Apple encodes email_verified as a bool or the string "true".
        raw_verified = claims.get("email_verified", False)
        email_verified = raw_verified is True or raw_verified == "true"

        return OAuthProfile(
            provider="apple",
            subject=str(claims["sub"]),
            email=str(email).lower(),
            email_verified=email_verified,
            full_name=full_name or None,
            avatar_url=None,
        )

    async def _verify_apple_id_token(self, id_token_str: str, nonce: Optional[str] = None) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                jwks = (await client.get(APPLE_JWKS_URL)).json()
        except httpx.HTTPError as e:
            logger.error(f"Could not fetch Apple JWKS: {e}")
            raise OAuthError("Could not reach Apple to verify your sign-in.")

        try:
            header = jwt.get_unverified_header(id_token_str)
        except Exception:
            raise OAuthError("Malformed Apple identity token.")

        key = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
        if key is None:
            raise OAuthError("Apple signing key not found.")

        try:
            claims = jwt.decode(
                id_token_str,
                key,
                algorithms=["RS256"],
                audience=settings.APPLE_CLIENT_ID,
                issuer=APPLE_ISSUER,
                options={"verify_at_hash": False},
            )
        except Exception as e:
            logger.warning(f"Apple ID token verification failed: {e}")
            raise OAuthError("Apple sign-in could not be verified.")

        if nonce is not None and claims.get("nonce") != nonce:
            raise OAuthError("Apple sign-in nonce mismatch.")
        return claims

    # ------------------------------------------------------------------ #
    # User resolution
    # ------------------------------------------------------------------ #
    async def resolve_user(self, db: AsyncSession, profile: OAuthProfile) -> tuple[User, bool]:
        """
        Find-or-create a local user for a verified OAuth profile.

        Order: (1) match by provider subject id, (2) link by verified email,
        (3) create a brand-new user + personal organization.

        Returns (user, is_new) — is_new is True only when a fresh account was
        created, so the caller can route first-time users into onboarding.
        """
        provider_col = User.google_id if profile.provider == "google" else User.apple_id

        # 1) Returning social user (matched by stable subject id).
        existing = (
            await db.execute(select(User).where(provider_col == profile.subject))
        ).scalar_one_or_none()
        if existing:
            return await self._touch_login(db, existing, profile), False

        # 2) Existing account with the same VERIFIED email → link this provider.
        if profile.email_verified:
            by_email = (
                await db.execute(select(User).where(User.email == profile.email))
            ).scalar_one_or_none()
            if by_email:
                self._set_provider_id(by_email, profile)
                if not by_email.avatar_url and profile.avatar_url:
                    by_email.avatar_url = profile.avatar_url
                if not by_email.full_name and profile.full_name:
                    by_email.full_name = profile.full_name
                return await self._touch_login(db, by_email, profile), False

        # 3) New user + personal organization.
        return await self._create_user(db, profile), True

    def _set_provider_id(self, user: User, profile: OAuthProfile) -> None:
        if profile.provider == "google":
            user.google_id = profile.subject
        else:
            user.apple_id = profile.subject

    async def _touch_login(self, db: AsyncSession, user: User, profile: OAuthProfile) -> User:
        if not user.is_active:
            raise OAuthError("This account has been deactivated.")
        # Ensure the provider link is set (covers the match-by-subject path too).
        self._set_provider_id(user, profile)
        user.last_login_at = datetime.utcnow()
        await db.commit()
        await db.refresh(user)
        return user

    async def _create_user(self, db: AsyncSession, profile: OAuthProfile) -> User:
        user = User(
            email=profile.email,
            hashed_password=None,
            full_name=profile.full_name,
            avatar_url=profile.avatar_url,
            auth_provider=profile.provider,
            is_verified=profile.email_verified,
            email_verified_at=datetime.utcnow() if profile.email_verified else None,
            last_login_at=datetime.utcnow(),
        )
        self._set_provider_id(user, profile)
        db.add(user)
        await db.flush()  # get user.id

        organization = Organization(
            name=(profile.full_name or profile.email.split("@")[0]) + "'s Workspace",
            slug=await self._unique_slug(db, profile.email),
            owner_id=user.id,
        )
        db.add(organization)
        await db.flush()

        db.add(OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role="owner",
        ))

        await db.commit()
        await db.refresh(user)
        logger.info(f"Created new {profile.provider} user {user.email} ({user.id})")
        return user

    async def _unique_slug(self, db: AsyncSession, email: str) -> str:
        base = email.split("@")[0].lower().replace(".", "-") or "workspace"
        slug = base
        for _ in range(5):
            exists = (
                await db.execute(select(Organization).where(Organization.slug == slug))
            ).scalar_one_or_none()
            if not exists:
                return slug
            slug = f"{base}-{uuid.uuid4().hex[:6]}"
        return f"{base}-{uuid.uuid4().hex[:10]}"


_oauth_service: Optional[OAuthService] = None


def get_oauth_service() -> OAuthService:
    """Get the global OAuth service (singleton)."""
    global _oauth_service
    if _oauth_service is None:
        _oauth_service = OAuthService()
    return _oauth_service
