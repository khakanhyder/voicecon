"""
Unit tests for API key authentication (`app.core.api_keys`).

This module owns *what makes a key valid*. The rules it enforces are all
revocation paths — a key must stop working the moment it is revoked, expires,
its owner is deactivated, or its workspace is shut off — plus one structural
property: the stored `key_prefix` is a non-unique lookup hint, so a collision
must fall through to the hash check rather than 500.

The FastAPI wiring that decides *when* to consult this lives in
`app.core.dependencies` and is covered by `tests/integration/test_api_key_auth.py`.
"""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.core.api_keys import (
    KEY_PREFIX,
    KEY_PREFIX_LEN,
    LAST_USED_RESOLUTION,
    authenticate_api_key,
    looks_like_api_key,
)
from app.core.security import generate_api_key, get_password_hash
from app.models.user import ApiKey


async def _make_key(db, user, organization, *, token=None, **overrides):
    """Insert an ApiKey row and return (plaintext_token, row)."""
    if token is None:
        token, _ = generate_api_key()

    fields = {
        "user_id": user.id,
        "organization_id": organization.id,
        "name": "Test Key",
        "key_hash": get_password_hash(token),
        "key_prefix": token[:KEY_PREFIX_LEN],
        "scopes": [],
        "is_active": True,
    }
    fields.update(overrides)

    api_key = ApiKey(**fields)
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return token, api_key


@pytest.mark.unit
@pytest.mark.auth
class TestTokenShape:
    def test_a_vcon_token_is_recognised(self):
        assert looks_like_api_key(f"{KEY_PREFIX}abc123") is True

    def test_a_jwt_is_not_mistaken_for_a_key(self):
        """
        The header carries either kind, and this is what tells them apart
        without trying to decode either.
        """
        assert looks_like_api_key("eyJhbGciOiJIUzI1NiJ9.e30.sig") is False

    @pytest.mark.parametrize("token", [None, "", "   ", "notvcon_abc"])
    def test_anything_else_is_refused(self, token):
        assert looks_like_api_key(token) is False


@pytest.mark.unit
@pytest.mark.auth
class TestAuthentication:
    async def test_a_valid_key_authenticates(
        self, db_session, test_user, test_organization
    ):
        token, api_key = await _make_key(db_session, test_user, test_organization)

        resolved = await authenticate_api_key(db_session, token)

        assert resolved.id == api_key.id

    async def test_the_owner_and_workspace_are_loaded(
        self, db_session, test_user, test_organization
    ):
        """
        Eagerly loaded on purpose: the caller builds a workspace context from
        both, and lazy-loading them on an async session raises MissingGreenlet.
        """
        token, _ = await _make_key(db_session, test_user, test_organization)

        resolved = await authenticate_api_key(db_session, token)

        assert resolved.user.id == test_user.id
        assert resolved.organization.id == test_organization.id

    async def test_a_key_that_was_never_issued_is_refused(self, db_session):
        unknown, _ = generate_api_key()

        with pytest.raises(HTTPException) as exc:
            await authenticate_api_key(db_session, unknown)

        assert exc.value.status_code == 401

    async def test_a_token_that_is_not_a_key_is_refused(self, db_session):
        with pytest.raises(HTTPException) as exc:
            await authenticate_api_key(db_session, "eyJhbGciOiJIUzI1NiJ9.e30.s")

        assert exc.value.status_code == 401

    async def test_the_right_prefix_with_the_wrong_secret_is_refused(
        self, db_session, test_user, test_organization
    ):
        """
        The prefix is a lookup hint, not a credential. Knowing it — it is shown
        in the UI — must not authenticate anything.
        """
        token, _ = await _make_key(db_session, test_user, test_organization)
        forged = token[:KEY_PREFIX_LEN] + "X" * (len(token) - KEY_PREFIX_LEN)

        with pytest.raises(HTTPException):
            await authenticate_api_key(db_session, forged)

    async def test_every_failure_gives_the_same_answer(
        self, db_session, test_user, test_organization
    ):
        """
        Distinguishing "no such key" from "wrong secret" would hand an attacker
        an oracle for enumerating valid prefixes.
        """
        token, _ = await _make_key(
            db_session, test_user, test_organization, is_active=False
        )
        unknown, _ = generate_api_key()

        errors = []
        for candidate in (token, unknown):
            with pytest.raises(HTTPException) as exc:
                await authenticate_api_key(db_session, candidate)
            errors.append((exc.value.status_code, exc.value.detail))

        assert errors[0] == errors[1]


@pytest.mark.unit
@pytest.mark.auth
class TestRevocationPaths:
    async def test_a_revoked_key_stops_working(
        self, db_session, test_user, test_organization
    ):
        token, _ = await _make_key(
            db_session, test_user, test_organization, is_active=False
        )

        with pytest.raises(HTTPException):
            await authenticate_api_key(db_session, token)

    async def test_an_expired_key_stops_working(
        self, db_session, test_user, test_organization
    ):
        token, _ = await _make_key(
            db_session,
            test_user,
            test_organization,
            expires_at=datetime.utcnow() - timedelta(seconds=1),
        )

        with pytest.raises(HTTPException):
            await authenticate_api_key(db_session, token)

    async def test_a_key_expiring_in_the_future_still_works(
        self, db_session, test_user, test_organization
    ):
        token, _ = await _make_key(
            db_session,
            test_user,
            test_organization,
            expires_at=datetime.utcnow() + timedelta(days=1),
        )

        assert await authenticate_api_key(db_session, token) is not None

    async def test_a_key_with_no_expiry_does_not_expire(
        self, db_session, test_user, test_organization
    ):
        token, _ = await _make_key(
            db_session, test_user, test_organization, expires_at=None
        )

        assert await authenticate_api_key(db_session, token) is not None

    async def test_deactivating_the_owner_kills_their_keys(
        self, db_session, test_user, test_organization
    ):
        """A key is only as good as the account behind it."""
        token, _ = await _make_key(db_session, test_user, test_organization)

        test_user.is_active = False
        await db_session.commit()

        with pytest.raises(HTTPException):
            await authenticate_api_key(db_session, token)

    async def test_deactivating_the_workspace_kills_its_keys(
        self, db_session, test_user, test_organization
    ):
        token, _ = await _make_key(db_session, test_user, test_organization)

        test_organization.is_active = False
        await db_session.commit()

        with pytest.raises(HTTPException):
            await authenticate_api_key(db_session, token)


@pytest.mark.unit
@pytest.mark.auth
class TestPrefixCollision:
    async def test_two_keys_sharing_a_prefix_each_authenticate_as_themselves(
        self, db_session, test_user, test_organization
    ):
        """
        Seven secret characters can collide. The lookup collects every candidate
        and hash-checks each, so a collision must not 500 or cross-authenticate.
        Narrowing this back to `scalar_one_or_none()` would raise
        MultipleResultsFound.
        """
        shared_prefix = f"{KEY_PREFIX}collide"
        first = shared_prefix + "-first-half-of-the-secret"
        second = shared_prefix + "-second-half-of-the-secret"

        _, first_row = await _make_key(
            db_session, test_user, test_organization, token=first
        )
        _, second_row = await _make_key(
            db_session, test_user, test_organization, token=second
        )
        assert first_row.key_prefix == second_row.key_prefix

        assert (await authenticate_api_key(db_session, first)).id == first_row.id
        assert (await authenticate_api_key(db_session, second)).id == second_row.id

    async def test_a_collision_does_not_let_a_third_secret_in(
        self, db_session, test_user, test_organization
    ):
        shared_prefix = f"{KEY_PREFIX}collide"
        await _make_key(
            db_session, test_user, test_organization, token=shared_prefix + "-aaaa"
        )
        await _make_key(
            db_session, test_user, test_organization, token=shared_prefix + "-bbbb"
        )

        with pytest.raises(HTTPException):
            await authenticate_api_key(db_session, shared_prefix + "-cccc")


@pytest.mark.unit
@pytest.mark.auth
class TestLastUsedTracking:
    async def test_first_use_is_recorded(
        self, db_session, test_user, test_organization
    ):
        token, api_key = await _make_key(
            db_session, test_user, test_organization, last_used_at=None
        )

        await authenticate_api_key(db_session, token)

        await db_session.refresh(api_key)
        assert api_key.last_used_at is not None

    async def test_a_recent_write_is_not_repeated(
        self, db_session, test_user, test_organization
    ):
        """
        Without this throttle a busy integration turns every read into a write.
        Minute resolution is plenty for "when was this key last seen".
        """
        just_now = datetime.utcnow() - timedelta(seconds=1)
        token, api_key = await _make_key(
            db_session, test_user, test_organization, last_used_at=just_now
        )

        await authenticate_api_key(db_session, token)

        await db_session.refresh(api_key)
        assert api_key.last_used_at == just_now

    async def test_a_stale_timestamp_is_refreshed(
        self, db_session, test_user, test_organization
    ):
        stale = datetime.utcnow() - LAST_USED_RESOLUTION - timedelta(minutes=1)
        token, api_key = await _make_key(
            db_session, test_user, test_organization, last_used_at=stale
        )

        await authenticate_api_key(db_session, token)

        await db_session.refresh(api_key)
        assert api_key.last_used_at > stale
