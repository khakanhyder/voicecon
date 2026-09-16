"""
What a tool needs before it may be saved.

Each "rejects" case used to save cleanly and fail only on a live call. The
field keys are asserted, not just "some error", because the builder form places
each message under the input it names.
"""
import pytest

from app.services.tools.validation import validate_tool_config


def errors(tool_type, **config):
    return validate_tool_config(tool_type, config)


class TestRequiredFields:
    @pytest.mark.parametrize("tool_type, field", [
        ("workflow", "workflow_id"),
        ("connected_integration", "connection_id"),
        ("transfer_call", "destination"),
        ("leave_voicemail", "message"),
        ("send_sms", "to"),
        ("dtmf", "digits"),
        ("sip_request", "sip_uri"),
        ("handoff", "destination"),
        ("query_knowledge_base", "knowledge_base_id"),
        ("api_request", "url"),
        ("mcp", "server_url"),
        ("mcp", "tool_name"),
        ("slack", "webhook_url"),
        ("slack", "message"),
        ("custom_tool", "url"),
    ])
    def test_an_empty_config_names_the_missing_field(self, tool_type, field):
        assert field in errors(tool_type)

    def test_whitespace_does_not_count_as_filled_in(self):
        assert "destination" in errors("transfer_call", destination="   ")

    def test_hang_up_needs_nothing(self):
        assert errors("hang_up") == {}


class TestTransferAndSms:
    @pytest.mark.parametrize("destination", [
        "+15551234567", "+44 20 7946 0958", "+1 (555) 123-4567",
        "sip:agent@example.com", "sips:queue@pbx.example.com", "{{caller_number}}",
    ])
    def test_accepts_dialable_destinations(self, destination):
        assert errors("transfer_call", destination=destination) == {}

    @pytest.mark.parametrize("destination", [
        "hello", "5551234567", "+123", "+1555abc4567", "sip:nohost", "example.com",
    ])
    def test_rejects_undialable_destinations(self, destination):
        assert "destination" in errors("transfer_call", destination=destination)

    def test_sms_accepts_the_caller_template_and_needs_a_message(self):
        assert errors("send_sms", to="{{caller_number}}", message="Hi") == {}
        assert set(errors("send_sms", to="call me")) == {"to", "message"}


class TestUrlsAndJson:
    @pytest.mark.parametrize("url", ["api.example.com", "ftp://example.com", "https://", "https://api", "https://a b.com"])
    def test_rejects_urls_that_are_not_full_http_urls(self, url):
        assert "url" in errors("api_request", url=url)

    def test_slack_webhooks_must_be_https(self):
        assert "webhook_url" in errors("slack", webhook_url="http://hooks.slack.com/x", message="m")
        assert errors("slack", webhook_url="https://hooks.slack.com/services/T/B/x", message="m") == {}

    def test_headers_and_body_must_be_json_objects(self):
        found = errors("api_request", url="https://api.example.com", headers="{nope", body="[1, 2]")
        assert set(found) == {"headers", "body"}

    def test_parsed_json_from_an_api_client_is_accepted(self):
        assert errors(
            "api_request", url="https://api.example.com",
            headers={"X-Key": "abc"}, body={"name": "{{name}}"},
        ) == {}

    @pytest.mark.parametrize("timeout", ["0", "121", "soon"])
    def test_timeout_must_be_seconds_in_range(self, timeout):
        assert "timeout" in errors("mcp", server_url="https://mcp.example.com", tool_name="x", timeout=timeout)

    def test_invalid_method_is_rejected(self):
        assert "method" in errors("api_request", url="https://api.example.com", method="FETCH")


class TestCustomToolAuth:
    base = {"url": "https://hooks.example.com/tool"}

    def test_each_auth_mode_requires_its_credentials(self):
        assert "auth_token" in validate_tool_config("custom_tool", {**self.base, "auth_type": "bearer"})
        assert {"auth_user", "auth_pass"} <= set(validate_tool_config("custom_tool", {**self.base, "auth_type": "basic"}))
        found = validate_tool_config("custom_tool", {**self.base, "auth_type": "custom_header", "auth_header": "X Key"})
        assert {"auth_header", "auth_value"} <= set(found)

    def test_unused_auth_fields_are_not_checked(self):
        assert validate_tool_config("custom_tool", {**self.base, "auth_type": "none", "auth_token": ""}) == {}


class TestParametersAndTypes:
    def test_parameter_names_must_be_identifiers(self):
        schema = {"type": "object", "properties": {"customer name": {"type": "string"}}, "required": []}
        assert "parameters" in errors("hang_up", parameters=schema)

    def test_required_parameters_must_exist(self):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["email"]}
        assert "parameters" in errors("hang_up", parameters=schema)

    @pytest.mark.parametrize("tool_type", ["google_sheets", "google_calendar", "gohighlevel"])
    def test_retired_types_point_at_connected_integrations(self, tool_type):
        assert "Connected Integration" in errors(tool_type)["tool_type"]

    def test_unknown_types_are_rejected(self):
        assert "tool_type" in errors("teleport")

    def test_dtmf_rejects_letters_outside_the_keypad(self):
        assert "digits" in errors("dtmf", digits="12x")
        assert errors("dtmf", digits="1w2#*") == {}
