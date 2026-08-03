"""
Integration tests for email verification at sign-up and password reset.

Drives the real routes end to end with only the mail transport stubbed, so the
code generation, HMAC storage, expiry, attempt limits and rate limiting are all
the real implementation.

Follows the async-client pattern in ``test_phone_numbers_api.py``: an in-process
httpx client sharing the test event loop, with per-request DB sessions.
"""
import uuid
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.database import get_db
from app.main import app
from app.models.user import User
from app.models.verification import PURPOSE_EMAIL_VERIFICATION, VerificationCode
from app.services.auth import verification as verification_service
from app.services.email.service import email_service

#: Every code the app tried to email, newest last.
SENT: list = []


@pytest.fixture(autouse=True)
def mail(monkeypatch):
    """
    Capture outgoing codes instead of sending them.

    The code only exists in the email, so the test reads it here — exactly the
    information a real user gets, and nothing more.
    """
    SENT.clear()

    async def fake_send(*, to_email, code, expires_minutes, purpose="signup", **kwargs):
        SENT.append({"to": to_email, "code": code, "purpose": purpose})
        return True

    monkeypatch.setattr(email_service, "send_verification_code", fake_send)
    # Pin verification on and debug off: the suite must not depend on local .env.
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    monkeypatch.setattr(settings, "DEBUG", False)
    return SENT


def last_code() -> str:
    assert SENT, "no code was emailed"
    return SENT[-1]["code"]


@pytest_asyncio.fixture
async def client(db_engine):
    """In-loop async HTTP client with per-request DB sessions."""
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def an_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


async def _signup_payload(client, email: str, password: str = "password123"):
    """Run the verification step and return a ready-to-post register body."""
    sent = await client.post(
        "/api/v1/auth/email/send-code", json={"email": email, "purpose": "signup"}
    )
    assert sent.status_code == 200, sent.text

    verified = await client.post(
        "/api/v1/auth/email/verify-code", json={"email": email, "code": last_code()}
    )
    assert verified.status_code == 200, verified.text

    return {
        "email": email,
        "password": password,
        "full_name": "Test User",
        "email_verification_token": verified.json()["email_verification_token"],
    }


# ---------- sign-up verification ----------


@pytest.mark.integration
@pytest.mark.asyncio
class TestSignupVerification:
    async def test_code_is_emailed_and_never_returned_by_the_api(self, client):
        """The response must not leak the code — only the inbox has it."""
        email = an_email()
        res = await client.post(
            "/api/v1/auth/email/send-code", json={"email": email, "purpose": "signup"}
        )

        assert res.status_code == 200, res.text
        body = res.json()
        assert body["debug_code"] is None
        assert body["expires_in_minutes"] == verification_service.CODE_TTL_MINUTES

        assert SENT[-1]["to"] == email
        assert SENT[-1]["purpose"] == "signup"
        assert len(SENT[-1]["code"]) == verification_service.CODE_LENGTH

    async def test_only_the_hmac_is_stored(self, client, db_session):
        """A database leak must not hand out working codes."""
        email = an_email()
        await client.post(
            "/api/v1/auth/email/send-code", json={"email": email, "purpose": "signup"}
        )

        row = (
            await db_session.execute(
                select(VerificationCode).where(VerificationCode.email == email)
            )
        ).scalar_one()

        assert row.purpose == PURPOSE_EMAIL_VERIFICATION
        assert row.code_hash != last_code()
        assert len(row.code_hash) == 64

    async def test_verified_email_can_register_and_is_marked_verified(
        self, client, db_session
    ):
        email = an_email()
        payload = await _signup_payload(client, email)

        res = await client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 201, res.text
        assert res.json()["user"]["is_verified"] is True

        user = (
            await db_session.execute(select(User).where(User.email == email))
        ).scalar_one()
        assert user.is_verified is True
        assert user.email_verified_at is not None

    async def test_registering_without_verifying_is_refused(self, client, db_session):
        """The whole point: no account for an address you have not proved."""
        email = an_email()

        res = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "password123", "full_name": "Sneaky"},
        )

        assert res.status_code == 400
        assert "verify your email" in res.json()["detail"].lower()

        user = (
            await db_session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        assert user is None

    async def test_token_for_one_address_cannot_register_another(self, client):
        """The token is bound to the address it was issued for."""
        payload = await _signup_payload(client, an_email())
        payload["email"] = an_email()

        res = await client.post("/api/v1/auth/register", json=payload)

        assert res.status_code == 400
        assert "verify your email" in res.json()["detail"].lower()

    async def test_wrong_code_is_refused_and_counts_against_the_attempt_limit(
        self, client, db_session
    ):
        email = an_email()
        await client.post(
            "/api/v1/auth/email/send-code", json={"email": email, "purpose": "signup"}
        )

        res = await client.post(
            "/api/v1/auth/email/verify-code", json={"email": email, "code": "000000"}
        )
        assert res.status_code == 400

        row = (
            await db_session.execute(
                select(VerificationCode).where(VerificationCode.email == email)
            )
        ).scalar_one()
        assert row.attempts == 1
        assert row.consumed_at is None

    async def test_code_dies_after_too_many_wrong_guesses(self, client):
        """A 6-digit code is only safe because guessing is capped."""
        email = an_email()
        await client.post(
            "/api/v1/auth/email/send-code", json={"email": email, "purpose": "signup"}
        )
        real_code = last_code()

        wrong = "111111" if real_code != "111111" else "222222"
        for _ in range(verification_service.MAX_ATTEMPTS):
            await client.post(
                "/api/v1/auth/email/verify-code", json={"email": email, "code": wrong}
            )

        # Even the correct code is dead now.
        res = await client.post(
            "/api/v1/auth/email/verify-code", json={"email": email, "code": real_code}
        )
        assert res.status_code == 400

    async def test_expired_code_is_refused(self, client, db_session):
        email = an_email()
        await client.post(
            "/api/v1/auth/email/send-code", json={"email": email, "purpose": "signup"}
        )

        row = (
            await db_session.execute(
                select(VerificationCode).where(VerificationCode.email == email)
            )
        ).scalar_one()
        row.expires_at = datetime.utcnow() - timedelta(seconds=1)
        await db_session.commit()

        res = await client.post(
            "/api/v1/auth/email/verify-code", json={"email": email, "code": last_code()}
        )
        assert res.status_code == 400
        assert "expired" in res.json()["detail"].lower()

    async def test_a_code_is_single_use(self, client):
        email = an_email()
        await client.post(
            "/api/v1/auth/email/send-code", json={"email": email, "purpose": "signup"}
        )
        code = last_code()

        first = await client.post(
            "/api/v1/auth/email/verify-code", json={"email": email, "code": code}
        )
        assert first.status_code == 200

        second = await client.post(
            "/api/v1/auth/email/verify-code", json={"email": email, "code": code}
        )
        assert second.status_code == 400

    async def test_resending_inside_the_cooldown_is_rate_limited(self, client):
        """Otherwise 'Resend' is a button for flooding someone's inbox."""
        email = an_email()
        await client.post(
            "/api/v1/auth/email/send-code", json={"email": email, "purpose": "signup"}
        )

        res = await client.post(
            "/api/v1/auth/email/send-code", json={"email": email, "purpose": "signup"}
        )

        assert res.status_code == 429
        assert res.headers.get("Retry-After")
        assert len(SENT) == 1

    async def test_code_is_not_sent_to_an_address_that_already_has_an_account(
        self, client
    ):
        email = an_email()
        payload = await _signup_payload(client, email)
        assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
        SENT.clear()

        res = await client.post(
            "/api/v1/auth/email/send-code", json={"email": email, "purpose": "signup"}
        )

        assert res.status_code == 400
        assert "already registered" in res.json()["detail"].lower()
        assert SENT == []

    async def test_address_casing_does_not_create_a_second_account(self, client):
        """Verifying Foo@x.com and registering foo@x.com is one address."""
        email = an_email()
        payload = await _signup_payload(client, email.upper())
        payload["email"] = email

        res = await client.post("/api/v1/auth/register", json=payload)

        assert res.status_code == 201, res.text
        assert res.json()["user"]["email"] == email


# ---------- forgotten password ----------


@pytest.mark.integration
@pytest.mark.asyncio
class TestPasswordReset:
    async def _registered_user(self, client, password="password123") -> str:
        email = an_email()
        payload = await _signup_payload(client, email, password)
        assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
        SENT.clear()
        return email

    async def test_unknown_address_looks_identical_to_a_known_one(self, client):
        """The response must not tell an attacker which emails are registered."""
        known = await self._registered_user(client)
        unknown = an_email()

        known_res = await client.post("/api/v1/auth/password/forgot", json={"email": known})
        SENT.clear()
        unknown_res = await client.post(
            "/api/v1/auth/password/forgot", json={"email": unknown}
        )

        assert known_res.status_code == unknown_res.status_code == 200
        assert known_res.json()["message"] == unknown_res.json()["message"]
        # ...but no email is actually sent to the address with no account.
        assert SENT == []

    async def test_reset_sets_the_new_password_and_signs_the_user_in(
        self, client, db_session
    ):
        email = await self._registered_user(client, "old-password-1")

        await client.post("/api/v1/auth/password/forgot", json={"email": email})
        assert SENT[-1]["purpose"] == "password_reset"

        res = await client.post(
            "/api/v1/auth/password/reset",
            json={"email": email, "code": last_code(), "new_password": "new-password-2"},
        )

        assert res.status_code == 200, res.text
        body = res.json()
        assert body["access_token"] and body["refresh_token"]
        assert body["user"]["email"] == email

        user = (
            await db_session.execute(select(User).where(User.email == email))
        ).scalar_one()
        await db_session.refresh(user)
        assert verify_password("new-password-2", user.hashed_password)

    async def test_the_old_password_stops_working(self, client):
        email = await self._registered_user(client, "old-password-1")
        await client.post("/api/v1/auth/password/forgot", json={"email": email})
        await client.post(
            "/api/v1/auth/password/reset",
            json={"email": email, "code": last_code(), "new_password": "new-password-2"},
        )

        old = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "old-password-1"}
        )
        new = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "new-password-2"}
        )

        assert old.status_code == 401
        assert new.status_code == 200

    async def test_wrong_code_leaves_the_password_alone(self, client):
        email = await self._registered_user(client, "old-password-1")
        await client.post("/api/v1/auth/password/forgot", json={"email": email})

        res = await client.post(
            "/api/v1/auth/password/reset",
            json={"email": email, "code": "000000", "new_password": "attacker-pass"},
        )
        assert res.status_code == 400

        still_works = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "old-password-1"}
        )
        assert still_works.status_code == 200

    async def test_a_signup_code_cannot_reset_a_password(self, client, db_session):
        """
        Codes are bound to their flow, so one mailed for "confirm your address"
        is not also a password-reset token.
        """
        email = an_email()
        db_session.add(
            User(
                email=email,
                hashed_password=get_password_hash("old-password-1"),
                full_name="Existing",
                is_active=True,
                is_verified=True,
            )
        )
        await db_session.commit()

        # A live sign-up code for the same address.
        code, _ = await verification_service.issue_code(
            db_session, email, PURPOSE_EMAIL_VERIFICATION
        )

        res = await client.post(
            "/api/v1/auth/password/reset",
            json={"email": email, "code": code, "new_password": "new-password-2"},
        )

        assert res.status_code == 400
        assert (
            await client.post(
                "/api/v1/auth/login", json={"email": email, "password": "old-password-1"}
            )
        ).status_code == 200

    async def test_reset_code_is_single_use(self, client):
        email = await self._registered_user(client, "old-password-1")
        await client.post("/api/v1/auth/password/forgot", json={"email": email})
        code = last_code()

        first = await client.post(
            "/api/v1/auth/password/reset",
            json={"email": email, "code": code, "new_password": "new-password-2"},
        )
        assert first.status_code == 200

        replay = await client.post(
            "/api/v1/auth/password/reset",
            json={"email": email, "code": code, "new_password": "third-password-3"},
        )
        assert replay.status_code == 400

    async def test_reset_verifies_an_account_that_never_confirmed_its_email(
        self, client, db_session
    ):
        """Receiving the code proves the address just as well as sign-up did."""
        email = an_email()
        db_session.add(
            User(
                email=email,
                hashed_password="$2b$12$" + "x" * 53,  # unusable; reset replaces it
                full_name="Legacy",
                is_active=True,
                is_verified=False,
            )
        )
        await db_session.commit()

        await client.post("/api/v1/auth/password/forgot", json={"email": email})
        res = await client.post(
            "/api/v1/auth/password/reset",
            json={"email": email, "code": last_code(), "new_password": "new-password-2"},
        )
        assert res.status_code == 200, res.text

        user = (
            await db_session.execute(select(User).where(User.email == email))
        ).scalar_one()
        await db_session.refresh(user)
        assert user.is_verified is True
        assert user.email_verified_at is not None
