"""
Integration Manager Service.

Manages integration connections, authentication, and operations.
"""
import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import httpx

from app.models.integration import (
    IntegrationConnector,
    IntegrationConnection,
    IntegrationLog,
)
from app.services.integrations.credential_manager import get_credential_manager
from app.services.integrations.oauth_handler import get_oauth_handler, OAuth2Error

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    """Raised when integration operation fails."""
    pass


class ConnectionTestError(Exception):
    """Raised when connection test fails."""
    pass


def _normalize_base_url(value: str) -> str:
    """Make a host someone typed into a setup form usable as a base URL.

    People paste "my-project.supabase.co", "https://my-project.supabase.co/"
    and everything in between. Left alone, the first becomes a relative URL and
    the last double-slashes every endpoint.
    """
    host = (value or "").strip().rstrip("/")
    if host and not host.startswith(("http://", "https://")):
        host = f"https://{host}"
    return host


class IntegrationManager:
    """
    Manages integration connections and operations.

    Features:
    - Connect/disconnect integrations
    - OAuth2 flow handling
    - Credential encryption
    - Connection testing
    - Token refresh automation
    - API call logging
    """

    def __init__(self):
        """Initialize integration manager."""
        self.credential_manager = get_credential_manager()
        self.oauth_handler = get_oauth_handler()
        self.http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                follow_redirects=True
            )
        return self.http_client

    async def close(self):
        """Close HTTP client."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

    async def initiate_oauth_flow(
        self,
        connector: IntegrationConnector,
        user_id: str,
        redirect_uri: str,
        scopes: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        Initiate OAuth2 authorization flow.

        Args:
            connector: Integration connector
            user_id: User ID
            redirect_uri: OAuth callback redirect URI
            scopes: List of OAuth scopes to request

        Returns:
            Dictionary with authorization_url and state

        Raises:
            IntegrationError: If OAuth flow initiation fails
        """
        try:
            # Verify connector uses OAuth2
            if connector.auth_type != "oauth2":
                raise IntegrationError(f"Connector {connector.name} does not use OAuth2")

            # Resolve OAuth config from the provider registry (public endpoints)
            # + environment (client credentials).
            from app.services.integrations.oauth_providers import resolve_client_credentials
            oauth = resolve_client_credentials(connector.slug, connector.auth_config)
            authorize_url = oauth["authorize_url"] or connector.base_url
            client_id = oauth["client_id"]

            if not client_id:
                raise IntegrationError(
                    f"{connector.name} is not configured for OAuth on this server. "
                    f"The administrator must register an OAuth app and set the client "
                    f"credentials (see the integration setup docs)."
                )
            if not authorize_url:
                raise IntegrationError(f"No authorize URL configured for {connector.name}")

            # Generate state
            state = self.oauth_handler.generate_state(
                connector_id=str(connector.id),
                user_id=user_id
            )

            # Use the requested scopes, else the provider's defaults.
            if not scopes:
                scopes = oauth["scopes"]

            # Build authorization URL (provider-specific extra params, e.g. Google
            # access_type=offline for refresh tokens).
            authorization_url = self.oauth_handler.build_authorization_url(
                authorize_url=authorize_url,
                client_id=client_id,
                redirect_uri=redirect_uri,
                state=state,
                scopes=scopes,
                additional_params=oauth.get("authorize_params") or None,
            )

            logger.info(f"OAuth flow initiated for connector: {connector.name}")

            return {
                "authorization_url": authorization_url,
                "state": state,
            }

        except Exception as e:
            logger.error(f"Failed to initiate OAuth flow: {e}", exc_info=True)
            raise IntegrationError(f"Failed to initiate OAuth flow: {str(e)}")

    async def complete_oauth_flow(
        self,
        connector: IntegrationConnector,
        code: str,
        state: str,
        redirect_uri: str,
        user_id: str,
        organization_id: str,
        db: AsyncSession,
        connection_name: Optional[str] = None,
    ) -> IntegrationConnection:
        """
        Complete OAuth2 authorization flow.

        Args:
            connector: Integration connector
            code: Authorization code from OAuth callback
            state: State parameter for verification
            redirect_uri: OAuth callback redirect URI
            user_id: User ID
            organization_id: Organization ID
            db: Database session
            connection_name: Optional connection name

        Returns:
            Created IntegrationConnection

        Raises:
            IntegrationError: If OAuth completion fails
        """
        try:
            # Verify state
            is_valid, state_data = self.oauth_handler.verify_state(state)
            if not is_valid or not state_data:
                raise IntegrationError("Invalid or expired state parameter")

            # Verify connector ID matches
            if state_data["connector_id"] != str(connector.id):
                raise IntegrationError("Connector ID mismatch")

            # Verify user ID matches
            if state_data["user_id"] != user_id:
                raise IntegrationError("User ID mismatch")

            # Resolve OAuth config (registry endpoints + env credentials).
            from app.services.integrations.oauth_providers import resolve_client_credentials
            oauth = resolve_client_credentials(connector.slug, connector.auth_config)
            token_url = oauth["token_url"]
            client_id = oauth["client_id"]
            client_secret = oauth["client_secret"]

            if not token_url or not client_id or not client_secret:
                raise IntegrationError(
                    f"{connector.name} OAuth is not fully configured on this server "
                    f"(missing client credentials or token URL)."
                )

            # Exchange code for tokens
            token_data = await self.oauth_handler.exchange_code_for_token(
                token_url=token_url,
                client_id=client_id,
                client_secret=client_secret,
                code=code,
                redirect_uri=redirect_uri,
                style=oauth.get("token_style", "form"),
            )

            # Extract tokens
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")

            if not access_token:
                raise IntegrationError("No access token in response")

            # Encrypt tokens
            encrypted_tokens = self.credential_manager.encrypt_oauth_tokens(
                access_token=access_token,
                refresh_token=refresh_token,
            )

            # Calculate token expiry
            token_expires_at = self.oauth_handler.calculate_token_expiry(expires_in)

            # Create connection
            connection = IntegrationConnection(
                user_id=user_id,
                organization_id=organization_id,
                connector_id=connector.id,
                name=connection_name or f"{connector.name} Connection",
                status="active",
                access_token_encrypted=encrypted_tokens["access_token_encrypted"],
                refresh_token_encrypted=encrypted_tokens.get("refresh_token_encrypted"),
                token_expires_at=token_expires_at,
                integration_metadata={"token_type": token_data.get("token_type", "Bearer")},
            )

            db.add(connection)
            await db.commit()
            await db.refresh(connection)

            logger.info(f"OAuth flow completed for connector: {connector.name}")

            return connection

        except OAuth2Error as e:
            logger.error(f"OAuth2 error: {e}", exc_info=True)
            raise IntegrationError(f"OAuth2 error: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to complete OAuth flow: {e}", exc_info=True)
            raise IntegrationError(f"Failed to complete OAuth flow: {str(e)}")

    async def connect_with_api_key(
        self,
        connector: IntegrationConnector,
        api_key: str,
        user_id: str,
        organization_id: str,
        db: AsyncSession,
        additional_fields: Optional[Dict[str, str]] = None,
        connection_name: Optional[str] = None,
    ) -> IntegrationConnection:
        """
        Create connection with API key authentication.

        Args:
            connector: Integration connector
            api_key: API key
            user_id: User ID
            organization_id: Organization ID
            db: Database session
            additional_fields: Additional authentication fields
            connection_name: Optional connection name

        Returns:
            Created IntegrationConnection

        Raises:
            IntegrationError: If connection creation fails
        """
        try:
            # Verify connector uses API key auth
            if connector.auth_type != "api_key":
                raise IntegrationError(f"Connector {connector.name} does not use API key auth")

            # Encrypt API key
            encrypted_api_key = self.credential_manager.encrypt(api_key)

            # Encrypt additional fields if provided
            encrypted_auth_data = None
            if additional_fields:
                encrypted_auth_data = self.credential_manager.encrypt_dict(additional_fields)

            # Tenant-scoped providers carry their host in a setup field rather
            # than in the shared connector row — Supabase's "Project URL" is
            # the whole reason the seeded base_url is a placeholder. Which
            # field that is comes from the connector's own auth_config, so this
            # stays data-driven instead of a slug switch here.
            config = {}
            base_url_field = (connector.auth_config or {}).get("base_url_field")
            supplied_host = (additional_fields or {}).get(base_url_field or "base_url")
            if supplied_host:
                config["base_url"] = _normalize_base_url(supplied_host)

            # Create connection
            connection = IntegrationConnection(
                user_id=user_id,
                organization_id=organization_id,
                connector_id=connector.id,
                name=connection_name or f"{connector.name} Connection",
                status="pending",  # Will be "active" after test
                api_key_encrypted=encrypted_api_key,
                auth_data_encrypted=encrypted_auth_data,
                config=config,
            )

            # Test connection before saving
            test_result = await self.test_connection(connection, connector, db=db)

            if not test_result["success"]:
                raise ConnectionTestError(f"Connection test failed: {test_result['message']}")

            connection.status = "active"
            connection.last_sync_at = datetime.utcnow()

            db.add(connection)
            await db.commit()
            await db.refresh(connection)

            logger.info(f"API key connection created for connector: {connector.name}")

            return connection

        except ConnectionTestError:
            raise

        except Exception as e:
            logger.error(f"Failed to create API key connection: {e}", exc_info=True)
            raise IntegrationError(f"Failed to create API key connection: {str(e)}")

    async def test_connection(
        self,
        connection: IntegrationConnection,
        connector: IntegrationConnector,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Test integration connection.

        Prefers the connector's own ``test_connection`` when there is a
        connector class for the slug, and only falls back to a generic HTTP GET
        against ``test_endpoint`` when there is not.

        The generic probe assumes the integration is a REST API reachable at
        ``base_url + test_endpoint`` with the credential in a header. That is
        true for most connectors and false for a growing number: object storage
        authenticates with a per-request SigV4 signature, SMTP is not HTTP at
        all, and a webhook has no endpoint to GET. For those the generic probe
        cannot do anything but fail, which would make every one of them
        impossible to connect.

        It is also the more honest test for the REST connectors: the connector's
        own method exercises the same auth path its actions use, which is the
        specific thing that was silently diverging for Cal.com.

        Args:
            connection: Integration connection
            connector: Integration connector
            db: Session, needed to instantiate a connector class

        Returns:
            Test result dictionary
        """
        import time

        start_time = time.time()

        connector_test = await self._connector_self_test(connection, connector, db)
        if connector_test is not None:
            connector_test.setdefault(
                "response_time_ms", int((time.time() - start_time) * 1000)
            )
            return connector_test

        try:

            # Get test endpoint from auth_config
            auth_config = connector.auth_config or {}
            test_endpoint = auth_config.get("test_endpoint", "/user")

            # Build full URL. Same resolution the connector itself uses, so a
            # tenant-scoped host (Supabase project, Azure account) is tested
            # against the host the actions will actually call.
            from app.services.integrations.connector_base import resolve_base_url

            base_url = resolve_base_url(connector, connection)
            if not base_url:
                return {
                    "success": False,
                    "message": "No base URL configured for connector",
                    "response_time_ms": 0,
                }

            test_url = f"{base_url.rstrip('/')}/{test_endpoint.lstrip('/')}"

            # Get credentials
            headers = {}
            params = {}

            if connection.access_token_encrypted:
                # OAuth2
                access_token = self.credential_manager.decrypt(connection.access_token_encrypted)
                headers["Authorization"] = f"Bearer {access_token}"

            elif connection.api_key_encrypted:
                # API Key
                api_key = self.credential_manager.decrypt(connection.api_key_encrypted)

                # Check where to put API key (header, query, etc.)
                api_key_location = auth_config.get("api_key_location", "header")
                api_key_name = auth_config.get("api_key_name", "X-API-Key")

                # Many providers need the credential wrapped in a scheme —
                # "Basic {api_key}" for Twilio, "Bearer {api_key}" for Telnyx.
                # Sending the bare key makes the header unparseable, so the test
                # fails even when the credential is valid. This mirrors
                # BaseConnector.get_auth_headers so a connection that tests
                # green also works for real API calls.
                api_key_format = auth_config.get("api_key_format", "{api_key}")
                formatted_key = api_key_format.format(api_key=api_key)

                if api_key_location == "query":
                    params[api_key_name] = formatted_key
                else:
                    headers[api_key_name] = formatted_key

            # Make test request
            client = await self._get_http_client()

            response = await client.get(test_url, headers=headers, params=params or None)

            response_time_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Connection test successful",
                    "response_time_ms": response_time_ms,
                    "details": {"status_code": response.status_code},
                }
            else:
                return {
                    "success": False,
                    "message": f"Connection test failed with status {response.status_code}",
                    "response_time_ms": response_time_ms,
                    "details": {
                        "status_code": response.status_code,
                        "response": response.text[:500],
                    },
                }

        except Exception as e:
            logger.error(f"Connection test error: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Connection test error: {str(e)}",
                "response_time_ms": 0,
                "details": {"error": str(e)},
            }

    async def _connector_self_test(
        self,
        connection: IntegrationConnection,
        connector: IntegrationConnector,
        db: Optional[AsyncSession],
    ) -> Optional[Dict[str, Any]]:
        """Run the connector class's own test, or return None if there isn't one.

        Returning None rather than raising is deliberate: a slug with no
        connector class is a normal state (the row is seeded before the class
        exists), and the caller should quietly fall through to the generic
        probe rather than treat it as a failure.
        """
        from app.services.integrations import connectors as connector_module
        from app.services.integrations.action_registry import CONNECTOR_CLASS_MAP

        class_name = CONNECTOR_CLASS_MAP.get(connector.slug)
        if not class_name or db is None:
            return None

        connector_class = getattr(connector_module, class_name, None)
        if connector_class is None:
            return None

        instance = connector_class(connection=connection, connector=connector, db=db)
        try:
            result = await instance.test_connection()
        except Exception as exc:  # noqa: BLE001 - connectors raise their own types
            logger.warning(f"{connector.slug} self-test raised: {exc}")
            return {
                "success": False,
                "message": f"Connection test failed: {exc}",
                "details": {},
            }
        finally:
            # Every connector opens an HTTP client in __init__ whether or not
            # it ends up using it; not closing leaks a connection pool per
            # connection attempt.
            try:
                await instance.close()
            except Exception:  # noqa: BLE001
                pass

        if not isinstance(result, dict):
            return None
        result.setdefault("success", False)
        result.setdefault("message", "")
        result.setdefault("details", {})
        return result

    async def refresh_token(
        self,
        connection: IntegrationConnection,
        connector: IntegrationConnector,
        db: AsyncSession,
    ) -> bool:
        """
        Refresh OAuth2 access token.

        Args:
            connection: Integration connection
            connector: Integration connector
            db: Database session

        Returns:
            True if refresh successful

        Raises:
            IntegrationError: If token refresh fails
        """
        try:
            # Verify OAuth2
            if connector.auth_type != "oauth2":
                raise IntegrationError("Only OAuth2 connections can be refreshed")

            if not connection.refresh_token_encrypted:
                raise IntegrationError("No refresh token available")

            # Resolve OAuth config (registry endpoints + env credentials).
            from app.services.integrations.oauth_providers import resolve_client_credentials
            oauth = resolve_client_credentials(connector.slug, connector.auth_config)
            token_url = oauth["token_url"]
            client_id = oauth["client_id"]
            client_secret = oauth["client_secret"]

            if not token_url or not client_id or not client_secret:
                raise IntegrationError(
                    f"{connector.name} OAuth is not fully configured on this server "
                    f"(missing client credentials or token URL)."
                )

            # Decrypt refresh token
            refresh_token = self.credential_manager.decrypt(connection.refresh_token_encrypted)

            # Refresh tokens
            token_data = await self.oauth_handler.refresh_access_token(
                token_url=token_url,
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
                style=oauth.get("token_style", "form"),
            )

            # Extract new tokens
            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token", refresh_token)  # Use old if not provided
            expires_in = token_data.get("expires_in")

            # Encrypt new tokens
            encrypted_tokens = self.credential_manager.encrypt_oauth_tokens(
                access_token=new_access_token,
                refresh_token=new_refresh_token,
            )

            # Calculate new expiry
            token_expires_at = self.oauth_handler.calculate_token_expiry(expires_in)

            # Update connection
            connection.access_token_encrypted = encrypted_tokens["access_token_encrypted"]
            connection.refresh_token_encrypted = encrypted_tokens.get("refresh_token_encrypted")
            connection.token_expires_at = token_expires_at
            connection.updated_at = datetime.utcnow()

            await db.commit()

            logger.info(f"Token refreshed for connection: {connection.id}")

            return True

        except OAuth2Error as e:
            logger.error(f"OAuth2 error during refresh: {e}", exc_info=True)
            raise IntegrationError(f"Token refresh failed: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to refresh token: {e}", exc_info=True)
            raise IntegrationError(f"Token refresh failed: {str(e)}")

    async def disconnect_integration(
        self,
        connection: IntegrationConnection,
        db: AsyncSession,
    ) -> None:
        """
        Disconnect integration.

        Args:
            connection: Integration connection
            db: Database session
        """
        connection.status = "disconnected"
        connection.is_active = False
        connection.updated_at = datetime.utcnow()

        await db.commit()

        logger.info(f"Integration disconnected: {connection.id}")


# Global integration manager instance
_integration_manager: Optional[IntegrationManager] = None


def get_integration_manager() -> IntegrationManager:
    """
    Get global integration manager instance (singleton).

    Returns:
        IntegrationManager instance
    """
    global _integration_manager
    if _integration_manager is None:
        _integration_manager = IntegrationManager()
    return _integration_manager
