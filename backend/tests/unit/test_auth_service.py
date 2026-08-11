"""
Unit tests for authentication primitives: password hashing and JWT tokens.

Everything here is in `app.core.security`, which is what stands between the
public sign-up form and an authenticated session — so these tests care as much
about what must be *rejected* (tampered tokens, wrong secrets, refresh tokens
used as access tokens) as about the happy path.
"""
import base64
import json
import time
import uuid
from datetime import datetime, timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    BCRYPT_MAX_BYTES,
    create_access_token,
    create_email_verification_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    get_password_hash,
    verify_api_key,
    verify_email_verification_token,
    verify_password,
)


def _claims(token: str) -> dict:
    """Decode a token the way the app does, so a bad signature fails the test."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


@pytest.mark.unit
@pytest.mark.auth
class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password(self):
        password = "test_password_123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_correct_password(self):
        password = "test_password_123"

        assert verify_password(password, get_password_hash(password)) is True

    def test_verify_incorrect_password(self):
        hashed = get_password_hash("test_password_123")

        assert verify_password("wrong_password", hashed) is False

    def test_hash_same_password_twice(self):
        """Per-hash salt: identical passwords must not produce identical hashes."""
        password = "test_password_123"
        hash1, hash2 = get_password_hash(password), get_password_hash(password)

        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_hash_empty_password(self):
        hashed = get_password_hash("")

        assert verify_password("", hashed) is True

    def test_hash_special_characters(self):
        password = "p@ssw0rd!#$%^&*()_+-=[]{}|;:',.<>?/~`"

        assert verify_password(password, get_password_hash(password)) is True

    def test_hash_unicode_password(self):
        password = "pässwörd123密码"

        assert verify_password(password, get_password_hash(password)) is True

    def test_long_password_can_still_log_in(self):
        """
        Regression: bcrypt reads at most 72 bytes and raises past that. Hashing
        truncated but verifying did not, so a long passphrase registered fine and
        then 500'd on every login. Nothing caps password length on the way in.
        """
        password = "a" * 200

        assert verify_password(password, get_password_hash(password)) is True

    def test_long_unicode_password_can_still_log_in(self):
        """Truncation is on *bytes*, so multi-byte characters must not crash it."""
        password = "密码" * 100  # 3 bytes each → 600 bytes

        assert verify_password(password, get_password_hash(password)) is True

    def test_passwords_differing_past_the_bcrypt_limit_are_equivalent(self):
        """
        Documents an accepted consequence of bcrypt's 72-byte window: anything
        beyond it is not read, so two passwords sharing a 72-byte prefix collide.
        Asserted so that a future switch to a pre-hashing scheme is a deliberate,
        visible change rather than a silent one.
        """
        base = "x" * BCRYPT_MAX_BYTES

        assert verify_password(base + "AAA", get_password_hash(base + "ZZZ")) is True

    def test_verify_against_a_malformed_hash_does_not_pass(self):
        """A corrupt or empty hash column must never authenticate anybody."""
        for bad_hash in ("", "not-a-bcrypt-hash", "$2b$12$tooshort"):
            try:
                assert verify_password("anything", bad_hash) is False
            except ValueError:
                pass  # bcrypt refusing to parse it is an equally safe outcome


@pytest.mark.unit
@pytest.mark.auth
class TestTokenGeneration:
    """Test JWT token generation."""

    def test_create_access_token(self):
        token = create_access_token(subject=uuid.uuid4())

        assert isinstance(token, str)
        assert token.count(".") == 2  # header.payload.signature

    def test_create_refresh_token(self):
        token = create_refresh_token(subject=uuid.uuid4())

        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_access_token_carries_subject_and_type(self):
        user_id = uuid.uuid4()

        claims = _claims(create_access_token(subject=user_id))

        assert claims["sub"] == str(user_id)
        assert claims["type"] == "access"

    def test_refresh_token_carries_subject_and_type(self):
        user_id = uuid.uuid4()

        claims = _claims(create_refresh_token(subject=user_id))

        assert claims["sub"] == str(user_id)
        assert claims["type"] == "refresh"

    def test_subject_is_stringified(self):
        """`sub` must be a string — a raw UUID makes the token unencodable."""
        claims = _claims(create_access_token(subject=12345))

        assert claims["sub"] == "12345"
        assert isinstance(claims["sub"], str)

    def test_token_with_custom_expiration(self):
        token = create_access_token(
            subject=uuid.uuid4(), expires_delta=timedelta(hours=24)
        )

        expires_in = _claims(token)["exp"] - time.time()

        assert 23 * 3600 < expires_in < 25 * 3600

    def test_scopes_are_included_when_given(self):
        claims = _claims(
            create_access_token(subject=uuid.uuid4(), scopes=["agents:read", "calls:write"])
        )

        assert claims["scopes"] == ["agents:read", "calls:write"]

    def test_scopes_are_omitted_when_not_given(self):
        """An unscoped token must not carry an empty scope list to reason about."""
        assert "scopes" not in _claims(create_access_token(subject=uuid.uuid4()))


@pytest.mark.unit
@pytest.mark.auth
class TestTokenDecoding:
    """Test JWT token decoding and validation."""

    def test_decode_valid_token(self):
        user_id = uuid.uuid4()

        payload = decode_token(create_access_token(subject=user_id))

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_decode_returns_none_rather_than_raising(self):
        """
        Callers branch on a falsy return, so `decode_token` swallows JWTError.
        A raised exception here would escape as a 500 instead of a 401.
        """
        assert decode_token("invalid.token.string") is None

    def test_decode_expired_token(self):
        token = create_access_token(
            subject=uuid.uuid4(), expires_delta=timedelta(seconds=-1)
        )

        assert decode_token(token) is None

    def test_decode_tampered_payload(self):
        """Re-signing is required to change claims; editing them must not work."""
        token = create_access_token(subject=uuid.uuid4())
        header, _, signature = token.split(".")

        forged = create_access_token(subject="attacker").split(".")[1]

        assert decode_token(f"{header}.{forged}.{signature}") is None

    def test_token_signed_with_another_secret_is_rejected(self):
        """The whole security property: only this server can mint valid tokens."""
        forged = jwt.encode(
            {"sub": "attacker", "type": "access",
             "exp": datetime.utcnow() + timedelta(hours=1)},
            "not-the-real-secret",
            algorithm=settings.ALGORITHM,
        )

        assert decode_token(forged) is None

    def test_unsigned_token_is_rejected(self):
        """
        `alg: none` is the classic JWT bypass. Assembled by hand because the
        library refuses to *sign* it — which is exactly how an attacker would
        produce one.
        """
        def b64(payload: dict) -> str:
            raw = json.dumps(payload).encode()
            return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

        unsigned = "{}.{}.".format(
            b64({"alg": "none", "typ": "JWT"}),
            b64({"sub": "attacker", "type": "access", "exp": int(time.time()) + 3600}),
        )

        assert decode_token(unsigned) is None

    def test_empty_token_is_rejected(self):
        assert decode_token("") is None


@pytest.mark.unit
@pytest.mark.auth
class TestTokenExpiration:
    """Test token expiration handling."""

    def test_access_token_uses_the_configured_lifetime(self):
        token = create_access_token(subject=uuid.uuid4())

        expires_in = _claims(token)["exp"] - time.time()

        expected = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert abs(expires_in - expected) < 10

    def test_refresh_token_outlives_the_access_token(self):
        """Otherwise refreshing would be pointless — both would die together."""
        user_id = uuid.uuid4()

        access_exp = _claims(create_access_token(subject=user_id))["exp"]
        refresh_exp = _claims(create_refresh_token(subject=user_id))["exp"]

        assert refresh_exp > access_exp

    def test_tokens_expire_at_all(self):
        """A token with no `exp` never expires and can never be revoked."""
        claims = _claims(create_access_token(subject=uuid.uuid4()))

        assert "exp" in claims


@pytest.mark.unit
@pytest.mark.auth
class TestEmailVerificationTokens:
    """Proof that an address was confirmed before an account is created for it."""

    def test_token_verifies_for_its_own_address(self):
        token = create_email_verification_token("user@example.com")

        assert verify_email_verification_token(token, "user@example.com") is True

    def test_address_is_matched_case_insensitively_and_trimmed(self):
        """Sign-up forms send whatever the user typed; the check normalises both."""
        token = create_email_verification_token("  User@Example.COM ")

        assert verify_email_verification_token(token, "user@example.com") is True

    def test_token_does_not_verify_another_address(self):
        """
        The core property: a token proving you own A must not let you register B.
        """
        token = create_email_verification_token("user@example.com")

        assert verify_email_verification_token(token, "victim@example.com") is False

    def test_an_access_token_is_not_a_verification_proof(self):
        """Type confusion here would turn any session into a verified address."""
        token = create_access_token(subject="user@example.com")

        assert verify_email_verification_token(token, "user@example.com") is False

    def test_expired_verification_token_is_refused(self):
        token = create_email_verification_token("user@example.com", expires_minutes=-1)

        assert verify_email_verification_token(token, "user@example.com") is False

    def test_garbage_is_refused(self):
        assert verify_email_verification_token("nonsense", "user@example.com") is False


@pytest.mark.unit
@pytest.mark.auth
class TestApiKeys:
    """API keys are bearer secrets; only their hash may be stored."""

    def test_generated_key_verifies_against_its_hash(self):
        key, key_hash = generate_api_key()

        assert verify_api_key(key, key_hash) is True

    def test_key_is_namespaced_for_recognisability(self):
        """The prefix is what lets leak scanners spot one in a public repo."""
        key, _ = generate_api_key()

        assert key.startswith("vcon_")

    def test_hash_does_not_contain_the_key(self):
        key, key_hash = generate_api_key()

        assert key not in key_hash

    def test_keys_are_unique(self):
        # Kept small deliberately: each call pays a 12-round bcrypt hash, and a
        # collision in 256-bit random tokens would show up at any sample size.
        keys = {generate_api_key()[0] for _ in range(5)}

        assert len(keys) == 5

    def test_another_key_does_not_verify(self):
        _, key_hash = generate_api_key()
        other_key, _ = generate_api_key()

        assert verify_api_key(other_key, key_hash) is False


@pytest.mark.unit
@pytest.mark.auth
class TestAuthenticationFlow:
    """The sequences these primitives are composed into."""

    async def test_registration_stores_only_a_hash(self, db_session):
        from app.models.user import User

        plain_password = "test_password_123"
        user = User(
            email="newuser@example.com",
            hashed_password=get_password_hash(plain_password),
            full_name="New User",
        )
        db_session.add(user)
        await db_session.commit()

        assert plain_password not in user.hashed_password
        assert verify_password(plain_password, user.hashed_password) is True

    async def test_login_issues_a_usable_token_pair(self):
        user_id = uuid.uuid4()

        access = decode_token(create_access_token(subject=user_id))
        refresh = decode_token(create_refresh_token(subject=user_id))

        assert access["sub"] == refresh["sub"] == str(user_id)
        assert access["type"] == "access"
        assert refresh["type"] == "refresh"

    async def test_refresh_flow_mints_a_new_access_token(self):
        user_id = uuid.uuid4()
        refresh_token = create_refresh_token(subject=user_id)

        payload = decode_token(refresh_token)
        assert payload["type"] == "refresh"

        new_access = decode_token(create_access_token(subject=payload["sub"]))

        assert new_access["sub"] == str(user_id)
        assert new_access["type"] == "access"

    async def test_access_and_refresh_tokens_are_distinguishable(self):
        """
        The `type` claim is the only thing stopping a refresh token — which lives
        30 days — from being accepted as a session token.
        """
        user_id = uuid.uuid4()

        assert decode_token(create_access_token(subject=user_id))["type"] == "access"
        assert decode_token(create_refresh_token(subject=user_id))["type"] == "refresh"

    async def test_password_change_invalidates_the_old_password(self):
        new_hash = get_password_hash("new_password_456")

        assert verify_password("old_password_123", new_hash) is False
        assert verify_password("new_password_456", new_hash) is True
