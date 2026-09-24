"""
Base Connector Class.

Abstract base class for all integration connectors.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import IntegrationConnector, IntegrationConnection, IntegrationLog
from app.services.integrations.credential_manager import get_credential_manager
from app.services.integrations.http_client import (
    IntegrationHTTPClient,
    RateLimiter,
    RetryConfig,
    HTTPRequestError,
)

logger = logging.getLogger(__name__)

#: Longest a connection's bookkeeping (last used, error count, request log) may
#: wait. It is best-effort and must never hold up the action it describes.
BOOKKEEPING_TIMEOUT = 3.0


class ConnectorError(Exception):
    """Raised when connector operation fails."""
    pass


def resolve_base_url(
    connector: IntegrationConnector,
    connection: Optional[IntegrationConnection] = None,
) -> Optional[str]:
    """The API host to talk to for this particular connection.

    Most providers have one host for everybody and the connector row's
    ``base_url`` is the whole answer. A few are tenant-scoped and cannot be:

    * **Supabase** — every project has its own ``https://<ref>.supabase.co``.
      The seeded row is the literal placeholder ``https://your-project.supabase.co``,
      so without an override every Supabase call resolves to a host that does
      not exist.
    * **Azure Blob** — ``https://<account>.blob.core.windows.net``.
    * **Make**, **Zendesk** — region- and subdomain-scoped hooks.

    The override lives on ``connection.config["base_url"]``, written by the
    setup form, and is read here rather than at each call site so that the
    connector, the connection test and the OAuth flow cannot disagree about
    where the requests are going.
    """
    config = getattr(connection, "config", None) or {}
    override = config.get("base_url")
    if isinstance(override, str) and override.strip():
        return override.strip().rstrip("/")
    return connector.base_url


class BaseConnector(ABC):
    """
    Abstract base class for integration connectors.

    All connectors must inherit from this class and implement required methods.

    Features:
    - Automatic authentication handling
    - Rate limiting
    - Request/response logging
    - Error handling with retries
    - Token refresh (for OAuth2)
    """

    def __init__(
        self,
        connection: IntegrationConnection,
        connector: IntegrationConnector,
        db: AsyncSession,
    ):
        """
        Initialize connector.

        Args:
            connection: Integration connection
            connector: Integration connector configuration
            db: Database session
        """
        self.connection = connection
        self.connector = connector
        self.db = db

        # Services
        self.credential_manager = get_credential_manager()

        # HTTP client with rate limiting
        rate_limiter = self._create_rate_limiter()
        retry_config = RetryConfig(max_retries=3)

        self.http_client = IntegrationHTTPClient(
            base_url=resolve_base_url(connector, connection),
            rate_limiter=rate_limiter,
            retry_config=retry_config,
        )

    def _create_rate_limiter(self) -> Optional[RateLimiter]:
        """
        Create rate limiter from connector configuration.

        Returns:
            RateLimiter instance or None
        """
        auth_config = self.connector.auth_config or {}

        requests_per_minute = auth_config.get("rate_limit_per_minute") or self.connector.rate_limit_per_minute
        requests_per_hour = auth_config.get("rate_limit_per_hour") or self.connector.rate_limit_per_hour
        requests_per_day = auth_config.get("rate_limit_per_day") or self.connector.rate_limit_per_day

        if not any([requests_per_minute, requests_per_hour, requests_per_day]):
            return None

        return RateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            requests_per_day=requests_per_day,
        )

    async def get_access_token(self) -> str:
        """
        Get access token for requests.

        Handles token refresh if needed (for OAuth2).

        Returns:
            Access token

        Raises:
            ConnectorError: If token cannot be retrieved
        """
        try:
            # An OAuth connector connected with a pasted personal token instead
            if self.uses_personal_token():
                return self.credential_manager.decrypt(
                    self.connection.api_key_encrypted
                )

            # Check if OAuth2
            if self.connector.auth_type == "oauth2":
                # Check if token expired
                if self.connection.token_expires_at:
                    if datetime.utcnow() >= self.connection.token_expires_at:
                        # Token expired, need to refresh
                        logger.info(f"Token expired for connection {self.connection.id}, refreshing...")
                        await self.refresh_token()

                # Decrypt and return access token
                if not self.connection.access_token_encrypted:
                    raise ConnectorError("No access token available")

                return self.credential_manager.decrypt(
                    self.connection.access_token_encrypted
                )

            # API key auth
            elif self.connector.auth_type == "api_key":
                if not self.connection.api_key_encrypted:
                    raise ConnectorError("No API key available")

                return self.credential_manager.decrypt(
                    self.connection.api_key_encrypted
                )

            else:
                raise ConnectorError(f"Unsupported auth type: {self.connector.auth_type}")

        except Exception as e:
            logger.error(f"Failed to get access token: {e}", exc_info=True)
            raise ConnectorError(f"Failed to get access token: {str(e)}")

    def uses_personal_token(self) -> bool:
        """True for an OAuth connector connected with a personal token instead.

        Such a connection holds the token in ``api_key_encrypted`` and has no
        OAuth access token; connecting one way clears the other's credentials.
        """
        if self.connector.auth_type != "oauth2":
            return False
        if not getattr(self.connection, "api_key_encrypted", None):
            return False
        if getattr(self.connection, "access_token_encrypted", None):
            return False
        from app.services.integrations.oauth_providers import personal_token_config

        return personal_token_config(self.connector.slug) is not None

    def get_auth_data(self) -> Dict[str, Any]:
        """
        Return the connection's decrypted additional auth fields (the
        `additional_fields` supplied at connect time), or {} if none.

        Used by connectors that need more than a single credential — e.g.
        WhatsApp stores its phone_number_id alongside the access token.
        """
        if not getattr(self.connection, "auth_data_encrypted", None):
            return {}
        try:
            return self.credential_manager.decrypt_dict(self.connection.auth_data_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt auth data: {e}")
            return {}

    async def refresh_token(self) -> None:
        """
        Refresh OAuth2 access token.

        Only applicable for OAuth2 connections.

        Raises:
            ConnectorError: If token refresh fails
        """
        if self.connector.auth_type != "oauth2" or self.uses_personal_token():
            return

        try:
            from app.services.integrations.integration_manager import get_integration_manager

            manager = get_integration_manager()

            await manager.refresh_token(
                connection=self.connection,
                connector=self.connector,
                db=self.db,
            )

            # Refresh connection from database
            await self.db.refresh(self.connection)

            logger.info(f"Token refreshed for connection {self.connection.id}")

        except Exception as e:
            logger.error(f"Failed to refresh token: {e}", exc_info=True)
            raise ConnectorError(f"Failed to refresh token: {str(e)}")

    def get_auth_headers(self, access_token: str) -> Dict[str, str]:
        """
        Build authentication headers.

        Args:
            access_token: Access token

        Returns:
            Headers dictionary
        """
        auth_config = self.connector.auth_config or {}

        if self.uses_personal_token():
            from app.services.integrations.oauth_providers import personal_token_config

            token_cfg = personal_token_config(self.connector.slug) or {}
            return {
                token_cfg.get("header", "Authorization"):
                    token_cfg.get("format", "Bearer {token}").format(token=access_token)
            }

        # OAuth2 / Bearer token
        if self.connector.auth_type == "oauth2":
            return {"Authorization": f"Bearer {access_token}"}

        # API Key
        elif self.connector.auth_type == "api_key":
            api_key_location = auth_config.get("api_key_location", "header")
            api_key_name = auth_config.get("api_key_name", "X-API-Key")
            api_key_format = auth_config.get("api_key_format", "{api_key}")

            if api_key_location == "header":
                return {api_key_name: api_key_format.format(api_key=access_token)}

        return {}

    def get_auth_params(self, access_token: str) -> Dict[str, Any]:
        """Credentials that belong in the query string rather than a header.

        Cal.com and Vonage authenticate with ``?apiKey=`` / ``?api_key=``, and
        their seed rows say so via ``api_key_location: "query"``. Until this
        existed, ``get_auth_headers`` returned ``{}`` for them and nothing else
        picked the credential up, so every request went out anonymous.

        What made that hard to see: ``IntegrationManager.test_connection``
        builds its own request and *does* honour ``api_key_location``. So the
        connection tested green, the UI showed Connected, and only the actual
        actions 401'd. Both paths now derive the credential the same way.

        Args:
            access_token: Decrypted API key or access token.

        Returns:
            Query parameters to merge into the request, or ``{}``.
        """
        if self.connector.auth_type != "api_key":
            return {}

        auth_config = self.connector.auth_config or {}
        if auth_config.get("api_key_location") != "query":
            return {}

        api_key_name = auth_config.get("api_key_name", "api_key")
        api_key_format = auth_config.get("api_key_format", "{api_key}")
        return {api_key_name: api_key_format.format(api_key=access_token)}

    async def make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated API request with logging.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            json: JSON body
            data: Form data
            headers: Additional headers

        Returns:
            Response data

        Raises:
            ConnectorError: If request fails
        """
        import time

        try:
            # Get access token
            access_token = await self.get_access_token()

            # Build headers
            request_headers = self.get_auth_headers(access_token)

            # Add additional headers
            if headers:
                request_headers.update(headers)

            # Query-string credentials, for providers that authenticate that
            # way. An explicit caller parameter wins — Vonage's connector
            # passes api_key/api_secret itself, and that call should not be
            # silently rewritten underneath it.
            auth_params = self.get_auth_params(access_token)
            if auth_params:
                params = {**auth_params, **(params or {})}

            # Make request
            start_time = time.time()

            response_data = await self.http_client.request(
                method=method,
                endpoint=endpoint,
                headers=request_headers,
                params=params,
                json=json,
                data=data,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # Log successful request
            await self._log_request(
                method=method,
                endpoint=endpoint,
                request_headers=request_headers,
                request_body=json or data,
                status_code=200,
                response_body=response_data,
                duration_ms=duration_ms,
                success=True,
            )

            # Record that the connection was used. Best-effort bookkeeping:
            # it must never be able to fail a request that already succeeded.
            #
            # It could, and did. This block wrote `usage_count` and
            # `last_used_at`, neither of which exists on IntegrationConnection
            # (they are ApiKey columns), so every call raised AttributeError
            # *after* the provider had already answered. It stayed hidden
            # because the guard below skips the connect flow, whose connection
            # is still transient — so connecting worked and everything
            # afterwards failed, which reads exactly like a bad credential.
            await self._record_connection_state(last_sync_at=datetime.utcnow())

            return response_data

        except HTTPRequestError as e:
            # Log failed request
            await self._log_request(
                method=method,
                endpoint=endpoint,
                request_headers=headers or {},
                request_body=json or data,
                status_code=None,
                response_body=None,
                duration_ms=None,
                success=False,
                error_message=str(e),
            )

            # Update connection error count (persisted connections only)
            await self._record_connection_state(
                error_count=(getattr(self.connection, "error_count", None) or 0) + 1,
                last_error=str(e)[:2000],
            )

            logger.error(f"Request failed: {e}", exc_info=True)
            raise ConnectorError(f"Request failed: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error in make_request: {e}", exc_info=True)
            raise ConnectorError(f"Request failed: {str(e)}")

    async def _log_request(
        self,
        method: str,
        endpoint: str,
        request_headers: Dict[str, str],
        request_body: Optional[Dict[str, Any]],
        status_code: Optional[int],
        response_body: Optional[Dict[str, Any]],
        duration_ms: Optional[int],
        success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Log API request to database.

        Args:
            method: HTTP method
            endpoint: API endpoint
            request_headers: Request headers
            request_body: Request body
            status_code: Response status code
            response_body: Response body
            duration_ms: Request duration in milliseconds
            success: Whether request succeeded
            error_message: Error message if failed
        """
        # Skip logging for transient (unsaved) connections — the connect flow
        # validates a connection before it has an id.
        if getattr(self.connection, "id", None) is None:
            return
        try:
            # Remove sensitive headers
            safe_headers = {
                k: v if k.lower() not in ["authorization", "x-api-key"] else "***"
                for k, v in request_headers.items()
            }

            # Truncate large bodies
            safe_request_body = request_body
            if request_body and len(str(request_body)) > 5000:
                safe_request_body = {"_truncated": True, "size": len(str(request_body))}

            safe_response_body = response_body
            if response_body and len(str(response_body)) > 5000:
                safe_response_body = {"_truncated": True, "size": len(str(response_body))}

            log = IntegrationLog(
                connection_id=self.connection.id,
                method=method,
                endpoint=endpoint,
                request_headers=safe_headers,
                request_body=safe_request_body,
                status_code=status_code,
                response_body=safe_response_body,
                duration_ms=duration_ms,
                success=success,
                error_message=error_message,
            )

            async def add_log(side) -> None:
                side.add(log)

            await self._bookkeeping(add_log, what="log the request")
        except Exception as e:
            logger.error(f"Failed to log request: {e}", exc_info=True)

    # ------------------------------------------------------------ bookkeeping
    #
    # "Last used", the error count and the request log are written in a short
    # session of their own, with a lock timeout and an overall time limit.
    #
    # They used to go through the caller's session: set the attribute, commit.
    # That made every action wait on the connection's row. When any other
    # transaction held that row (a call whose session had not finished, or a
    # commit that failed and was never rolled back, leaving its lock in place),
    # the next action on the same connection hung indefinitely. The request to
    # the provider had already returned; the hang was the UPDATE behind it. It
    # looked like "Google Sheets is broken" while Calendar, a different row,
    # kept working. Losing a "last used" timestamp is harmless; hanging a call
    # is not.

    def _bind(self):
        return getattr(self.db, "bind", None) if self.db is not None else None

    async def _bookkeeping(self, apply, what: str) -> None:
        """Run ``apply(side_session)`` and commit it, never blocking the caller."""
        bind = self._bind()
        if bind is None:
            return
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession

        async def write() -> None:
            async with _AsyncSession(bind=bind, expire_on_commit=False) as side:
                if bind.dialect.name == "postgresql":
                    await side.execute(text("SET LOCAL lock_timeout = '2s'"))
                await apply(side)
                await side.commit()

        try:
            await asyncio.wait_for(write(), timeout=BOOKKEEPING_TIMEOUT)
        except Exception as exc:  # noqa: BLE001 - bookkeeping is best-effort
            logger.warning(
                f"Skipped: could not {what} for connection "
                f"{getattr(self.connection, 'id', None)}: {exc!r}"
            )

    async def _record_connection_state(self, **fields: Any) -> None:
        """Save "last used" / error details on the connection, best-effort."""
        connection_id = getattr(self.connection, "id", None)
        if connection_id is None:
            return  # the connect flow validates a connection before it is saved
        from sqlalchemy import update
        from sqlalchemy.orm.attributes import set_committed_value

        async def apply(side) -> None:
            await side.execute(
                update(IntegrationConnection)
                .where(IntegrationConnection.id == connection_id)
                .values(**fields)
            )

        await self._bookkeeping(apply, what="record connection use")
        # Keep the caller's copy in step without marking it dirty, so its own
        # next commit does not write (and wait on) the same row again.
        for key, value in fields.items():
            try:
                set_committed_value(self.connection, key, value)
            except Exception:  # noqa: BLE001 - transient/unmapped objects
                pass

    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to integration.

        Must be implemented by subclasses.

        Returns:
            Test result dictionary with:
            - success: bool
            - message: str
            - details: dict
        """
        pass

    async def close(self):
        """Close HTTP client."""
        await self.http_client.close()

    # Convenience methods for common HTTP operations
    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make GET request."""
        return await self.make_request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make POST request."""
        return await self.make_request("POST", endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make PUT request."""
        return await self.make_request("PUT", endpoint, **kwargs)

    async def patch(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make PATCH request."""
        return await self.make_request("PATCH", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make DELETE request."""
        return await self.make_request("DELETE", endpoint, **kwargs)
