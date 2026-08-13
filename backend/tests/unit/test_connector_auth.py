"""How a connector authenticates and where it sends its requests.

Both behaviours here failed silently in a way that looked like a bad
credential, so they are pinned with tests rather than left to inspection.
"""
from types import SimpleNamespace

import pytest

from app.services.integrations.connector_base import BaseConnector, resolve_base_url


class _Connector(BaseConnector):
    """Concrete subclass — BaseConnector is abstract on test_connection."""

    async def test_connection(self):  # pragma: no cover - not exercised here
        return {"success": True, "message": "", "details": {}}


def _make(auth_type="api_key", auth_config=None, config=None, base_url="https://api.example.com"):
    connector = SimpleNamespace(
        base_url=base_url,
        auth_type=auth_type,
        auth_config=auth_config or {},
        rate_limit_per_minute=None,
        rate_limit_per_hour=None,
        rate_limit_per_day=None,
    )
    connection = SimpleNamespace(id=None, config=config or {})
    return _Connector(connection=connection, connector=connector, db=None)


class TestQueryParameterCredentials:
    """Cal.com and Vonage authenticate with a query parameter, not a header.

    Before ``get_auth_params`` existed, ``get_auth_headers`` returned {} for
    them and no other code path picked the credential up, so every request went
    out unauthenticated. It was invisible because the connection *test* builds
    its own request and did honour api_key_location — so the UI said Connected
    and only the actions 401'd.
    """

    def test_query_credential_is_emitted_as_a_parameter(self):
        connector = _make(
            auth_config={"api_key_location": "query", "api_key_name": "apiKey"}
        )
        assert connector.get_auth_params("secret") == {"apiKey": "secret"}

    def test_query_credential_is_not_also_sent_as_a_header(self):
        connector = _make(
            auth_config={"api_key_location": "query", "api_key_name": "apiKey"}
        )
        assert connector.get_auth_headers("secret") == {}

    def test_header_credential_produces_no_query_parameter(self):
        connector = _make(
            auth_config={
                "api_key_location": "header",
                "api_key_name": "Authorization",
                "api_key_format": "Bearer {api_key}",
            }
        )
        assert connector.get_auth_headers("secret") == {"Authorization": "Bearer secret"}
        assert connector.get_auth_params("secret") == {}

    def test_format_template_is_applied_to_query_credentials_too(self):
        connector = _make(
            auth_config={
                "api_key_location": "query",
                "api_key_name": "token",
                "api_key_format": "tok_{api_key}",
            }
        )
        assert connector.get_auth_params("abc") == {"token": "tok_abc"}

    def test_oauth_connections_never_put_the_token_in_the_url(self):
        connector = _make(
            auth_type="oauth2",
            auth_config={"api_key_location": "query", "api_key_name": "apiKey"},
        )
        assert connector.get_auth_params("token") == {}
        assert connector.get_auth_headers("token") == {"Authorization": "Bearer token"}

    def test_location_defaults_to_header(self):
        connector = _make(auth_config={"api_key_name": "X-API-Key"})
        assert connector.get_auth_params("secret") == {}


class TestBaseUrlResolution:
    """Tenant-scoped providers need a host per connection, not per connector.

    Supabase's seeded row is the literal placeholder
    ``https://your-project.supabase.co``; without an override every call
    resolved to a host that does not exist.
    """

    def test_connection_override_wins_over_the_connector_default(self):
        connector = SimpleNamespace(base_url="https://your-project.supabase.co")
        connection = SimpleNamespace(config={"base_url": "https://real.supabase.co"})
        assert resolve_base_url(connector, connection) == "https://real.supabase.co"

    def test_connector_default_is_used_when_there_is_no_override(self):
        connector = SimpleNamespace(base_url="https://api.example.com")
        connection = SimpleNamespace(config={})
        assert resolve_base_url(connector, connection) == "https://api.example.com"

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_blank_overrides_are_ignored(self, value):
        connector = SimpleNamespace(base_url="https://api.example.com")
        connection = SimpleNamespace(config={"base_url": value})
        assert resolve_base_url(connector, connection) == "https://api.example.com"

    def test_trailing_slash_is_stripped_so_endpoints_do_not_double_up(self):
        connector = SimpleNamespace(base_url="https://api.example.com")
        connection = SimpleNamespace(config={"base_url": "https://real.supabase.co/"})
        assert resolve_base_url(connector, connection) == "https://real.supabase.co"

    def test_missing_connection_falls_back_to_the_connector(self):
        connector = SimpleNamespace(base_url="https://api.example.com")
        assert resolve_base_url(connector, None) == "https://api.example.com"

    def test_the_connector_actually_uses_the_resolved_host(self):
        connector = _make(
            base_url="https://your-project.supabase.co",
            config={"base_url": "https://real.supabase.co"},
        )
        assert connector.http_client.base_url == "https://real.supabase.co"


class TestNormalizeBaseUrl:
    """People paste hosts in whatever form their provider showed them."""

    @pytest.mark.parametrize(
        "supplied,expected",
        [
            ("my-project.supabase.co", "https://my-project.supabase.co"),
            ("https://my-project.supabase.co/", "https://my-project.supabase.co"),
            ("  https://my-project.supabase.co  ", "https://my-project.supabase.co"),
            ("http://localhost:8000/", "http://localhost:8000"),
        ],
    )
    def test_hosts_are_normalized(self, supplied, expected):
        from app.services.integrations.integration_manager import _normalize_base_url

        assert _normalize_base_url(supplied) == expected


class TestCredentialReachesTheRequest:
    """The helper returning the right dict is not the same as the request
    carrying it. This is the assertion that would have caught the Cal.com bug.
    """

    @pytest.fixture
    def captured(self, monkeypatch):
        calls = {}

        async def fake_request(method, endpoint, headers=None, params=None, **kwargs):
            calls.update(
                method=method, endpoint=endpoint, headers=headers, params=params
            )
            return {"ok": True}

        return calls, fake_request

    async def _call(self, connector, captured, **kwargs):
        calls, fake_request = captured
        connector.http_client.request = fake_request
        connector.credential_manager = SimpleNamespace(decrypt=lambda v: "secret")
        connector.connection.api_key_encrypted = "enc"
        connector.connection.access_token_encrypted = None
        await connector.make_request("GET", "/v1/me", **kwargs)
        return calls

    @pytest.mark.asyncio
    async def test_query_credential_is_attached_to_the_outbound_request(self, captured):
        connector = _make(
            auth_config={"api_key_location": "query", "api_key_name": "apiKey"}
        )
        calls = await self._call(connector, captured)
        assert calls["params"] == {"apiKey": "secret"}

    @pytest.mark.asyncio
    async def test_caller_parameters_are_preserved_alongside_the_credential(self, captured):
        connector = _make(
            auth_config={"api_key_location": "query", "api_key_name": "apiKey"}
        )
        calls = await self._call(connector, captured, params={"status": "upcoming"})
        assert calls["params"] == {"apiKey": "secret", "status": "upcoming"}

    @pytest.mark.asyncio
    async def test_an_explicit_caller_credential_is_not_overwritten(self, captured):
        """Vonage's connector passes api_key/api_secret itself; that call must
        not be silently rewritten underneath it."""
        connector = _make(
            auth_config={"api_key_location": "query", "api_key_name": "api_key"}
        )
        calls = await self._call(connector, captured, params={"api_key": "explicit"})
        assert calls["params"]["api_key"] == "explicit"

    @pytest.mark.asyncio
    async def test_header_auth_sends_no_query_parameters(self, captured):
        connector = _make(
            auth_config={
                "api_key_location": "header",
                "api_key_name": "Authorization",
                "api_key_format": "Bearer {api_key}",
            }
        )
        calls = await self._call(connector, captured)
        assert calls["params"] is None
        assert calls["headers"]["Authorization"] == "Bearer secret"


class TestCredentialsAreReadFromWhereTheyLive:
    """Configuration must be read through `env_value`, never bare `os.getenv`.

    Pydantic loads `.env` into the Settings object but never exports it to the
    process environment. Reading credentials with `os.getenv` therefore returned
    None for values that were present and correct in `.env`, and the user was
    told "not configured for OAuth on this server — the administrator must
    register an OAuth app" for an app they had already registered.
    """

    def test_a_value_only_in_settings_is_found(self, monkeypatch):
        from app.core import config

        monkeypatch.delenv("TEST_ONLY_CREDENTIAL", raising=False)
        monkeypatch.setattr(config.settings, "TEST_ONLY_CREDENTIAL", "from-dotenv",
                            raising=False)
        assert config.env_value("TEST_ONLY_CREDENTIAL") == "from-dotenv"

    def test_a_value_only_in_the_process_environment_is_found(self, monkeypatch):
        """Deployments that set real env vars and ship no .env must still work."""
        from app.core import config

        monkeypatch.setenv("TEST_ENV_ONLY_CREDENTIAL", "from-environ")
        assert config.env_value("TEST_ENV_ONLY_CREDENTIAL") == "from-environ"

    def test_an_empty_settings_value_falls_through_to_the_environment(self, monkeypatch):
        """A blank duplicate key in .env must not shadow a real env var."""
        from app.core import config

        monkeypatch.setattr(config.settings, "TEST_BLANK_CREDENTIAL", "", raising=False)
        monkeypatch.setenv("TEST_BLANK_CREDENTIAL", "real-value")
        assert config.env_value("TEST_BLANK_CREDENTIAL") == "real-value"

    def test_a_missing_value_returns_the_default(self):
        from app.core import config

        assert config.env_value("TEST_ABSENT_CREDENTIAL") is None
        assert config.env_value("TEST_ABSENT_CREDENTIAL", "fallback") == "fallback"

    def test_no_credential_lookup_still_uses_bare_os_getenv(self):
        """Guards the fix from being reintroduced elsewhere in the same files."""
        import pathlib

        offenders = []
        for path in (
            "app/services/integrations/oauth_providers.py",
            "app/services/integrations/connectors/trello_connector.py",
        ):
            text = pathlib.Path(path).read_text()
            for line in text.splitlines():
                if "os.getenv(" in line and not line.strip().startswith("#"):
                    offenders.append(f"{path}: {line.strip()}")
        assert not offenders, (
            "Credential lookups must use env_value(), not os.getenv():\n"
            + "\n".join(offenders)
        )
