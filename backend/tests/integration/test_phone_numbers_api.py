"""
Integration tests for buying phone numbers from a connected carrier.

Drives the real FastAPI routes end to end — provider listing, search, purchase,
reassignment and release — with the carrier HTTP layer stubbed at
``NumberProvider._request``. Everything below that stub is the real code path:
credential decryption, provider resolution, the Telnyx two-step order flow, and
the database writes.

Follows the async-client pattern in ``test_settings_api.py``: an in-process
httpx client so the app shares the test event loop, per-request DB sessions, and
self-contained fixtures (the shared conftest user fixtures predate the models).
"""
import base64
import uuid

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.dependencies import get_current_user
from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models.agent import Agent
from app.models.call import PhoneNumber
from app.models.integration import IntegrationConnection, IntegrationConnector
from app.models.user import Organization, OrganizationMember, User
from app.services.integrations.credential_manager import get_credential_manager
from app.services.telephony.providers.base import NumberProvider

# Which user the next request acts as (set by ``as_user``).
_ACTING: dict = {"id": None}

# Every carrier call the stub saw, for assertions.
CARRIER_CALLS: list = []


# ---------- carrier stub ----------

TELNYX_SEARCH = {
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

TWILIO_SEARCH = {
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


@pytest.fixture(autouse=True)
def carrier(monkeypatch):
    """
    Replace the carrier HTTP layer with a canned Twilio/Telnyx account.

    Routing is by provider slug + method + path, so the same stub serves both
    carriers and each test can assert on exactly what was sent.
    """
    CARRIER_CALLS.clear()
    texml_apps: dict = {}

    async def fake_request(self, method, path, **kwargs):
        CARRIER_CALLS.append(
            {"provider": self.slug, "method": method, "path": path, **kwargs}
        )
        key = f"{method} {path}"

        if self.slug == "twilio":
            if "AvailablePhoneNumbers" in path:
                return TWILIO_SEARCH
            if key.endswith("IncomingPhoneNumbers.json") and method == "POST":
                return {
                    "sid": "PN_purchased",
                    "phone_number": kwargs["form"]["PhoneNumber"],
                    "capabilities": {"voice": True, "sms": True},
                }
            if method == "GET" and path.endswith("IncomingPhoneNumbers.json"):
                return {"incoming_phone_numbers": [{"sid": "PN_purchased"}]}
            if method in ("POST", "DELETE"):  # update webhook / release
                return None
            raise AssertionError(f"unexpected twilio call: {key}")

        # telnyx
        if key == "GET /v2/available_phone_numbers":
            return TELNYX_SEARCH
        if key == "GET /v2/texml_applications":
            return {"data": [{"id": app_id, "voice_url": url}
                             for url, app_id in texml_apps.items()]}
        if key == "POST /v2/texml_applications":
            url = kwargs["json_body"]["voice_url"]
            texml_apps[url] = f"app-{len(texml_apps) + 1}"
            return {"data": {"id": texml_apps[url]}}
        if key == "POST /v2/number_orders":
            return {"data": {"id": "order-1", "status": "pending"}}
        if key == "GET /v2/phone_numbers":
            return {"data": [{"id": "num-telnyx-1"}]}
        if method in ("PATCH", "DELETE"):
            return {"data": {}}
        raise AssertionError(f"unexpected telnyx call: {key}")

    monkeypatch.setattr(NumberProvider, "_request", fake_request)
    return CARRIER_CALLS


def calls_for(provider: str, method: str = None, contains: str = None) -> list:
    """Filter recorded carrier calls."""
    out = [c for c in CARRIER_CALLS if c["provider"] == provider]
    if method:
        out = [c for c in out if c["method"] == method]
    if contains:
        out = [c for c in out if contains in c["path"]]
    return out


# ---------- fixtures ----------


@pytest_asyncio.fixture
async def owner(db_session) -> User:
    """A user who owns an organization, as the register endpoint builds it."""
    user = User(
        email=f"owner-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="Owner",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    org = Organization(
        name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}", owner_id=user.id, is_active=True
    )
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(db_session) -> User:
    """An unrelated user, for tenant-isolation checks."""
    user = User(
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="Other",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    org = Organization(
        name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}", owner_id=user.id, is_active=True
    )
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _org_id_of(db_session, user: User) -> uuid.UUID:
    result = await db_session.execute(
        select(OrganizationMember.organization_id).where(
            OrganizationMember.user_id == user.id
        )
    )
    return result.scalar_one()


@pytest_asyncio.fixture
async def agent(db_session, owner) -> Agent:
    org_id = await _org_id_of(db_session, owner)
    agent = Agent(
        user_id=owner.id,
        organization_id=org_id,
        name="Support Bot",
        system_prompt="You are helpful.",
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def second_agent(db_session, owner) -> Agent:
    org_id = await _org_id_of(db_session, owner)
    agent = Agent(
        user_id=owner.id,
        organization_id=org_id,
        name="Sales Bot",
        system_prompt="You sell things.",
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


async def _connect_carrier(db_session, user: User, slug: str, name: str) -> IntegrationConnection:
    """Create the connector + an active connection, as the Integrations UI does."""
    result = await db_session.execute(
        select(IntegrationConnector).where(IntegrationConnector.slug == slug)
    )
    connector = result.scalar_one_or_none()
    if not connector:
        connector = IntegrationConnector(
            name=name,
            slug=slug,
            category="phone",
            auth_type="api_key",
            base_url=f"https://api.{slug}.com",
            auth_config={},
            is_active=True,
        )
        db_session.add(connector)
        await db_session.flush()

    secret = (
        base64.b64encode(b"ACfakesid:faketoken").decode()
        if slug == "twilio"
        else "KEY_telnyx_fake"
    )
    connection = IntegrationConnection(
        user_id=user.id,
        organization_id=await _org_id_of(db_session, user),
        connector_id=connector.id,
        name=f"{name} Connection",
        status="active",
        is_active=True,
        api_key_encrypted=get_credential_manager().encrypt(secret),
    )
    db_session.add(connection)
    await db_session.commit()
    await db_session.refresh(connection)
    return connection


@pytest_asyncio.fixture
async def telnyx_connected(db_session, owner) -> IntegrationConnection:
    return await _connect_carrier(db_session, owner, "telnyx", "Telnyx")


@pytest_asyncio.fixture
async def twilio_connected(db_session, owner) -> IntegrationConnection:
    return await _connect_carrier(db_session, owner, "twilio", "Twilio")


@pytest_asyncio.fixture
async def client(db_engine):
    """In-loop async HTTP client with per-request DB sessions."""
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    from fastapi import Depends

    async def _current_user(db=Depends(get_db)):
        result = await db.execute(select(User).where(User.id == _ACTING["id"]))
        return result.scalar_one()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _current_user

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def as_user(client, user: User):
    _ACTING["id"] = user.id
    return client


# ---------- provider listing ----------


@pytest.mark.integration
@pytest.mark.asyncio
class TestProviderListing:
    async def test_nothing_connected_lists_no_providers(self, client, owner):
        res = await as_user(client, owner).get("/api/v1/phone-numbers/providers")
        assert res.status_code == 200
        assert res.json() == []

    async def test_only_connected_carriers_are_listed(
        self, client, owner, telnyx_connected
    ):
        """Twilio is not connected, so it must not be offered."""
        res = await as_user(client, owner).get("/api/v1/phone-numbers/providers")
        assert res.status_code == 200
        body = res.json()
        assert [p["slug"] for p in body] == ["telnyx"]
        assert body[0]["connection_id"] == str(telnyx_connected.id)
        assert body[0]["source"] == "integration"

    async def test_both_carriers_listed_when_both_connected(
        self, client, owner, telnyx_connected, twilio_connected
    ):
        res = await as_user(client, owner).get("/api/v1/phone-numbers/providers")
        assert sorted(p["slug"] for p in res.json()) == ["telnyx", "twilio"]

    async def test_another_users_connection_is_not_listed(
        self, client, other_user, telnyx_connected
    ):
        res = await as_user(client, other_user).get("/api/v1/phone-numbers/providers")
        assert res.json() == []


# ---------- search ----------


@pytest.mark.integration
@pytest.mark.asyncio
class TestSearch:
    async def test_search_without_a_connected_carrier_is_refused(self, client, owner):
        res = await as_user(client, owner).get("/api/v1/phone-numbers/search")
        assert res.status_code == 400
        assert "Integrations" in res.json()["detail"]

    async def test_single_carrier_is_used_automatically(
        self, client, owner, telnyx_connected
    ):
        res = await as_user(client, owner).get(
            "/api/v1/phone-numbers/search?country_code=US&area_code=301"
        )
        assert res.status_code == 200
        body = res.json()
        assert len(body) == 1
        assert body[0]["provider"] == "telnyx"
        assert body[0]["phone_number"] == "+13015550100"
        assert body[0]["monthly_cost"] == 1.0
        assert body[0]["capabilities"] == {"voice": True, "sms": True, "mms": False}

    async def test_two_carriers_require_a_choice(
        self, client, owner, telnyx_connected, twilio_connected
    ):
        res = await as_user(client, owner).get("/api/v1/phone-numbers/search")
        assert res.status_code == 400
        assert "Choose which one" in res.json()["detail"]

    async def test_explicit_provider_selects_that_carrier(
        self, client, owner, telnyx_connected, twilio_connected
    ):
        res = await as_user(client, owner).get(
            "/api/v1/phone-numbers/search?provider=twilio&area_code=415"
        )
        assert res.status_code == 200
        assert res.json()[0]["provider"] == "twilio"
        assert calls_for("twilio", "GET", "AvailablePhoneNumbers")
        assert not calls_for("telnyx")

    async def test_unconnected_carrier_is_refused(
        self, client, owner, telnyx_connected
    ):
        res = await as_user(client, owner).get(
            "/api/v1/phone-numbers/search?provider=twilio"
        )
        assert res.status_code == 400
        assert "not connected" in res.json()["detail"]
        assert not calls_for("twilio")


# ---------- purchase ----------


@pytest.mark.integration
@pytest.mark.asyncio
class TestPurchase:
    async def test_purchase_on_telnyx_records_carrier_and_connection(
        self, client, owner, agent, telnyx_connected, db_session
    ):
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={
                "phone_number": "+13015550100",
                "agent_id": str(agent.id),
                "provider": "telnyx",
                "connection_id": str(telnyx_connected.id),
                "country_code": "US",
                "area_code": "301",
                "monthly_cost": 1.0,
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["provider"] == "telnyx"
        assert body["phone_number"] == "+13015550100"
        assert body["monthly_cost"] == 1.0
        assert body["agent_id"] == str(agent.id)

        row = (
            await db_session.execute(
                select(PhoneNumber).where(PhoneNumber.phone_number == "+13015550100")
            )
        ).scalar_one()
        assert row.provider == "telnyx"
        assert row.provider_sid == "num-telnyx-1"
        assert row.integration_connection_id == telnyx_connected.id
        assert row.provider_metadata["texml_application_id"] == "app-1"
        assert row.user_id == owner.id

    async def test_telnyx_number_is_attached_to_an_app_holding_the_agent_url(
        self, client, owner, agent, telnyx_connected
    ):
        """Without this attachment an inbound call reaches nothing."""
        await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={
                "phone_number": "+13015550100",
                "agent_id": str(agent.id),
                "provider": "telnyx",
            },
        )
        created = calls_for("telnyx", "POST", "/v2/texml_applications")[0]
        assert created["json_body"]["voice_url"].endswith(
            f"/api/v1/telephony/telnyx/voice/{agent.id}"
        )
        order = calls_for("telnyx", "POST", "/v2/number_orders")[0]
        assert order["json_body"]["connection_id"] == "app-1"
        attach = calls_for("telnyx", "PATCH")[0]
        assert attach["json_body"] == {"connection_id": "app-1"}

    async def test_purchase_on_twilio_sets_voice_webhook(
        self, client, owner, agent, twilio_connected, db_session
    ):
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={
                "phone_number": "+14155550100",
                "agent_id": str(agent.id),
                "provider": "twilio",
            },
        )
        assert res.status_code == 201, res.text
        assert res.json()["provider"] == "twilio"

        form = calls_for("twilio", "POST", "IncomingPhoneNumbers")[0]["form"]
        assert form["PhoneNumber"] == "+14155550100"
        assert form["VoiceUrl"].endswith(f"/api/v1/telephony/twilio/voice/{agent.id}")

        row = (
            await db_session.execute(
                select(PhoneNumber).where(PhoneNumber.phone_number == "+14155550100")
            )
        ).scalar_one()
        assert row.provider_sid == "PN_purchased"

    async def test_purchase_routes_to_the_chosen_carrier_only(
        self, client, owner, agent, telnyx_connected, twilio_connected
    ):
        """With both connected, buying on Telnyx must not touch Twilio."""
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={
                "phone_number": "+13015550100",
                "agent_id": str(agent.id),
                "provider": "telnyx",
            },
        )
        assert res.status_code == 201
        assert not calls_for("twilio")

    async def test_purchase_without_choosing_is_refused_when_both_connected(
        self, client, owner, agent, telnyx_connected, twilio_connected
    ):
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={"phone_number": "+13015550100", "agent_id": str(agent.id)},
        )
        assert res.status_code == 400
        assert not calls_for("telnyx", "POST", "/v2/number_orders")

    async def test_duplicate_number_is_rejected_before_any_carrier_call(
        self, client, owner, agent, telnyx_connected
    ):
        payload = {
            "phone_number": "+13015550100",
            "agent_id": str(agent.id),
            "provider": "telnyx",
        }
        first = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision", json=payload
        )
        assert first.status_code == 201

        CARRIER_CALLS.clear()
        second = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision", json=payload
        )
        assert second.status_code == 400
        assert "already provisioned" in second.json()["detail"]
        assert CARRIER_CALLS == []

    async def test_cannot_buy_a_number_for_someone_elses_agent(
        self, client, other_user, agent, telnyx_connected, db_session
    ):
        await _connect_carrier(db_session, other_user, "telnyx", "Telnyx")
        res = await as_user(client, other_user).post(
            "/api/v1/phone-numbers/provision",
            json={
                "phone_number": "+13015550100",
                "agent_id": str(agent.id),
                "provider": "telnyx",
            },
        )
        assert res.status_code == 404
        assert CARRIER_CALLS == []


# ---------- reassign + release ----------


@pytest_asyncio.fixture
async def telnyx_number(client, owner, agent, telnyx_connected, db_session) -> PhoneNumber:
    """A number already bought on Telnyx."""
    res = await as_user(client, owner).post(
        "/api/v1/phone-numbers/provision",
        json={
            "phone_number": "+13015550100",
            "agent_id": str(agent.id),
            "provider": "telnyx",
        },
    )
    assert res.status_code == 201, res.text
    CARRIER_CALLS.clear()
    return (
        await db_session.execute(
            select(PhoneNumber).where(PhoneNumber.phone_number == "+13015550100")
        )
    ).scalar_one()


@pytest.mark.integration
@pytest.mark.asyncio
class TestReassignAndRelease:
    async def test_reassigning_repoints_the_carrier_webhook(
        self, client, owner, telnyx_number, second_agent
    ):
        res = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{telnyx_number.id}",
            json={"agent_id": str(second_agent.id)},
        )
        assert res.status_code == 200, res.text
        assert res.json()["agent_id"] == str(second_agent.id)

        created = calls_for("telnyx", "POST", "/v2/texml_applications")
        assert created, "a TeXML app for the new agent should have been created"
        assert created[0]["json_body"]["voice_url"].endswith(
            f"/api/v1/telephony/telnyx/voice/{second_agent.id}"
        )

    async def test_release_goes_back_to_the_buying_carrier(
        self, client, owner, telnyx_number, db_session
    ):
        res = await as_user(client, owner).delete(
            f"/api/v1/phone-numbers/{telnyx_number.id}"
        )
        assert res.status_code == 204

        assert calls_for("telnyx", "DELETE"), "number should be released at Telnyx"
        assert not calls_for("twilio")

        remaining = (
            await db_session.execute(
                select(PhoneNumber).where(PhoneNumber.id == telnyx_number.id)
            )
        ).scalar_one_or_none()
        assert remaining is None

    async def test_another_user_cannot_release_the_number(
        self, client, other_user, telnyx_number
    ):
        res = await as_user(client, other_user).delete(
            f"/api/v1/phone-numbers/{telnyx_number.id}"
        )
        assert res.status_code == 404
        assert CARRIER_CALLS == []

    async def test_listing_shows_the_purchased_number(
        self, client, owner, telnyx_number
    ):
        res = await as_user(client, owner).get("/api/v1/phone-numbers")
        assert res.status_code == 200
        body = res.json()
        assert [n["phone_number"] for n in body] == ["+13015550100"]
        assert body[0]["provider"] == "telnyx"

    async def test_another_user_does_not_see_the_number(
        self, client, other_user, telnyx_number
    ):
        res = await as_user(client, other_user).get("/api/v1/phone-numbers")
        assert res.json() == []


# ---------- step 0: connecting the carrier in the first place ----------


@pytest.fixture
def carrier_auth_probe(monkeypatch):
    """
    Capture the request `IntegrationManager.test_connection` sends to the
    carrier, and answer 200 so the connection is stored.

    The credential must arrive in the scheme the carrier expects — a bare key in
    the Authorization header is unparseable, and the connection would be
    rejected even with valid credentials.
    """
    seen: dict = {}

    class _FakeResponse:
        status_code = 200
        text = "{}"

        @staticmethod
        def json():
            return {}

    class _FakeClient:
        async def get(self, url, headers=None, params=None):
            seen["url"] = url
            seen["headers"] = headers or {}
            seen["params"] = params or {}
            return _FakeResponse()

    from app.services.integrations.integration_manager import IntegrationManager

    async def fake_get_http_client(self):
        return _FakeClient()

    monkeypatch.setattr(IntegrationManager, "_get_http_client", fake_get_http_client)
    return seen


async def _seed_connector(db_session, slug: str, name: str, auth_config: dict, base_url: str):
    """Create a connector row matching what scripts/seed_data.py installs."""
    connector = IntegrationConnector(
        name=name,
        slug=slug,
        category="phone",
        auth_type="api_key",
        base_url=base_url,
        auth_config=auth_config,
        is_active=True,
    )
    db_session.add(connector)
    await db_session.commit()
    await db_session.refresh(connector)
    return connector


@pytest.mark.integration
@pytest.mark.asyncio
class TestConnectingACarrier:
    async def test_connect_telnyx_then_it_appears_as_a_provider(
        self, client, owner, db_session, carrier_auth_probe
    ):
        connector = await _seed_connector(
            db_session,
            "telnyx",
            "Telnyx",
            {
                "api_key_location": "header",
                "api_key_name": "Authorization",
                "api_key_format": "Bearer {api_key}",
                "test_endpoint": "/v2/phone_numbers",
            },
            "https://api.telnyx.com",
        )

        res = await as_user(client, owner).post(
            "/api/v1/integrations/connections",
            json={
                "connector_id": str(connector.id),
                "name": "Telnyx Connection",
                "api_key_auth": {
                    "api_key": "KEY_real_looking_key",
                    "additional_fields": {"sip_connection_id": "sip-1"},
                },
            },
        )
        assert res.status_code == 201, res.text

        # The credential must be sent as "Bearer <key>", not bare.
        assert carrier_auth_probe["headers"]["Authorization"] == "Bearer KEY_real_looking_key"
        assert carrier_auth_probe["url"] == "https://api.telnyx.com/v2/phone_numbers"

        providers = await as_user(client, owner).get("/api/v1/phone-numbers/providers")
        assert [p["slug"] for p in providers.json()] == ["telnyx"]

    async def test_connect_twilio_sends_basic_auth_and_enables_purchasing(
        self, client, owner, agent, db_session, carrier_auth_probe
    ):
        connector = await _seed_connector(
            db_session,
            "twilio",
            "Twilio",
            {
                "api_key_location": "header",
                "api_key_name": "Authorization",
                "api_key_format": "Basic {api_key}",
                "test_endpoint": "/2010-04-01/Accounts.json",
            },
            "https://api.twilio.com",
        )

        packed = base64.b64encode(b"ACrealsid:realtoken").decode()
        res = await as_user(client, owner).post(
            "/api/v1/integrations/connections",
            json={
                "connector_id": str(connector.id),
                "name": "Twilio Connection",
                "api_key_auth": {
                    "api_key": packed,
                    "additional_fields": {"account_sid": "ACrealsid"},
                },
            },
        )
        assert res.status_code == 201, res.text
        assert carrier_auth_probe["headers"]["Authorization"] == f"Basic {packed}"

        # And the freshly connected account can immediately buy a number.
        bought = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={
                "phone_number": "+14155550100",
                "agent_id": str(agent.id),
                "provider": "twilio",
            },
        )
        assert bought.status_code == 201, bought.text
        assert bought.json()["provider"] == "twilio"

    async def test_query_located_api_keys_go_in_the_query_string(
        self, client, owner, db_session, carrier_auth_probe
    ):
        """Vonage-style connectors authenticate by query parameter, not header."""
        connector = await _seed_connector(
            db_session,
            "vonage",
            "Vonage",
            {
                "api_key_location": "query",
                "api_key_name": "api_key",
                "test_endpoint": "/v1/account/get-balance",
            },
            "https://api.nexmo.com",
        )

        res = await as_user(client, owner).post(
            "/api/v1/integrations/connections",
            json={
                "connector_id": str(connector.id),
                "name": "Vonage Connection",
                "api_key_auth": {"api_key": "vonage_key"},
            },
        )
        assert res.status_code == 201, res.text
        assert carrier_auth_probe["params"] == {"api_key": "vonage_key"}
        assert "Authorization" not in carrier_auth_probe["headers"]
