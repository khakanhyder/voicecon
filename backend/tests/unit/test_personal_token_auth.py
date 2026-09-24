"""An OAuth connector connected with a pasted personal token instead (monday).

monday only issues OAuth tokens to an app installed in the user's account, so
it also takes a personal API token. The connection then holds that token in
``api_key_encrypted`` with no OAuth access token, and the connector has to send
it the way monday expects rather than as an OAuth Bearer token.
"""
from types import SimpleNamespace

import pytest

from app.services.integrations.connector_base import BaseConnector


class _Connector(BaseConnector):
    async def test_connection(self):  # pragma: no cover - not exercised here
        return {"success": True, "message": "", "details": {}}


class _PlainCredentials:
    """Stands in for the credential manager: the 'ciphertext' is the value."""

    def decrypt(self, value):
        return value


def _make(slug="monday", api_key=None, access_token=None, auth_type="oauth2"):
    connector = SimpleNamespace(
        slug=slug,
        base_url="https://api.monday.com",
        auth_type=auth_type,
        auth_config={},
        rate_limit_per_minute=None,
        rate_limit_per_hour=None,
        rate_limit_per_day=None,
    )
    connection = SimpleNamespace(
        id=None,
        config={},
        api_key_encrypted=api_key,
        access_token_encrypted=access_token,
        token_expires_at=None,
    )
    instance = _Connector(connection=connection, connector=connector, db=None)
    instance.credential_manager = _PlainCredentials()
    return instance


class TestPersonalToken:
    def test_personal_token_is_sent_bare(self):
        connector = _make(api_key="tok")
        assert connector.uses_personal_token()
        assert connector.get_auth_headers("tok") == {"Authorization": "tok"}

    @pytest.mark.asyncio
    async def test_access_token_comes_from_the_api_key_column(self):
        assert await _make(api_key="tok").get_access_token() == "tok"

    def test_oauth_connection_keeps_bearer(self):
        connector = _make(access_token="oauth")
        assert not connector.uses_personal_token()
        assert connector.get_auth_headers("oauth") == {"Authorization": "Bearer oauth"}

    def test_oauth_token_wins_if_both_are_present(self):
        # Connecting one way clears the other, but never trust a stale pair
        # to pick the personal token over a live OAuth grant.
        assert not _make(api_key="tok", access_token="oauth").uses_personal_token()

    def test_other_oauth_connectors_take_no_personal_token(self):
        assert not _make(slug="hubspot", api_key="tok").uses_personal_token()

    @pytest.mark.asyncio
    async def test_personal_token_is_never_refreshed(self):
        # refresh_token would otherwise call the OAuth token endpoint with no
        # refresh token and fail the request.
        await _make(api_key="tok").refresh_token()
