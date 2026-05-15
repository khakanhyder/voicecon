"""
Unit tests for Authentication Service.

Tests user authentication, token management, and password handling.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from jose import jwt, JWTError

from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.config import settings


@pytest.mark.unit
class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "test_password_123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_correct_password(self):
        """Test verifying correct password."""
        password = "test_password_123"
        hashed = get_password_hash(password)

        is_valid = verify_password(password, hashed)
        assert is_valid is True

    def test_verify_incorrect_password(self):
        """Test verifying incorrect password."""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)

        is_valid = verify_password(wrong_password, hashed)
        assert is_valid is False

    def test_hash_same_password_twice(self):
        """Test that hashing same password twice produces different hashes."""
        password = "test_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Hashes should be different due to salt
        assert hash1 != hash2

        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_hash_empty_password(self):
        """Test hashing empty password."""
        password = ""
        hashed = get_password_hash(password)

        assert len(hashed) > 0
        assert verify_password(password, hashed) is True

    def test_hash_long_password(self):
        """Test hashing very long password."""
        password = "a" * 200
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_hash_special_characters(self):
        """Test hashing password with special characters."""
        password = "p@ssw0rd!#$%^&*()_+-=[]{}|;:',.<>?/~`"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_hash_unicode_password(self):
        """Test hashing password with unicode characters."""
        password = "pässwörd123密码"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True


@pytest.mark.unit
class TestTokenGeneration:
    """Test JWT token generation."""

    def test_create_access_token(self):
        """Test creating access token."""
        user_id = uuid.uuid4()
        token = create_access_token(
            data={"sub": str(user_id), "type": "access"}
        )

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self):
        """Test creating refresh token."""
        user_id = uuid.uuid4()
        token = create_refresh_token(
            data={"sub": str(user_id), "type": "refresh"}
        )

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_access_token_contains_user_id(self):
        """Test that access token contains user ID."""
        user_id = uuid.uuid4()
        token = create_access_token(
            data={"sub": str(user_id), "type": "access"}
        )

        # Decode without verification for testing
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_refresh_token_contains_user_id(self):
        """Test that refresh token contains user ID."""
        user_id = uuid.uuid4()
        token = create_refresh_token(
            data={"sub": str(user_id), "type": "refresh"}
        )

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"

    def test_token_with_custom_expiration(self):
        """Test creating token with custom expiration."""
        user_id = uuid.uuid4()
        custom_expiration = timedelta(hours=24)

        token = create_access_token(
            data={"sub": str(user_id)},
            expires_delta=custom_expiration,
        )

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        exp_timestamp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp)
        now = datetime.utcnow()

        time_diff = exp_datetime - now
        # Should be approximately 24 hours (allowing small variance)
        assert 23 * 3600 < time_diff.total_seconds() < 25 * 3600

    def test_token_with_additional_claims(self):
        """Test creating token with additional claims."""
        user_id = uuid.uuid4()
        token = create_access_token(
            data={
                "sub": str(user_id),
                "email": "test@example.com",
                "role": "admin",
            }
        )

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        assert payload["sub"] == str(user_id)
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "admin"


@pytest.mark.unit
class TestTokenDecoding:
    """Test JWT token decoding and validation."""

    def test_decode_valid_token(self):
        """Test decoding valid token."""
        user_id = uuid.uuid4()
        token = create_access_token(
            data={"sub": str(user_id), "type": "access"}
        )

        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_decode_expired_token(self):
        """Test decoding expired token."""
        user_id = uuid.uuid4()

        # Create token that expires immediately
        token = create_access_token(
            data={"sub": str(user_id)},
            expires_delta=timedelta(seconds=-1),  # Already expired
        )

        with pytest.raises(JWTError):
            decode_token(token)

    def test_decode_invalid_token(self):
        """Test decoding invalid token."""
        invalid_token = "invalid.token.string"

        with pytest.raises(JWTError):
            decode_token(invalid_token)

    def test_decode_token_with_wrong_secret(self):
        """Test decoding token with wrong secret key."""
        user_id = uuid.uuid4()
        token = create_access_token(data={"sub": str(user_id)})

        # Try to decode with wrong secret
        with pytest.raises(JWTError):
            jwt.decode(
                token,
                "wrong_secret_key",
                algorithms=[settings.ALGORITHM],
            )

    def test_decode_token_with_wrong_algorithm(self):
        """Test decoding token with wrong algorithm."""
        user_id = uuid.uuid4()
        token = create_access_token(data={"sub": str(user_id)})

        # Try to decode with wrong algorithm
        with pytest.raises(JWTError):
            jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS384"],  # Wrong algorithm
            )

    def test_decode_tampered_token(self):
        """Test decoding tampered token."""
        user_id = uuid.uuid4()
        token = create_access_token(data={"sub": str(user_id)})

        # Tamper with the token
        parts = token.split(".")
        tampered_token = parts[0] + ".modified." + parts[2]

        with pytest.raises(JWTError):
            decode_token(tampered_token)


@pytest.mark.unit
class TestTokenExpiration:
    """Test token expiration handling."""

    def test_access_token_default_expiration(self):
        """Test access token default expiration time."""
        user_id = uuid.uuid4()
        token = create_access_token(data={"sub": str(user_id)})

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        exp_timestamp = payload["exp"]
        iat_timestamp = payload["iat"]

        # Calculate token lifetime
        lifetime = exp_timestamp - iat_timestamp

        # Access token should expire in 30 minutes (1800 seconds)
        assert lifetime == 1800

    def test_refresh_token_longer_expiration(self):
        """Test refresh token has longer expiration."""
        user_id = uuid.uuid4()
        access_token = create_access_token(data={"sub": str(user_id)})
        refresh_token = create_refresh_token(data={"sub": str(user_id)})

        access_payload = jwt.decode(
            access_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        refresh_payload = jwt.decode(
            refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        access_lifetime = access_payload["exp"] - access_payload["iat"]
        refresh_lifetime = refresh_payload["exp"] - refresh_payload["iat"]

        # Refresh token should have longer lifetime
        assert refresh_lifetime > access_lifetime

    def test_token_issued_at_time(self):
        """Test token issued at time is correct."""
        before = datetime.utcnow()
        user_id = uuid.uuid4()
        token = create_access_token(data={"sub": str(user_id)})
        after = datetime.utcnow()

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        iat_datetime = datetime.fromtimestamp(payload["iat"])

        # Issued at time should be between before and after
        assert before <= iat_datetime <= after


@pytest.mark.unit
@pytest.mark.asyncio
class TestAuthenticationFlow:
    """Test complete authentication flows."""

    async def test_registration_password_storage(self, db_session):
        """Test that passwords are hashed during registration."""
        from app.models.user import User

        plain_password = "test_password_123"
        hashed_password = get_password_hash(plain_password)

        user = User(
            email="newuser@example.com",
            hashed_password=hashed_password,
            full_name="New User",
        )

        db_session.add(user)
        await db_session.commit()

        # Verify password is hashed
        assert user.hashed_password != plain_password
        assert verify_password(plain_password, user.hashed_password) is True

    async def test_login_token_generation(self):
        """Test token generation during login."""
        user_id = uuid.uuid4()

        # Generate tokens
        access_token = create_access_token(
            data={"sub": str(user_id), "type": "access"}
        )
        refresh_token = create_refresh_token(
            data={"sub": str(user_id), "type": "refresh"}
        )

        # Verify both tokens are valid
        access_payload = decode_token(access_token)
        refresh_payload = decode_token(refresh_token)

        assert access_payload["sub"] == str(user_id)
        assert refresh_payload["sub"] == str(user_id)
        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"

    async def test_token_refresh_flow(self):
        """Test refreshing access token using refresh token."""
        user_id = uuid.uuid4()

        # Create initial tokens
        old_access_token = create_access_token(
            data={"sub": str(user_id), "type": "access"}
        )
        refresh_token = create_refresh_token(
            data={"sub": str(user_id), "type": "refresh"}
        )

        # Decode refresh token
        refresh_payload = decode_token(refresh_token)
        assert refresh_payload["type"] == "refresh"

        # Create new access token
        new_access_token = create_access_token(
            data={"sub": refresh_payload["sub"], "type": "access"}
        )

        # Verify new token is valid and different
        new_payload = decode_token(new_access_token)
        assert new_payload["sub"] == str(user_id)
        assert new_access_token != old_access_token

    async def test_password_change_invalidates_old_hash(self):
        """Test that changing password creates new hash."""
        old_password = "old_password_123"
        new_password = "new_password_456"

        old_hash = get_password_hash(old_password)
        new_hash = get_password_hash(new_password)

        # Hashes should be different
        assert old_hash != new_hash

        # Old password should not verify with new hash
        assert verify_password(old_password, new_hash) is False

        # New password should verify with new hash
        assert verify_password(new_password, new_hash) is True
