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


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password using bcrypt.
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
    )


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    Truncates password to 72 bytes if necessary (bcrypt limitation).
    """
    # Truncate password to 72 bytes to avoid bcrypt error
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]

    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    scopes: Optional[list] = None
) -> str:
    """
    Create a JWT access token.

    Args:
        subject: The subject of the token (usually user ID)
        expires_delta: Optional custom expiration time
        scopes: Optional list of scopes/permissions

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
        "type": "access"
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
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.

    Args:
        subject: The subject of the token (usually user ID)
        expires_delta: Optional custom expiration time

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
        "type": "refresh"
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
