"""
What an error response may say.

QA found raw exception text in API responses — carrier replies, parser errors,
database failures — and a helper that *returned* its HTTPException. The rule
now: only a message written for the user reaches the client, through
``public_message``; everything else is logged and answered generically.
"""
import re
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.phone_numbers import CARRIER_ERROR, _raise_provider_error
from app.core.exceptions import UserFacingError
from app.services.integrations.integration_manager import IntegrationError
from app.services.telephony.provider_registry import NoTelephonyProviderError
from app.services.telephony.providers.base import NumberProviderError, _carrier_rejection_message

ENDPOINTS = Path(__file__).resolve().parents[2] / "app" / "api"

#: Any response detail or websocket/SSE message built from a caught exception.
_RAW_ERROR = re.compile(
    r"detail\s*=\s*(str\((e|exc)\)|f\"[^\"]*\{(e|exc|str\((e|exc)\))\})"
    r"|['\"]message['\"]\s*:\s*str\((e|exc)\)"
)


def test_no_endpoint_returns_raw_exception_text():
    offenders = [
        f"{path.relative_to(ENDPOINTS.parent)}:{number}: {line.strip()}"
        for path in ENDPOINTS.rglob("*.py")
        for number, line in enumerate(path.read_text().splitlines(), 1)
        if _RAW_ERROR.search(line)
    ]
    assert offenders == [], "Use e.public_message or a generic sentence:\n" + "\n".join(offenders)


class TestProviderErrorHelper:
    def test_raises_instead_of_returning(self):
        # The reported bug: `return HTTPException(...)` is a value, not an error.
        with pytest.raises(HTTPException) as exc:
            _raise_provider_error(NoTelephonyProviderError("Connect Twilio under Integrations first."))
        assert exc.value.status_code == 400
        assert exc.value.detail == "Connect Twilio under Integrations first."

    def test_carrier_detail_stays_out_of_the_response(self):
        raw = NumberProviderError("Twilio: Account AC123 has insufficient permissions for /IncomingPhoneNumbers")
        with pytest.raises(HTTPException) as exc:
            _raise_provider_error(raw)
        assert exc.value.status_code == 502
        assert exc.value.detail == CARRIER_ERROR

    def test_unknown_failures_are_generic_500s(self):
        with pytest.raises(HTTPException) as exc:
            _raise_provider_error(RuntimeError("connection to db failed: password authentication"))
        assert exc.value.status_code == 500
        assert "password" not in exc.value.detail


class TestCarrierMessages:
    @pytest.mark.parametrize("status, phrase", [
        (401, "credentials"), (404, "could not find"), (429, "rate-limiting"),
        (503, "having problems"), (400, "could not complete"),
    ])
    def test_status_picks_the_sentence(self, status, phrase):
        assert phrase in _carrier_rejection_message("Twilio", status)

    async def test_transport_errors_do_not_leak_the_url(self, monkeypatch):
        from app.services.telephony.providers.twilio_provider import TwilioNumberProvider

        async def boom(*args, **kwargs):
            raise httpx.ConnectError("[Errno -2] Name or service not known: api.twilio.com")

        monkeypatch.setattr(httpx.AsyncClient, "request", boom)
        provider = TwilioNumberProvider({"account_sid": "AC1", "auth_token": "t"})
        with pytest.raises(NumberProviderError) as exc:
            await provider._request("GET", "/Accounts.json")
        assert "Errno" in str(exc.value)  # kept for the log
        assert exc.value.public_message == "Could not reach Twilio. Try again shortly."


class TestIntegrationErrors:
    def test_wrapped_errors_have_no_public_message(self):
        assert IntegrationError("Failed to complete OAuth flow: IntegrityError ...").public_message is None

    def test_public_errors_are_shown_as_written(self):
        assert IntegrationError.public("This connection link has expired.").public_message == (
            "This connection link has expired."
        )


def test_user_facing_errors_expose_their_message():
    assert UserFacingError("That code has expired.").public_message == "That code has expired."


class TestUpstreamFailureStatus:
    """Cloudflare replaces an origin 502/504 with its own page, dropping CORS."""

    @staticmethod
    def _client():
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from starlette.exceptions import HTTPException as StarletteHTTPException
        from app.main import upstream_failure_exception_handler

        app = FastAPI()
        app.add_exception_handler(StarletteHTTPException, upstream_failure_exception_handler)

        @app.get("/fail/{code}")
        async def fail(code: int):
            raise HTTPException(status_code=code, detail="Twilio is having problems right now.")

        return TestClient(app)

    @pytest.mark.parametrize("code", [502, 504])
    def test_gateway_errors_leave_as_503_with_their_detail(self, code):
        res = self._client().get(f"/fail/{code}")
        assert res.status_code == 503
        assert res.json()["detail"] == "Twilio is having problems right now."

    @pytest.mark.parametrize("code", [400, 401, 404, 500])
    def test_other_errors_are_untouched(self, code):
        assert self._client().get(f"/fail/{code}").status_code == code


class TestAreaCodeValidation:
    @pytest.mark.parametrize("area_code", ["12", "1234", "4a5"])
    async def test_malformed_us_area_code_is_a_400(self, area_code):
        from app.api.v1.endpoints.phone_numbers import search_phone_numbers

        with pytest.raises(HTTPException) as exc:
            await search_phone_numbers(
                country_code="US", area_code=area_code, contains=None, limit=10,
                provider=None, connection_id=None, current_user=None, org_id=None, db=None,
            )
        assert exc.value.status_code == 400
        assert "3 digits" in exc.value.detail
