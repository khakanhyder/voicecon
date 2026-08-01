"""
Unit tests for Twilio webhook signature validation.

A number bought on a user's own Twilio account is signed with *their* auth
token, not the platform one. These tests cover the resulting rule: a webhook is
accepted when it is signed by the account that owns the called number, and
rejected otherwise.
"""
import types

import pytest
from twilio.request_validator import RequestValidator

from app.api.v1.endpoints import telephony

WEBHOOK_URL = "https://api.voicecon.test/api/v1/telephony/twilio/voice/agent-1"
PLATFORM_TOKEN = "platform_auth_token"
OWN_TOKEN = "user_auth_token"


def _form(to_number="+14155550100"):
    return {"CallSid": "CA123", "From": "+14155559999", "To": to_number}


def _request(signature):
    """A stand-in for the FastAPI request the webhook arrives on."""
    return types.SimpleNamespace(
        headers={"X-Twilio-Signature": signature} if signature else {},
        url=types.SimpleNamespace(scheme="https", path="/api/v1/telephony/twilio/voice/agent-1"),
    )


def _sign(token, form):
    return RequestValidator(token).compute_signature(WEBHOOK_URL, form)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, numbers=()):
        self.numbers = list(numbers)

    async def execute(self, *_args, **_kwargs):
        return _FakeResult(self.numbers)


def _number(connection_id="conn-1", credential_source="integration"):
    return types.SimpleNamespace(
        phone_number="+14155550100",
        provider="twilio",
        integration_connection_id=connection_id,
        provider_metadata={"credential_source": credential_source},
    )


@pytest.fixture(autouse=True)
def webhook_settings(monkeypatch):
    """Validation on, platform credentials configured, fixed public URL."""
    monkeypatch.setattr(telephony.settings, "TWILIO_VALIDATE_WEBHOOKS", True)
    monkeypatch.setattr(telephony.settings, "TWILIO_AUTH_TOKEN", PLATFORM_TOKEN)
    monkeypatch.setattr(
        telephony.settings, "TWILIO_PUBLIC_BASE_URL", "https://api.voicecon.test"
    )


@pytest.fixture
def own_account_number(monkeypatch):
    """The called number lives on the user's own connected Twilio."""
    async def fake_credentials(db, slug, connection_id=None, provider_metadata=None):
        return {"account_sid": "AC_user", "auth_token": OWN_TOKEN}

    monkeypatch.setattr(telephony, "credentials_for_number", fake_credentials)
    return _FakeDB([_number()])


@pytest.mark.asyncio
async def test_own_account_signature_is_accepted(own_account_number):
    """
    The regression this guards: with a platform token configured, a call to a
    user's own number was rejected because it was signed with their token.
    """
    form = _form()

    valid = await telephony.validate_twilio_request(
        _request(_sign(OWN_TOKEN, form)), form, own_account_number
    )

    assert valid is True


@pytest.mark.asyncio
async def test_platform_signature_is_accepted_for_platform_numbers(monkeypatch):
    async def fake_credentials(db, slug, connection_id=None, provider_metadata=None):
        return {"account_sid": "AC_platform", "auth_token": PLATFORM_TOKEN}

    monkeypatch.setattr(telephony, "credentials_for_number", fake_credentials)
    form = _form()

    valid = await telephony.validate_twilio_request(
        _request(_sign(PLATFORM_TOKEN, form)),
        form,
        _FakeDB([_number(connection_id=None, credential_source="platform")]),
    )

    assert valid is True


@pytest.mark.asyncio
async def test_signature_from_an_unrelated_account_is_rejected(own_account_number):
    form = _form()

    valid = await telephony.validate_twilio_request(
        _request(_sign("someone_elses_token", form)), form, own_account_number
    )

    assert valid is False


@pytest.mark.asyncio
async def test_missing_signature_header_is_rejected(own_account_number):
    form = _form()

    valid = await telephony.validate_twilio_request(
        _request(None), form, own_account_number
    )

    assert valid is False


@pytest.mark.asyncio
async def test_validation_is_skipped_when_no_token_is_available(monkeypatch):
    """Credential-less local development must keep working."""
    monkeypatch.setattr(telephony.settings, "TWILIO_AUTH_TOKEN", None)
    form = _form()

    valid = await telephony.validate_twilio_request(
        _request(None), form, _FakeDB()
    )

    assert valid is True


@pytest.mark.asyncio
async def test_validation_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(telephony.settings, "TWILIO_VALIDATE_WEBHOOKS", False)
    form = _form()

    valid = await telephony.validate_twilio_request(
        _request("bogus"), form, _FakeDB()
    )

    assert valid is True
