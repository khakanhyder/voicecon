"""
The four tool types that are one outbound HTTP request underneath.

These were implemented twice — once for a live call, once for the builder's
"Test" button — and the copies drifted. Both call sites now go through
``run_http_tool``, and these tests pin the behaviour that drift broke.
"""
import json

import httpx
import pytest

from app.services.tools.config import ToolConfigError
from app.services.tools.http_tools import (
    HTTP_TOOL_TYPES,
    auth_headers,
    require_safe_url,
    run_http_tool,
)


class Recorder:
    """Captures the request a tool makes, and answers it."""

    def __init__(self, status=200, body='{"ok": true}'):
        self.request: httpx.Request | None = None
        self._status = status
        self._body = body

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.request = request
        return httpx.Response(self._status, text=self._body)


@pytest.fixture
def transport(monkeypatch):
    """Answer every outbound request locally, and hand back the recorder.

    ``assert_safe_url`` still runs, so a test that uses a private address is
    refused exactly as it would be in production.
    """
    recorder = Recorder()
    real_init = httpx.AsyncClient.__init__

    def patched(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(recorder.handler)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)
    return recorder


class TestConfigStoredAsText:
    """The reported crash: headers and body arrive as JSON strings."""

    async def test_api_request_with_string_headers_and_body(self, transport):
        # Exactly what the builder form writes.
        cfg = {
            "url": "https://api.example.com/orders",
            "method": "POST",
            "headers": '{\n  "Content-Type": "application/json",\n  "X-Key": "abc"\n}',
            "body": '{"order_id": "{{order_id}}"}',
        }
        result = await run_http_tool("api_request", cfg, {"order_id": "A-1"})

        assert result["status_code"] == 200
        assert transport.request.headers["X-Key"] == "abc"
        assert json.loads(transport.request.content) == {"order_id": "A-1"}

    async def test_custom_tool_with_string_headers(self, transport):
        cfg = {
            "url": "https://hooks.example.com/t",
            "headers": '{"X-Trace": "on"}',
        }
        await run_http_tool("custom_tool", cfg, {"a": 1})
        assert transport.request.headers["X-Trace"] == "on"

    async def test_malformed_json_is_a_readable_error(self, transport):
        cfg = {"url": "https://api.example.com/x", "headers": '{"a": }'}
        with pytest.raises(ToolConfigError, match="Headers is not valid JSON"):
            await run_http_tool("api_request", cfg, {})


class TestBodyTemplating:
    async def test_placeholders_are_filled_not_appended(self, transport):
        cfg = {
            "url": "https://api.example.com/x",
            "body": '{"email": "{{email}}", "amount": "{{total}}"}',
        }
        await run_http_tool(
            "api_request", cfg, {"email": "ada@example.com", "total": 42}
        )
        sent = json.loads(transport.request.content)
        # The number stays a number; the receiving API cares.
        assert sent == {"email": "ada@example.com", "amount": 42}

    async def test_a_get_sends_values_as_query_not_body(self, transport):
        cfg = {"url": "https://api.example.com/lookup", "method": "GET"}
        await run_http_tool("api_request", cfg, {"q": "ada"})
        assert transport.request.url.params["q"] == "ada"
        assert not transport.request.content


class TestTimeout:
    """The form offered a timeout the executor ignored."""

    async def test_the_configured_timeout_is_used(self, transport, monkeypatch):
        seen = {}
        real_init = httpx.AsyncClient.__init__

        def capture(self, *args, **kwargs):
            seen["timeout"] = kwargs.get("timeout")
            real_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", capture)
        await run_http_tool(
            "api_request",
            {"url": "https://api.example.com/x", "timeout": "45"},
            {},
        )
        assert seen["timeout"] == 45.0


class TestCustomToolAuth:
    """Basic auth read config keys the form never wrote."""

    def test_basic_uses_the_fields_the_form_stores(self):
        headers = auth_headers(
            {"auth_type": "basic", "auth_user": "ada", "auth_pass": "s3cret"}
        )
        import base64

        expected = base64.b64encode(b"ada:s3cret").decode()
        assert headers["Authorization"] == f"Basic {expected}"

    def test_basic_still_accepts_the_older_spelling(self):
        headers = auth_headers(
            {"auth_type": "basic", "username": "ada", "password": "s3cret"}
        )
        assert headers["Authorization"].startswith("Basic ")

    def test_bearer(self):
        headers = auth_headers({"auth_type": "bearer", "auth_token": "tok"})
        assert headers == {"Authorization": "Bearer tok"}

    def test_custom_header_is_implemented(self):
        # The form offered this mode and nothing handled it.
        headers = auth_headers(
            {"auth_type": "custom_header", "auth_header": "X-API-Key", "auth_value": "k"}
        )
        assert headers == {"X-API-Key": "k"}

    def test_none(self):
        assert auth_headers({"auth_type": "none"}) == {}
        assert auth_headers({}) == {}

    def test_a_selected_mode_with_no_credential_says_so(self):
        with pytest.raises(ToolConfigError, match="no token is set"):
            auth_headers({"auth_type": "bearer"})
        with pytest.raises(ToolConfigError, match="no username or password"):
            auth_headers({"auth_type": "basic"})
        with pytest.raises(ToolConfigError, match="no header name"):
            auth_headers({"auth_type": "custom_header"})

    async def test_auth_reaches_the_request(self, transport):
        cfg = {
            "url": "https://hooks.example.com/t",
            "auth_type": "basic",
            "auth_user": "ada",
            "auth_pass": "s3cret",
        }
        await run_http_tool("custom_tool", cfg, {})
        assert transport.request.headers["Authorization"].startswith("Basic ")


class TestSlack:
    """The configured message template was read from a key nothing writes."""

    async def test_uses_the_configured_template(self, transport):
        cfg = {
            "webhook_url": "https://hooks.slack.com/services/T/B/x",
            "message": "New lead from {{caller_name}}: {{summary}}",
        }
        await run_http_tool(
            "slack", cfg, {"caller_name": "Ada", "summary": "wants a callback"}
        )
        sent = json.loads(transport.request.content)
        assert sent["text"] == "New lead from Ada: wants a callback"

    async def test_the_channel_override_is_sent(self, transport):
        cfg = {
            "webhook_url": "https://hooks.slack.com/services/T/B/x",
            "message": "hi",
            "channel": "#leads",
        }
        await run_http_tool("slack", cfg, {})
        assert json.loads(transport.request.content)["channel"] == "#leads"

    async def test_a_template_resolving_to_nothing_still_posts_something(
        self, transport
    ):
        cfg = {
            "webhook_url": "https://hooks.slack.com/services/T/B/x",
            "message": "{{missing}}",
        }
        await run_http_tool("slack", cfg, {})
        assert json.loads(transport.request.content)["text"].strip()


class TestDestinationGuard:
    """Every URL a user names is checked, on both call paths."""

    @pytest.fixture(autouse=True)
    def enforce_egress(self, monkeypatch):
        """Undo the suite-wide `EGRESS_ALLOW_PRIVATE`.

        tests/conftest.py turns the guard off so other tests can point at local
        fixtures. These tests exist to prove the guard works, so they need it
        on — production never has it off (`check_production_secrets` refuses to
        boot if it is set).
        """
        from app.core.config import settings

        monkeypatch.setattr(settings, "EGRESS_ALLOW_PRIVATE", False)

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/admin",
            "http://localhost:6379/",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.5/internal",
            "http://192.168.1.1/",
        ],
    )
    def test_private_and_link_local_are_refused(self, url):
        with pytest.raises(ToolConfigError, match="rejected"):
            require_safe_url(url, "api_request")

    def test_a_non_http_scheme_is_refused(self):
        with pytest.raises(ToolConfigError):
            require_safe_url("file:///etc/passwd", "api_request")

    def test_a_blank_url_names_the_tool(self):
        with pytest.raises(ToolConfigError, match="No URL configured"):
            require_safe_url("", "api_request")

    async def test_the_guard_applies_to_every_http_tool_type(self):
        configs = {
            "api_request": {"url": "http://169.254.169.254/"},
            "custom_tool": {"url": "http://169.254.169.254/"},
            "mcp": {"server_url": "http://169.254.169.254/", "tool_name": "x"},
            "slack": {"webhook_url": "http://169.254.169.254/"},
        }
        assert set(configs) == set(HTTP_TOOL_TYPES)
        for tool_type, cfg in configs.items():
            with pytest.raises(ToolConfigError, match="rejected"):
                await run_http_tool(tool_type, cfg, {})


class TestRedirects:
    """Kept out of TestDestinationGuard so DNS resolution stays mocked-out."""

    async def test_redirects_are_not_followed(self, monkeypatch):
        seen = {}
        real_init = httpx.AsyncClient.__init__

        def capture(self, *args, **kwargs):
            seen["follow"] = kwargs.get("follow_redirects")
            kwargs["transport"] = httpx.MockTransport(
                lambda r: httpx.Response(200, text="{}")
            )
            real_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", capture)
        await run_http_tool("api_request", {"url": "https://api.example.com/x"}, {})
        # A permitted public URL can 302 to a private one after the check.
        assert seen["follow"] is False


class TestMcp:
    async def test_posts_the_tool_name_and_params(self, transport):
        cfg = {"server_url": "https://mcp.example.com", "tool_name": "search_crm"}
        await run_http_tool("mcp", cfg, {"q": "ada"})
        sent = json.loads(transport.request.content)
        assert sent == {"tool": "search_crm", "params": {"q": "ada"}}

    async def test_a_missing_tool_name_is_caught(self, transport):
        with pytest.raises(ToolConfigError, match="No tool name"):
            await run_http_tool("mcp", {"server_url": "https://mcp.example.com"}, {})


class TestResponseShape:
    async def test_json_is_parsed_for_the_agent_to_read(self, monkeypatch):
        def handler(request):
            return httpx.Response(200, text='{"status": "ok", "id": 12}')

        real_init = httpx.AsyncClient.__init__
        monkeypatch.setattr(
            httpx.AsyncClient,
            "__init__",
            lambda self, *a, **k: real_init(
                self, *a, **{**k, "transport": httpx.MockTransport(handler)}
            ),
        )
        result = await run_http_tool(
            "api_request", {"url": "https://api.example.com/x"}, {}
        )
        assert result["json"] == {"status": "ok", "id": 12}
        assert result["ok"] is True

    async def test_a_non_json_error_page_still_comes_back(self, monkeypatch):
        def handler(request):
            return httpx.Response(500, text="<html>Server Error</html>")

        real_init = httpx.AsyncClient.__init__
        monkeypatch.setattr(
            httpx.AsyncClient,
            "__init__",
            lambda self, *a, **k: real_init(
                self, *a, **{**k, "transport": httpx.MockTransport(handler)}
            ),
        )
        result = await run_http_tool(
            "api_request", {"url": "https://api.example.com/x"}, {}
        )
        assert result["ok"] is False
        assert "Server Error" in result["body"]
        assert "json" not in result
