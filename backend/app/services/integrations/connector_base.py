"""
Base Connector Class.

Abstract base class for all integration connectors.
"""
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


class ConnectorError(Exception):
    """Raised when connector operation fails."""
    pass


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
            base_url=connector.base_url,
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
        if self.connector.auth_type != "oauth2":
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

            # Update connection usage (only for persisted connections — the
            # connect flow validates a transient, not-yet-saved connection).
            if getattr(self.connection, "id", None) is not None:
                self.connection.usage_count = (self.connection.usage_count or 0) + 1
                self.connection.last_used_at = datetime.utcnow()
                await self.db.commit()

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
            if getattr(self.connection, "id", None) is not None:
                self.connection.error_count = (self.connection.error_count or 0) + 1
                self.connection.last_error = str(e)
                self.connection.last_error_at = datetime.utcnow()
                await self.db.commit()

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

            self.db.add(log)
            await self.db.commit()

        except Exception as e:
            logger.error(f"Failed to log request: {e}", exc_info=True)

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
