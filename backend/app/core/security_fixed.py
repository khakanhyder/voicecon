"""
SECURITY FIXED VERSION - Replace security.py with this file after review.

Security utilities for authentication, password hashing, and JWT tokens.

FIXES APPLIED:
1. Environment-specific salt for encryption key derivation
2. Improved error handling
3. Added key rotation support preparation
"""
from datetime import datetime, timedelta
from typing import Any, Optional, Union
from jose import jwt, JWTError
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import secrets
import os
import warnings

from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    """
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Token payload data
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.

    Args:
        data: Token payload data
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })

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

    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        raise JWTError("Invalid or expired token")


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


# ============================================================================
# FIXED: Encryption Manager with Environment-Specific Salt
# ============================================================================

class EncryptionManager:
    """
    Manager for encrypting and decrypting sensitive data.

    SECURITY FIX: Now uses environment-specific salt instead of fixed salt.

    Uses Fernet (symmetric encryption):
    - AES-128 in CBC mode
    - HMAC for authentication
    - Automatic key derivation from SECRET_KEY
    """

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize with an encryption key.

        If no key provided, derives key from SECRET_KEY + ENCRYPTION_SALT.

        SECURITY: ENCRYPTION_SALT must be set in environment variables and
        must be different for each deployment environment (dev/staging/prod).
        """
        if encryption_key:
            self.key = encryption_key.encode()
        else:
            # Derive key from SECRET_KEY with environment-specific salt
            self.key = self._derive_encryption_key()

        self.cipher = Fernet(self.key)

    def _derive_encryption_key(self) -> bytes:
        """
        Derive encryption key from SECRET_KEY using PBKDF2.

        SECURITY FIX: Uses environment-specific salt instead of fixed salt.
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        import base64

        # Get environment-specific salt
        salt = self._get_encryption_salt()

        # Use PBKDF2 for key derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,  # OWASP recommended minimum
        )

        # Derive key from SECRET_KEY
        derived_key = kdf.derive(settings.SECRET_KEY.encode())

        # Encode for Fernet
        return base64.urlsafe_b64encode(derived_key)

    def _get_encryption_salt(self) -> bytes:
        """
        Get encryption salt from environment variables.

        SECURITY FIX: Each environment (dev/staging/prod) must have unique salt.

        The salt should be:
        1. At least 16 bytes (128 bits)
        2. Randomly generated per environment
        3. Stored securely in environment variables
        4. Never committed to version control
        """
        # Try to get from environment
        salt_hex = getattr(settings, 'ENCRYPTION_SALT', None)

        if not salt_hex:
            # CRITICAL: No salt found - generate and warn
            import warnings
            warnings.warn(
                "ENCRYPTION_SALT not set in environment! "
                "Generating temporary salt. "
                "SET ENCRYPTION_SALT in production!",
                UserWarning,
                stacklevel=2
            )

            # Generate temporary salt (will be different on each restart!)
            # This is NOT suitable for production
            salt = os.urandom(16)

            print("=" * 80)
            print("SECURITY WARNING: ENCRYPTION_SALT not configured")
            print("Add this to your .env file:")
            print(f"ENCRYPTION_SALT={salt.hex()}")
            print("=" * 80)

            return salt

        # Convert hex string to bytes
        try:
            return bytes.fromhex(salt_hex)
        except ValueError:
            raise ValueError(
                "ENCRYPTION_SALT must be a valid hex string. "
                "Generate with: python -c 'import os; print(os.urandom(16).hex())'"
            )

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

        try:
            encrypted_bytes = self.cipher.encrypt(data.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            raise ValueError(f"Encryption failed: {str(e)}")

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
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")

    def rotate_key(self, old_key: Optional[str] = None) -> 'EncryptionManager':
        """
        Create new encryption manager with new key for key rotation.

        Usage:
            new_manager = old_manager.rotate_key()
            # Re-encrypt all data with new manager
        """
        # Generate new salt for key rotation
        new_salt = os.urandom(16)

        # In production, store this new salt securely
        print(f"New ENCRYPTION_SALT for rotation: {new_salt.hex()}")

        # Create new manager (would use new salt from environment)
        return EncryptionManager()


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


# Convenience functions for common operations
def encrypt_value(value: str) -> str:
    """Alias for encrypt_sensitive_data"""
    return encrypt_sensitive_data(value)


def decrypt_value(encrypted_value: str) -> str:
    """Alias for decrypt_sensitive_data"""
    return decrypt_sensitive_data(encrypted_value)
