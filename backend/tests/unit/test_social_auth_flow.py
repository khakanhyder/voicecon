"""
Social sign-in (Google / Apple) end-to-end behaviour of the *decision* the
frontend routes on.

Both providers converge on `OAuthService.resolve_user`, whose `is_new` flag is
what tells the client "send this person through onboarding". These tests pin
that flag, the find-or-create ordering behind it, and the fact that the two
providers behave identically — the Apple flow is not allowed to drift from the
Google one.

Token verification itself (Google's token exchange, Apple's JWKS) is patched
out: it talks to the providers over the network and is not what decides the
redirect. Everything below the verification boundary is the real service
against the real database.
"""
import uuid

import pytest
from sqlalchemy import func, select

from app.models.user import Organization, OrganizationMember, User
from app.services.auth.oauth_service import OAuthError, OAuthProfile, OAuthService


def profile(
    provider: str,
    *,
    subject: str = "sub-1",
    email: str = "social@example.com",
    email_verified: bool = True,
    full_name: str | None = "Social User",
    avatar_url: str | None = None,
) -> OAuthProfile:
    return OAuthProfile(
        provider=provider,
        subject=subject,
        email=email,
        email_verified=email_verified,
        full_name=full_name,
        avatar_url=avatar_url,
    )


async def user_count(db) -> int:
    return (await db.execute(select(func.count()).select_from(User))).scalar_one()


@pytest.mark.unit
@pytest.mark.auth
@pytest.mark.parametrize("provider", ["google", "apple"])
class TestResolveUser:
    """The same expectations for both providers — run twice, once each."""

    async def test_first_sign_in_creates_account_and_org(self, db_session, provider):
        svc = OAuthService()

        user, is_new = await svc.resolve_user(db_session, profile(provider))

        assert is_new is True, "a first-time social sign-in must route to onboarding"
        assert user.email == "social@example.com"
        assert user.auth_provider == provider
        assert (user.google_id if provider == "google" else user.apple_id) == "sub-1"

        org = (
            await db_session.execute(
                select(Organization).where(Organization.owner_id == user.id)
            )
        ).scalar_one()
        member = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == org.id
                )
            )
        ).scalar_one()
        assert member.role == "owner"

    async def test_second_sign_in_reuses_the_account(self, db_session, provider):
        svc = OAuthService()
        first, _ = await svc.resolve_user(db_session, profile(provider))

        second, is_new = await svc.resolve_user(db_session, profile(provider))

        assert is_new is False, "a returning user must go straight to the dashboard"
        assert second.id == first.id
        assert await user_count(db_session) == 1

    async def test_second_sign_in_matches_on_subject_not_email(
        self, db_session, provider
    ):
        """Apple's Hide-My-Email relay address can change; the `sub` cannot."""
        svc = OAuthService()
        first, _ = await svc.resolve_user(db_session, profile(provider))

        second, is_new = await svc.resolve_user(
            db_session, profile(provider, email="rotated@privaterelay.example")
        )

        assert is_new is False
        assert second.id == first.id

    async def test_links_to_existing_account_on_verified_email(
        self, db_session, provider
    ):
        """Signing in socially to an account made with a password is not new."""
        existing = User(
            email="social@example.com",
            hashed_password="x",
            full_name="Existing User",
            is_active=True,
        )
        db_session.add(existing)
        await db_session.commit()

        svc = OAuthService()
        user, is_new = await svc.resolve_user(db_session, profile(provider))

        assert is_new is False, "linking an existing account must not re-run onboarding"
        assert user.id == existing.id
        assert (user.google_id if provider == "google" else user.apple_id) == "sub-1"
        assert await user_count(db_session) == 1

    async def test_unverified_email_never_takes_over_an_account(
        self, db_session, provider
    ):
        """
        An unverified address may not link — and may not quietly become a
        second account on the same email either, which the unique index turns
        into a 500. It is refused with a message the sign-in page can show.
        """
        existing = User(
            email="social@example.com",
            hashed_password="x",
            full_name="Existing User",
            is_active=True,
        )
        db_session.add(existing)
        await db_session.commit()

        svc = OAuthService()
        with pytest.raises(OAuthError):
            await svc.resolve_user(db_session, profile(provider, email_verified=False))

        await db_session.refresh(existing)
        assert existing.google_id is None and existing.apple_id is None
        assert await user_count(db_session) == 1

    async def test_deactivated_account_is_refused(self, db_session, provider):
        svc = OAuthService()
        user, _ = await svc.resolve_user(db_session, profile(provider))
        user.is_active = False
        await db_session.commit()

        with pytest.raises(OAuthError):
            await svc.resolve_user(db_session, profile(provider))

    async def test_missing_name_on_later_sign_in_keeps_the_stored_one(
        self, db_session, provider
    ):
        """Apple only sends the display name on the very first authorization."""
        svc = OAuthService()
        await svc.resolve_user(db_session, profile(provider))

        user, _ = await svc.resolve_user(db_session, profile(provider, full_name=None))

        assert user.full_name == "Social User"


@pytest.mark.unit
@pytest.mark.auth
class TestSocialAuthEndpoints:
    """
    The HTTP surface the buttons hit: both endpoints must hand back a session
    plus the `is_new` flag the client routes on.
    """

    async def _patch_verification(self, monkeypatch, prof: OAuthProfile):
        from app.api.v1.endpoints import auth as auth_endpoints

        svc = OAuthService()

        async def fake_google(code, redirect_uri="postmessage"):
            return prof

        async def fake_apple(id_token_str, full_name=None, nonce=None):
            return prof

        monkeypatch.setattr(svc, "verify_google_code", fake_google)
        monkeypatch.setattr(svc, "verify_apple", fake_apple)
        monkeypatch.setattr(auth_endpoints, "get_oauth_service", lambda: svc)

    async def test_google_endpoint_reports_new_then_returning(
        self, async_client, monkeypatch, db_session
    ):
        await self._patch_verification(monkeypatch, profile("google"))

        first = await async_client.post(
            "/api/v1/auth/google", json={"code": "irrelevant"}
        )
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["access_token"] and body["refresh_token"]
        assert body["user"]["is_new"] is True

        second = await async_client.post(
            "/api/v1/auth/google", json={"code": "irrelevant"}
        )
        assert second.json()["user"]["is_new"] is False

    async def test_apple_endpoint_reports_new_then_returning(
        self, async_client, monkeypatch, db_session
    ):
        await self._patch_verification(monkeypatch, profile("apple"))

        first = await async_client.post(
            "/api/v1/auth/apple",
            json={"id_token": "irrelevant", "full_name": "Social User"},
        )
        assert first.status_code == 200, first.text
        assert first.json()["user"]["is_new"] is True

        second = await async_client.post(
            "/api/v1/auth/apple", json={"id_token": "irrelevant"}
        )
        assert second.json()["user"]["is_new"] is False


@pytest.mark.unit
@pytest.mark.auth
class TestEmailCollision:
    """
    A provider that reports the email as unverified cannot link to the existing
    account — and must not fall through to creating a second user with the same
    address, which the unique index rejects with a 500.
    """

    async def test_endpoint_returns_a_clear_error_not_a_crash(
        self, async_client, monkeypatch, db_session
    ):
        from app.api.v1.endpoints import auth as auth_endpoints

        db_session.add(
            User(email="social@example.com", hashed_password="x", is_active=True)
        )
        await db_session.commit()

        svc = OAuthService()

        async def fake_apple(id_token_str, full_name=None, nonce=None):
            return profile("apple", email_verified=False)

        monkeypatch.setattr(svc, "verify_apple", fake_apple)
        monkeypatch.setattr(auth_endpoints, "get_oauth_service", lambda: svc)

        resp = await async_client.post(
            "/api/v1/auth/apple", json={"id_token": "irrelevant"}
        )

        assert resp.status_code == 401, resp.text
        assert "already" in resp.json()["detail"].lower()
