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


#: PBKDF2 rounds. Unchanged from the original derivation on purpose — raising it
#: would change the derived key and orphan every credential already stored.
_KDF_ITERATIONS = 100_000

#: What the secret used to fall back to when ``ENCRYPTION_SECRET_KEY`` was unset.
#: Kept only so the re-encryption script can read the old ciphertext; nothing in
#: the request path may use it.
LEGACY_DEFAULT_SECRET = 'default-secret-key-change-in-production'

#: The salt that was hardcoded alongside it, for the same reason.
LEGACY_SALT = b'voicecon-integration-salt'


def derive_key(secret: str, salt: bytes) -> bytes:
    """Derive a Fernet key from a secret and salt via PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
        backend=default_backend(),
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode()))


def _require_secret() -> str:
    """The configured encryption secret, or refuse to encrypt anything.

    There is deliberately no fallback. The previous default meant a deployment
    that never set this still encrypted successfully — under a key committed to
    this repository — so the misconfiguration produced working software and no
    signal. Raising is the only way this failure becomes visible.
    """
    secret = settings.ENCRYPTION_SECRET_KEY or os.getenv('ENCRYPTION_SECRET_KEY')
    if not secret:
        raise CredentialEncryptionError(
            "ENCRYPTION_SECRET_KEY is not configured. Integration credentials "
            "cannot be encrypted or decrypted without it. Generate one with "
            "`python -c \"import secrets; print(secrets.token_urlsafe(48))\"`."
        )
    if secret == LEGACY_DEFAULT_SECRET:
        raise CredentialEncryptionError(
            "ENCRYPTION_SECRET_KEY is set to the old hardcoded default, which is "
            "public. Set a generated value and re-encrypt existing credentials "
            "with scripts/reencrypt_credentials.py."
        )
    return secret


def _require_salt() -> bytes:
    """The per-deployment salt.

    ``ENCRYPTION_SALT`` is a hex string so it survives an env var round-trip
    intact. It must stay stable for the life of the stored data.
    """
    raw = settings.ENCRYPTION_SALT or os.getenv('ENCRYPTION_SALT')
    if not raw:
        raise CredentialEncryptionError(
            "ENCRYPTION_SALT is not configured. Generate one with "
            "`python -c \"import secrets; print(secrets.token_hex(16))\"`."
        )
    try:
        return bytes.fromhex(raw)
    except ValueError:
        # Accept a non-hex value rather than failing a deployment that already
        # stored data under it; the bytes just have to be reproducible.
        return raw.encode()


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
            self._encryption_key = derive_key(
                secret=_require_secret(),
                salt=_require_salt(),
            )
            logger.info("Credential encryption key derived successfully")
            return self._encryption_key

        except CredentialEncryptionError:
            raise
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
