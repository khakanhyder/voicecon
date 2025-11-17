"""
OAuth2 Authentication Handler.

Handles OAuth2 authorization flow for integrations.
"""
import logging
import secrets
import time
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import httpx
from urllib.parse import urlencode

from app.services.integrations.credential_manager import get_credential_manager

logger = logging.getLogger(__name__)


class OAuth2Error(Exception):
    """Raised when OAuth2 flow fails."""
    pass


class OAuth2Handler:
    """
    Handles OAuth2 authorization flow.

    Supports:
    - Authorization code flow
    - Token refresh
    - State management for CSRF protection
    """

    def __init__(self):
        """Initialize OAuth2 handler."""
        self.credential_manager = get_credential_manager()
        self.http_client: Optional[httpx.AsyncClient] = None
        self._state_store: Dict[str, Dict[str, Any]] = {}  # In-memory state store

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

    def generate_state(self, connector_id: str, user_id: str) -> str:
        """
        Generate state parameter for OAuth2 flow.

        Args:
            connector_id: Integration connector ID
            user_id: User ID

        Returns:
            State token
        """
        state = secrets.token_urlsafe(32)

        # Store state with metadata (expires in 10 minutes)
        self._state_store[state] = {
            "connector_id": connector_id,
            "user_id": user_id,
            "created_at": time.time(),
            "expires_at": time.time() + 600,  # 10 minutes
        }

        logger.info(f"Generated OAuth2 state: {state[:8]}... for user {user_id}")
        return state

    def verify_state(self, state: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Verify state parameter.

        Args:
            state: State token to verify

        Returns:
            Tuple of (is_valid, state_data)
        """
        state_data = self._state_store.get(state)

        if not state_data:
            logger.warning(f"State not found: {state[:8]}...")
            return False, None

        # Check expiration
        if time.time() > state_data["expires_at"]:
            logger.warning(f"State expired: {state[:8]}...")
            del self._state_store[state]
            return False, None

        # Remove used state
        del self._state_store[state]

        logger.info(f"State verified: {state[:8]}...")
        return True, state_data

    def build_authorization_url(
        self,
        authorize_url: str,
        client_id: str,
        redirect_uri: str,
        state: str,
        scopes: Optional[list] = None,
        additional_params: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Build OAuth2 authorization URL.

        Args:
            authorize_url: OAuth provider's authorization URL
            client_id: OAuth client ID
            redirect_uri: Redirect URI for callback
            state: State parameter for CSRF protection
            scopes: List of OAuth scopes
            additional_params: Additional query parameters

        Returns:
            Authorization URL
        """
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }

        if scopes:
            params["scope"] = " ".join(scopes)

        if additional_params:
            params.update(additional_params)

        url = f"{authorize_url}?{urlencode(params)}"
        logger.info(f"Built authorization URL for client_id: {client_id}")

        return url

    async def exchange_code_for_token(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        additional_params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            token_url: OAuth provider's token URL
            client_id: OAuth client ID
            client_secret: OAuth client secret
            code: Authorization code
            redirect_uri: Redirect URI used in authorization
            additional_params: Additional parameters

        Returns:
            Token response containing access_token, refresh_token, etc.

        Raises:
            OAuth2Error: If token exchange fails
        """
        try:
            client = await self._get_http_client()

            data = {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            }

            if additional_params:
                data.update(additional_params)

            logger.info(f"Exchanging code for token at {token_url}")

            response = await client.post(
                token_url,
                data=data,
                headers={"Accept": "application/json"}
            )

            response.raise_for_status()

            token_data = response.json()

            # Validate response
            if "access_token" not in token_data:
                raise OAuth2Error("No access_token in token response")

            logger.info("Successfully exchanged code for token")
            return token_data

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during token exchange: {e}", exc_info=True)
            raise OAuth2Error(f"Token exchange failed: {str(e)}")

        except Exception as e:
            logger.error(f"Error during token exchange: {e}", exc_info=True)
            raise OAuth2Error(f"Token exchange failed: {str(e)}")

    async def refresh_access_token(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        additional_params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.

        Args:
            token_url: OAuth provider's token URL
            client_id: OAuth client ID
            client_secret: OAuth client secret
            refresh_token: Refresh token
            additional_params: Additional parameters

        Returns:
            Token response with new access_token

        Raises:
            OAuth2Error: If token refresh fails
        """
        try:
            client = await self._get_http_client()

            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            }

            if additional_params:
                data.update(additional_params)

            logger.info(f"Refreshing token at {token_url}")

            response = await client.post(
                token_url,
                data=data,
                headers={"Accept": "application/json"}
            )

            response.raise_for_status()

            token_data = response.json()

            if "access_token" not in token_data:
                raise OAuth2Error("No access_token in refresh response")

            logger.info("Successfully refreshed token")
            return token_data

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during token refresh: {e}", exc_info=True)
            raise OAuth2Error(f"Token refresh failed: {str(e)}")

        except Exception as e:
            logger.error(f"Error during token refresh: {e}", exc_info=True)
            raise OAuth2Error(f"Token refresh failed: {str(e)}")

    def calculate_token_expiry(
        self,
        expires_in: Optional[int] = None
    ) -> Optional[datetime]:
        """
        Calculate token expiry datetime.

        Args:
            expires_in: Seconds until token expires

        Returns:
            Expiry datetime or None
        """
        if expires_in is None:
            return None

        # Subtract 5 minutes buffer to refresh before actual expiry
        buffer_seconds = 300
        expiry_seconds = max(expires_in - buffer_seconds, 0)

        return datetime.utcnow() + timedelta(seconds=expiry_seconds)


# Global OAuth2 handler instance
_oauth_handler: Optional[OAuth2Handler] = None


def get_oauth_handler() -> OAuth2Handler:
    """
    Get global OAuth2 handler instance (singleton).

    Returns:
        OAuth2Handler instance
    """
    global _oauth_handler
    if _oauth_handler is None:
        _oauth_handler = OAuth2Handler()
    return _oauth_handler
