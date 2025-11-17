"""
Integrations Services Package.

Exports integration services for external imports.
"""
from app.services.integrations.credential_manager import (
    get_credential_manager,
    CredentialManager,
    CredentialEncryptionError,
    CredentialDecryptionError,
)
from app.services.integrations.oauth_handler import (
    get_oauth_handler,
    OAuth2Handler,
    OAuth2Error,
)
from app.services.integrations.integration_manager import (
    get_integration_manager,
    IntegrationManager,
    IntegrationError,
    ConnectionTestError,
)

__all__ = [
    "get_credential_manager",
    "CredentialManager",
    "CredentialEncryptionError",
    "CredentialDecryptionError",
    "get_oauth_handler",
    "OAuth2Handler",
    "OAuth2Error",
    "get_integration_manager",
    "IntegrationManager",
    "IntegrationError",
    "ConnectionTestError",
]
