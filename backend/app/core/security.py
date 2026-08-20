"""
Security utilities for authentication, password hashing, and JWT tokens.
"""
from datetime import datetime, timedelta
from typing import Any, Optional, Union
from jose import jwt, JWTError
import bcrypt
from cryptography.fernet import Fernet
import secrets

from app.core.config import settings


#: bcrypt hashes at most 72 bytes of input and raises on anything longer.
BCRYPT_MAX_BYTES = 72


def _bcrypt_bytes(password: str) -> bytes:
    """
    Encode a password for bcrypt, clipped to the 72 bytes bcrypt will read.

    Hashing and verifying MUST clip identically. They did not: hashing truncated
    and verifying passed the full string, so a password longer than 72 bytes
    registered successfully and then raised `ValueError` on every subsequent
    login — a permanent lockout, surfacing as a 500. Nothing caps password
    length on the way in, so a long passphrase was enough to trigger it.
    """
    encoded = password.encode('utf-8')
    return encoded[:BCRYPT_MAX_BYTES]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password using bcrypt.
    """
    return bcrypt.checkpw(
        _bcrypt_bytes(plain_password),
        hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
    )


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    Truncates password to 72 bytes if necessary (bcrypt limitation).
    """
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(_bcrypt_bytes(password), salt)
    return hashed.decode('utf-8')


#: Claim carrying the issuing user's ``token_version``.
#:
#: A JWT cannot be withdrawn once signed, so revocation has to be something the
#: server checks at use time. Every token records the version the account held
#: when it was issued; bumping ``User.token_version`` leaves every outstanding
#: token stale. See the column's docstring in app.models.user.
TOKEN_VERSION_CLAIM = "tv"


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    scopes: Optional[list] = None,
    token_version: int = 0,
) -> str:
    """
    Create a JWT access token.

    Args:
        subject: The subject of the token (usually user ID)
        expires_delta: Optional custom expiration time
        scopes: Optional list of scopes/permissions
        token_version: The user's current ``token_version``, so the token can be
            invalidated later by incrementing it.

    Returns:
        Encoded JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access",
        TOKEN_VERSION_CLAIM: int(token_version or 0),
    }

    if scopes:
        to_encode["scopes"] = scopes

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    token_version: int = 0,
) -> str:
    """
    Create a JWT refresh token.

    Args:
        subject: The subject of the token (usually user ID)
        expires_delta: Optional custom expiration time
        token_version: The user's current ``token_version``. This matters most
            here — a refresh token lives for 30 days, so without it a stolen one
            outlives any password change made in response to the theft.

    Returns:
        Encoded JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        TOKEN_VERSION_CLAIM: int(token_version or 0),
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT token.

    Args:
        token: The JWT token to decode

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def token_version_matches(payload: dict, user: Any) -> bool:
    """Whether ``payload`` was issued before the user last revoked their sessions.

    Tokens minted before this claim existed carry no ``tv``. Those are treated
    as version 0, which is also the column default — so deploying this does not
    sign everyone out. Anyone whose ``token_version`` is later incremented is
    then correctly locked out of their old tokens.
    """
    presented = payload.get(TOKEN_VERSION_CLAIM, 0)
    current = getattr(user, "token_version", 0) or 0
    try:
        return int(presented or 0) == int(current)
    except (TypeError, ValueError):
        # A non-numeric claim is not something we issued.
        return False


#: Minutes a proof-of-verified-email token stays usable. Long enough to finish
#: filling in the sign-up form, short enough that a leaked token is not a
#: standing permit to register that address.
EMAIL_VERIFICATION_TOKEN_MINUTES = 30


def create_email_verification_token(
    email: str,
    expires_minutes: int = EMAIL_VERIFICATION_TOKEN_MINUTES,
) -> str:
    """
    Issue proof that `email` was confirmed by a one-time code.

    Handed to the client after a correct code and handed back on register, so
    the account can only be created for an address the user actually controls.
    """
    return jwt.encode(
        {
            "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
            "sub": email.strip().lower(),
            "type": "email_verification",
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def verify_email_verification_token(token: str, email: str) -> bool:
    """True when `token` is a live verification proof for `email`."""
    payload = decode_token(token)
    if not payload or payload.get("type") != "email_verification":
        return False
    return payload.get("sub") == email.strip().lower()


def generate_api_key() -> tuple[str, str]:
    """
    Generate an API key and its hash.

    Returns:
        Tuple of (api_key, api_key_hash)
    """
    # Generate a secure random key
    api_key = f"vcon_{secrets.token_urlsafe(32)}"
    # Hash it for storage
    api_key_hash = get_password_hash(api_key)
    return api_key, api_key_hash


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its hash.
    """
    return verify_password(plain_key, hashed_key)


# Encryption for sensitive data (API keys, tokens, etc.)
class EncryptionManager:
    """
    Manager for encrypting and decrypting sensitive data.
    Uses Fernet (symmetric encryption) for simplicity.
    """

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize with an encryption key.
        If no key provided, uses SECRET_KEY from settings.
        """
        if encryption_key:
            self.key = encryption_key.encode()
        else:
            # Derive key from SECRET_KEY
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'voicecon_salt',  # In production, use environment-specific salt
                iterations=100000,
            )
            self.key = base64.urlsafe_b64encode(
                kdf.derive(settings.SECRET_KEY.encode())
            )

        self.cipher = Fernet(self.key)

    def encrypt(self, data: str) -> str:
        """
        Encrypt a string.

        Args:
            data: Plain text string to encrypt

        Returns:
            Encrypted string (base64 encoded)
        """
        if not data:
            return ""
        encrypted_bytes = self.cipher.encrypt(data.encode())
        return encrypted_bytes.decode()

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt a string.

        Args:
            encrypted_data: Encrypted string (base64 encoded)

        Returns:
            Decrypted plain text string
        """
        if not encrypted_data:
            return ""
        try:
            decrypted_bytes = self.cipher.decrypt(encrypted_data.encode())
            return decrypted_bytes.decode()
        except Exception:
            return ""


# Global encryption manager instance
encryption_manager = EncryptionManager()


def encrypt_sensitive_data(data: str) -> str:
    """
    Encrypt sensitive data (API keys, tokens, etc.)
    """
    return encryption_manager.encrypt(data)


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """
    Decrypt sensitive data
    """
    return encryption_manager.decrypt(encrypted_data)
