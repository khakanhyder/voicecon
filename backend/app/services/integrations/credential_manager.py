"""
Credential Manager.

Handles secure encryption/decryption of integration credentials.
"""
import logging
import os
import json
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC as PBKDF2
from cryptography.hazmat.backends import default_backend
import base64

from app.core.config import settings

logger = logging.getLogger(__name__)


class CredentialEncryptionError(Exception):
    """Raised when credential encryption fails."""
    pass


class CredentialDecryptionError(Exception):
    """Raised when credential decryption fails."""
    pass


class CredentialManager:
    """
    Manages secure encryption and decryption of integration credentials.

    Uses Fernet (symmetric encryption) for credential storage.
    All credentials are encrypted before storing in database.
    """

    def __init__(self):
        """Initialize credential manager."""
        self._fernet: Optional[Fernet] = None
        self._encryption_key: Optional[bytes] = None

    def _get_encryption_key(self) -> bytes:
        """
        Get or create encryption key.

        Returns:
            Encryption key bytes

        Raises:
            CredentialEncryptionError: If key cannot be generated
        """
        if self._encryption_key is not None:
            return self._encryption_key

        try:
            # Get secret key from environment
            secret_key = getattr(settings, 'ENCRYPTION_SECRET_KEY', None) or os.getenv(
                'ENCRYPTION_SECRET_KEY',
                'default-secret-key-change-in-production'  # Default for development
            )

            # Generate encryption key from secret using PBKDF2
            salt = b'voicecon-integration-salt'  # Fixed salt for deterministic key

            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )

            key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
            self._encryption_key = key

            logger.info("Encryption key generated successfully")
            return key

        except Exception as e:
            logger.error(f"Failed to generate encryption key: {e}", exc_info=True)
            raise CredentialEncryptionError(f"Failed to generate encryption key: {str(e)}")

    def _get_fernet(self) -> Fernet:
        """
        Get or create Fernet cipher.

        Returns:
            Fernet instance
        """
        if self._fernet is None:
            key = self._get_encryption_key()
            self._fernet = Fernet(key)

        return self._fernet

    def encrypt(self, data: str) -> str:
        """
        Encrypt a string.

        Args:
            data: String to encrypt

        Returns:
            Encrypted string (base64 encoded)

        Raises:
            CredentialEncryptionError: If encryption fails
        """
        if not data:
            return ""

        try:
            fernet = self._get_fernet()
            encrypted_bytes = fernet.encrypt(data.encode('utf-8'))
            encrypted_string = encrypted_bytes.decode('utf-8')

            logger.debug(f"Successfully encrypted data (length: {len(data)})")
            return encrypted_string

        except Exception as e:
            logger.error(f"Encryption failed: {e}", exc_info=True)
            raise CredentialEncryptionError(f"Encryption failed: {str(e)}")

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            encrypted_data: Encrypted string to decrypt

        Returns:
            Decrypted string

        Raises:
            CredentialDecryptionError: If decryption fails
        """
        if not encrypted_data:
            return ""

        try:
            fernet = self._get_fernet()
            decrypted_bytes = fernet.decrypt(encrypted_data.encode('utf-8'))
            decrypted_string = decrypted_bytes.decode('utf-8')

            logger.debug(f"Successfully decrypted data (length: {len(decrypted_string)})")
            return decrypted_string

        except Exception as e:
            logger.error(f"Decryption failed: {e}", exc_info=True)
            raise CredentialDecryptionError(f"Decryption failed: {str(e)}")

    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """
        Encrypt a dictionary as JSON.

        Args:
            data: Dictionary to encrypt

        Returns:
            Encrypted JSON string

        Raises:
            CredentialEncryptionError: If encryption fails
        """
        try:
            json_string = json.dumps(data)
            return self.encrypt(json_string)

        except Exception as e:
            logger.error(f"Dictionary encryption failed: {e}", exc_info=True)
            raise CredentialEncryptionError(f"Dictionary encryption failed: {str(e)}")

    def decrypt_dict(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt an encrypted JSON string to dictionary.

        Args:
            encrypted_data: Encrypted JSON string

        Returns:
            Decrypted dictionary

        Raises:
            CredentialDecryptionError: If decryption fails
        """
        if not encrypted_data:
            return {}

        try:
            decrypted_string = self.decrypt(encrypted_data)
            return json.loads(decrypted_string)

        except Exception as e:
            logger.error(f"Dictionary decryption failed: {e}", exc_info=True)
            raise CredentialDecryptionError(f"Dictionary decryption failed: {str(e)}")

    def encrypt_oauth_tokens(
        self,
        access_token: str,
        refresh_token: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Encrypt OAuth tokens.

        Args:
            access_token: OAuth access token
            refresh_token: Optional OAuth refresh token

        Returns:
            Dictionary with encrypted tokens

        Raises:
            CredentialEncryptionError: If encryption fails
        """
        result = {
            "access_token_encrypted": self.encrypt(access_token)
        }

        if refresh_token:
            result["refresh_token_encrypted"] = self.encrypt(refresh_token)

        return result

    def decrypt_oauth_tokens(
        self,
        access_token_encrypted: str,
        refresh_token_encrypted: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Decrypt OAuth tokens.

        Args:
            access_token_encrypted: Encrypted access token
            refresh_token_encrypted: Optional encrypted refresh token

        Returns:
            Dictionary with decrypted tokens

        Raises:
            CredentialDecryptionError: If decryption fails
        """
        result = {
            "access_token": self.decrypt(access_token_encrypted)
        }

        if refresh_token_encrypted:
            result["refresh_token"] = self.decrypt(refresh_token_encrypted)

        return result


# Global credential manager instance
_credential_manager: Optional[CredentialManager] = None


def get_credential_manager() -> CredentialManager:
    """
    Get global credential manager instance (singleton).

    Returns:
        CredentialManager instance
    """
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = CredentialManager()
    return _credential_manager
