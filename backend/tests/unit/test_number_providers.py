"""
Unit tests for multi-carrier phone number provisioning.

Covers the three pieces that decide where a number is bought:
- the carrier clients (Twilio / Telnyx) and how they translate carrier payloads
- credential resolution from an integration connection
- provider selection rules (auto-select one, require a choice when several)

The carrier clients are exercised with a stubbed `_request`, so no network.
"""
import base64
import types

import pytest

from app.services.integrations.credential_manager import get_credential_manager
from app.services.telephony import provider_registry
from app.services.telephony.provider_registry import (
    INTEGRATION_SOURCE,
    PLATFORM_SOURCE,
    AmbiguousProviderError,
    NoTelephonyProviderError,
    ProviderOption,
    _connection_credentials,
    resolve_provider,
)
from app.services.telephony.providers import (
    NumberProviderError,
    TelnyxNumberProvider,
    TwilioNumberProvider,
)


def _stub_requests(provider, responses):
    """
    Replace `provider._request` with a canned-response stub.

    `responses` maps "METHOD /path" -> payload (or a callable taking the call
    kwargs). Every call is recorded on `provider.calls` for assertions.
    """
    provider.calls = []

    async def fake_request(method, path, **kwargs):
        provider.calls.append({"method": method, "path": path, **kwargs})
        key = f"{method} {path}"
        if key not in responses:
            raise AssertionError(f"unexpected carrier call: {key}")
        value = responses[key]
        return value(kwargs) if callable(value) else value

    provider._request = fake_request
    return provider


# ── credentials ─────────────────────────────────────────────────────────────


class _FakeConnection:
    """Stand-in for an IntegrationConnection row."""

    def __init__(self, api_key_encrypted=None, auth_data_encrypted=None):
        self.id = "conn-1"
        self.api_key_encrypted = api_key_encrypted
        self.auth_data_encrypted = auth_data_encrypted


def test_twilio_credentials_decoded_from_base64_pair():
    """Twilio stores Base64('SID:TOKEN') in the API key field."""
    manager = get_credential_manager()
    packed = base64.b64encode(b"AC_test_sid:test_auth_token").decode()
    connection = _FakeConnection(api_key_encrypted=manager.encrypt(packed))

    credentials = _connection_credentials("twilio", connection)

    assert credentials == {"account_sid": "AC_test_sid", "auth_token": "test_auth_token"}


def test_twilio_credentials_prefer_explicit_auth_data():
    """Explicit auth-data fields win over decoding the packed key."""
    manager = get_credential_manager()
    packed = base64.b64encode(b"AC_packed:packed_token").decode()
    connection = _FakeConnection(
        api_key_encrypted=manager.encrypt(packed),
        auth_data_encrypted=manager.encrypt_dict(
            {"account_sid": "AC_explicit", "auth_token": "explicit_token"}
        ),
    )

    credentials = _connection_credentials("twilio", connection)

    assert credentials["account_sid"] == "AC_explicit"
    assert credentials["auth_token"] == "explicit_token"


def test_telnyx_credentials_are_the_raw_api_key():
    manager = get_credential_manager()
    connection = _FakeConnection(api_key_encrypted=manager.encrypt("KEY0123telnyx"))

    assert _connection_credentials("telnyx", connection) == {"api_key": "KEY0123telnyx"}


def test_connection_without_credentials_is_rejected():
    with pytest.raises(NumberProviderError):
        _connection_credentials("telnyx", _FakeConnection())


def test_provider_rejects_incomplete_credentials():
    with pytest.raises(NumberProviderError):
        TwilioNumberProvider({"account_sid": "AC_only_sid"})
    with pytest.raises(NumberProviderError):
        TelnyxNumberProvider({})


# ── Twilio carrier client ───────────────────────────────────────────────────


def _twilio() -> TwilioNumberProvider:
    return TwilioNumberProvider({"account_sid": "AC123", "auth_token": "token"})


@pytest.mark.asyncio
async def test_twilio_search_maps_capabilities():
    provider = _stub_requests(
        _twilio(),
        {
            "GET /2010-04-01/Accounts/AC123/AvailablePhoneNumbers/US/Local.json": {
                "available_phone_numbers": [
                    {
                        "phone_number": "+14155550100",
                        "friendly_name": "(415) 555-0100",
                        "locality": "San Francisco",
                        "region": "CA",
                        "capabilities": {"voice": True, "SMS": True, "MMS": False},
                    }
                ]
            }
        },
    )

    results = await provider.search_numbers(country_code="US", area_code="415", limit=5)

    assert len(results) == 1
    number = results[0]
    assert number.phone_number == "+14155550100"
    assert number.provider == "twilio"
    assert number.capabilities == {"voice": True, "sms": True, "mms": False}
    # Search filters are passed through to Twilio's parameter names.
    assert provider.calls[0]["params"]["AreaCode"] == "415"
    assert provider.calls[0]["params"]["PageSize"] == 5


@pytest.mark.asyncio
async def test_twilio_purchase_sets_voice_webhook():
    provider = _stub_requests(
        _twilio(),
        {
            "POST /2010-04-01/Accounts/AC123/IncomingPhoneNumbers.json": {
                "sid": "PN999",
                "phone_number": "+14155550100",
                "capabilities": {"voice": True, "sms": True},
            }
        },
    )

    purchased = await provider.purchase_number(
        phone_number="+14155550100",
        voice_url="https://api.example.com/api/v1/telephony/twilio/voice/agent-1",
        status_callback_url="https://api.example.com/api/v1/telephony/twilio/status",
    )

    assert purchased.provider_sid == "PN999"
    assert purchased.provider == "twilio"
    form = provider.calls[0]["form"]
    assert form["PhoneNumber"] == "+14155550100"
    assert form["VoiceUrl"].endswith("/telephony/twilio/voice/agent-1")
    assert form["StatusCallback"].endswith("/telephony/twilio/status")


@pytest.mark.asyncio
async def test_twilio_release_falls_back_to_lookup_when_sid_missing():
    """Older rows may have no SID; the number is resolved by its E.164 value."""
    provider = _stub_requests(
        _twilio(),
        {
            "GET /2010-04-01/Accounts/AC123/IncomingPhoneNumbers.json": {
                "incoming_phone_numbers": [{"sid": "PN_looked_up"}]
            },
            "DELETE /2010-04-01/Accounts/AC123/IncomingPhoneNumbers/PN_looked_up.json": None,
        },
    )

    assert await provider.release_number(None, phone_number="+14155550100") is True
    assert provider.calls[-1]["method"] == "DELETE"


# ── Telnyx carrier client ───────────────────────────────────────────────────


def _telnyx() -> TelnyxNumberProvider:
    return TelnyxNumberProvider({"api_key": "KEY123"})


@pytest.mark.asyncio
async def test_telnyx_search_maps_features_regions_and_cost():
    provider = _stub_requests(
        _telnyx(),
        {
            "GET /v2/available_phone_numbers": {
                "data": [
                    {
                        "phone_number": "+13015550100",
                        "features": [{"name": "voice"}, {"name": "sms"}],
                        "region_information": [
                            {"region_type": "state", "region_name": "MD"},
                            {"region_type": "rate_center", "region_name": "BETHESDA"},
                        ],
                        "cost_information": {
                            "monthly_cost": "1.00",
                            "upfront_cost": "0.50",
                            "currency": "USD",
                        },
                    }
                ]
            }
        },
    )

    results = await provider.search_numbers(country_code="US", area_code="301", contains="555")

    assert len(results) == 1
    number = results[0]
    assert number.provider == "telnyx"
    assert number.capabilities == {"voice": True, "sms": True, "mms": False}
    assert number.locality == "BETHESDA"
    assert number.region == "MD"
    assert number.monthly_cost == 1.0
    assert number.setup_cost == 0.5
    # Telnyx uses bracketed filter params.
    params = provider.calls[0]["params"]
    assert params["filter[national_destination_code]"] == "301"
    assert params["filter[phone_number][contains]"] == "555"


@pytest.mark.asyncio
async def test_telnyx_purchase_creates_and_attaches_texml_application():
    """A number is only reachable once it is attached to an app holding the URL."""
    voice_url = "https://api.example.com/api/v1/telephony/telnyx/voice/agent-1"
    provider = _stub_requests(
        _telnyx(),
        {
            "GET /v2/texml_applications": {"data": []},
            "POST /v2/texml_applications": {"data": {"id": "app-77"}},
            "POST /v2/number_orders": {
                "data": {"id": "order-1", "status": "pending"}
            },
            "GET /v2/phone_numbers": {"data": [{"id": "num-42"}]},
            "PATCH /v2/phone_numbers/num-42": {"data": {"id": "num-42"}},
        },
    )

    purchased = await provider.purchase_number(
        phone_number="+13015550100",
        voice_url=voice_url,
        status_callback_url="https://api.example.com/api/v1/telephony/telnyx/status",
    )

    assert purchased.provider_sid == "num-42"
    assert purchased.provider_metadata["texml_application_id"] == "app-77"
    assert purchased.provider_metadata["order_id"] == "order-1"

    order = next(c for c in provider.calls if c["path"] == "/v2/number_orders")
    assert order["json_body"]["connection_id"] == "app-77"
    attach = next(c for c in provider.calls if c["method"] == "PATCH")
    assert attach["json_body"] == {"connection_id": "app-77"}


@pytest.mark.asyncio
async def test_telnyx_purchase_reuses_existing_texml_application():
    """Buying a second number for the same agent must not create a second app."""
    voice_url = "https://api.example.com/api/v1/telephony/telnyx/voice/agent-1"
    provider = _stub_requests(
        _telnyx(),
        {
            "GET /v2/texml_applications": {
                "data": [{"id": "app-existing", "voice_url": voice_url}]
            },
            "POST /v2/number_orders": {"data": {"id": "order-2"}},
            "GET /v2/phone_numbers": {"data": [{"id": "num-43"}]},
            "PATCH /v2/phone_numbers/num-43": {"data": {}},
        },
    )

    purchased = await provider.purchase_number(
        phone_number="+13015550101", voice_url=voice_url
    )

    assert purchased.provider_metadata["texml_application_id"] == "app-existing"
    assert not any(
        c["method"] == "POST" and c["path"] == "/v2/texml_applications"
        for c in provider.calls
    )


@pytest.mark.asyncio
async def test_telnyx_purchase_survives_unsettled_order(monkeypatch):
    """
    An order that has not settled must still return a result — the number was
    paid for, so it has to be recorded even without a resource id yet.
    """
    monkeypatch.setattr(TelnyxNumberProvider, "_ORDER_POLL_ATTEMPTS", 2)
    monkeypatch.setattr(TelnyxNumberProvider, "_ORDER_POLL_DELAY_SECONDS", 0)

    provider = _stub_requests(
        _telnyx(),
        {
            "GET /v2/texml_applications": {"data": []},
            "POST /v2/texml_applications": {"data": {"id": "app-9"}},
            "POST /v2/number_orders": {"data": {"id": "order-3"}},
            "GET /v2/phone_numbers": {"data": []},
        },
    )

    purchased = await provider.purchase_number(
        phone_number="+13015550102", voice_url="https://api.example.com/voice/a"
    )

    assert purchased.phone_number == "+13015550102"
    assert purchased.provider_sid is None
    assert purchased.provider_metadata["order_id"] == "order-3"


# ── provider selection ──────────────────────────────────────────────────────


def _option(slug, name, connection_id="conn-1", source=INTEGRATION_SOURCE):
    return ProviderOption(
        slug=slug,
        name=name,
        source=source,
        connection_id=connection_id,
        connection_name=name,
    )


@pytest.fixture
def stub_selection(monkeypatch):
    """Drive `resolve_provider` off a fixed option list, with no DB or network."""

    def apply(options):
        async def fake_list(db, user):
            return options

        async def fake_build(db, option):
            return types.SimpleNamespace(slug=option.slug)

        monkeypatch.setattr(provider_registry, "list_available_providers", fake_list)
        monkeypatch.setattr(provider_registry, "_build_provider", fake_build)

    return apply


@pytest.mark.asyncio
async def test_no_connected_carrier_is_a_clear_error(stub_selection):
    stub_selection([])

    with pytest.raises(NoTelephonyProviderError) as exc:
        await resolve_provider(db=None, user=None)

    assert "Integrations" in str(exc.value)


@pytest.mark.asyncio
async def test_single_carrier_is_selected_automatically(stub_selection):
    stub_selection([_option("telnyx", "Telnyx")])

    resolved = await resolve_provider(db=None, user=None)

    assert resolved.slug == "telnyx"


@pytest.mark.asyncio
async def test_two_carriers_require_an_explicit_choice(stub_selection):
    stub_selection([_option("twilio", "Twilio", "c1"), _option("telnyx", "Telnyx", "c2")])

    with pytest.raises(AmbiguousProviderError):
        await resolve_provider(db=None, user=None)


@pytest.mark.asyncio
async def test_explicit_slug_picks_that_carrier(stub_selection):
    stub_selection([_option("twilio", "Twilio", "c1"), _option("telnyx", "Telnyx", "c2")])

    resolved = await resolve_provider(db=None, user=None, slug="telnyx")

    assert resolved.slug == "telnyx"
    assert resolved.option.connection_id == "c2"


@pytest.mark.asyncio
async def test_unconnected_carrier_is_refused(stub_selection):
    """Asking for a carrier the user has not connected must not silently fall back."""
    stub_selection([_option("twilio", "Twilio")])

    with pytest.raises(NoTelephonyProviderError) as exc:
        await resolve_provider(db=None, user=None, slug="telnyx")

    assert "Telnyx" in str(exc.value)


@pytest.mark.asyncio
async def test_connection_id_disambiguates_duplicate_carriers(stub_selection):
    """The same carrier can be connected twice; the connection id decides."""
    stub_selection(
        [_option("twilio", "Twilio Main", "c1"), _option("twilio", "Twilio Backup", "c2")]
    )

    resolved = await resolve_provider(db=None, user=None, connection_id="c2")

    assert resolved.option.connection_name == "Twilio Backup"


@pytest.mark.asyncio
async def test_stale_connection_id_is_refused(stub_selection):
    stub_selection([_option("twilio", "Twilio", "c1")])

    with pytest.raises(NoTelephonyProviderError):
        await resolve_provider(db=None, user=None, connection_id="c-removed")


@pytest.mark.asyncio
async def test_platform_credentials_are_usable_when_nothing_is_connected(stub_selection):
    """Server-level Twilio credentials keep older deployments working."""
    stub_selection([_option("twilio", "Twilio", None, PLATFORM_SOURCE)])

    resolved = await resolve_provider(db=None, user=None)

    assert resolved.slug == "twilio"
    assert resolved.connection_uuid is None
