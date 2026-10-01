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

from app.core.config import settings
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
    await _subscribe(db_session, org)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _subscribe(db_session, org) -> None:
    """Put the workspace on a live paid plan that may buy numbers.

    Without it every purchase answered 402 before reaching the code under
    test, so these tests were checking the entitlement guard, not purchasing.
    """
    from datetime import datetime, timedelta
    from decimal import Decimal

    from app.models.subscription import Subscription, SubscriptionPlan
    from app.services.billing import catalog

    plan = (
        await db_session.execute(select(SubscriptionPlan).where(SubscriptionPlan.slug == "voice-ai"))
    ).scalar_one_or_none()
    if plan is None:
        plan = SubscriptionPlan(
            name="Voice AI",
            slug="voice-ai",
            stripe_product_id="prod_test_voice_ai",
            stripe_price_id="price_test_voice_ai",
            price_monthly=Decimal("120.00"),
            entitlements=catalog.entitlements_for_plan("voice-ai"),
        )
        db_session.add(plan)
        await db_session.flush()
    now = datetime.utcnow()
    db_session.add(
        Subscription(
            organization_id=org.id,
            plan_id=plan.id,
            status="active",
            billing_period="monthly",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
    )


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
    await _subscribe(db_session, org)
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


@pytest.fixture(autouse=True)
def no_platform_twilio(monkeypatch):
    """
    Default: the server holds no Twilio credentials of its own, and is reachable
    at a public URL (without one, purchases are refused outright).

    Pinned rather than inherited from the environment, so the suite behaves the
    same on a machine that has real platform credentials in `.env`.
    """
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", None)
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", None)
    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.voicecon.test")


@pytest.fixture
def platform_twilio(monkeypatch):
    """The deployment has its own Twilio account — Voicecon's shared account."""
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC_platform_sid")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "platform_auth_token")


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
        """With no platform account either, there is nowhere to buy from."""
        res = await as_user(client, owner).get("/api/v1/phone-numbers/providers")
        assert res.status_code == 200
        assert res.json() == []

    async def test_voicecon_numbers_are_offered_without_naming_the_carrier(
        self, client, owner, platform_twilio
    ):
        """Voicecon's own account is a purchase option, not a listed carrier."""
        res = await as_user(client, owner).get("/api/v1/phone-numbers/providers")
        assert res.status_code == 200
        assert res.json() == []

        res = await as_user(client, owner).get("/api/v1/phone-numbers/purchase-options")
        assert res.status_code == 200
        body = res.json()
        assert body["voicecon_available"] is True
        assert body["own_providers"] == []
        assert "twilio" not in str({k: v for k, v in body.items() if k != "supported_providers"}).lower()
        assert {p["slug"]: p["connected"] for p in body["supported_providers"]} == {
            "twilio": False, "telnyx": False,
        }

    async def test_own_twilio_is_listed_as_the_users_provider(
        self, client, owner, twilio_connected, platform_twilio
    ):
        """Connecting your own Twilio adds it to the own-provider flow only."""
        res = await as_user(client, owner).get("/api/v1/phone-numbers/providers")
        body = res.json()
        assert [(p["slug"], p["source"]) for p in body] == [("twilio", "integration")]
        assert body[0]["connection_id"] == str(twilio_connected.id)
        assert body[0]["is_default"] is True

        options = (await as_user(client, owner).get("/api/v1/phone-numbers/purchase-options")).json()
        assert options["voicecon_available"] is True
        assert [p["connection_id"] for p in options["own_providers"]] == [str(twilio_connected.id)]
        assert {p["slug"]: p["connected"] for p in options["supported_providers"]}["twilio"] is True

    async def test_voicecon_unavailable_without_platform_credentials(
        self, client, owner, telnyx_connected
    ):
        options = (await as_user(client, owner).get("/api/v1/phone-numbers/purchase-options")).json()
        assert options["voicecon_available"] is False
        assert [p["slug"] for p in options["own_providers"]] == ["telnyx"]

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

    async def test_twilio_is_searched_by_default(
        self, client, owner, telnyx_connected, twilio_connected
    ):
        """Twilio is the default carrier, so it is used when none is named."""
        res = await as_user(client, owner).get("/api/v1/phone-numbers/search")
        assert res.status_code == 200
        assert res.json()[0]["provider"] == "twilio"
        assert not calls_for("telnyx")

    async def test_voicecon_search_uses_our_account_and_hides_the_carrier(
        self, client, owner, twilio_connected, platform_twilio
    ):
        res = await as_user(client, owner).get(
            "/api/v1/phone-numbers/search?source=voicecon&area_code=415"
        )
        assert res.status_code == 200, res.text
        assert res.json() and all(n["provider"] == "voicecon" for n in res.json())
        assert "twilio" not in res.text.lower()

    async def test_voicecon_search_without_our_account_is_a_plain_message(
        self, client, owner, telnyx_connected
    ):
        res = await as_user(client, owner).get("/api/v1/phone-numbers/search?source=voicecon")
        assert res.status_code == 400
        detail = res.json()["detail"]
        assert "Voicecon numbers aren't available" in detail
        assert "twilio" not in detail.lower() and "telnyx" not in detail.lower()
        assert not calls_for("telnyx")

    async def test_own_search_never_touches_our_account(
        self, client, owner, telnyx_connected, platform_twilio
    ):
        res = await as_user(client, owner).get(
            f"/api/v1/phone-numbers/search?source=own&connection_id={telnyx_connected.id}&area_code=301"
        )
        assert res.status_code == 200, res.text
        assert res.json()[0]["provider"] == "telnyx"
        assert not calls_for("twilio")

    async def test_own_search_refuses_our_account_id(
        self, client, owner, telnyx_connected, platform_twilio
    ):
        res = await as_user(client, owner).get(
            "/api/v1/phone-numbers/search?source=own&connection_id=platform:twilio"
        )
        assert res.status_code == 400

    async def test_contains_must_be_digits(self, client, owner, platform_twilio):
        res = await as_user(client, owner).get("/api/v1/phone-numbers/search?source=voicecon&contains=abc")
        assert res.status_code == 400
        assert "digits" in res.json()["detail"]

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
        assert "not available" in res.json()["detail"]
        assert not calls_for("twilio")

    async def test_platform_account_searches_on_server_credentials(
        self, client, owner, platform_twilio
    ):
        """No integration connected — the shared account still finds numbers."""
        res = await as_user(client, owner).get(
            "/api/v1/phone-numbers/search?area_code=415"
        )
        assert res.status_code == 200
        assert res.json()[0]["phone_number"] == "+14155550100"
        # The request went to the platform account, not a user's.
        assert "AC_platform_sid" in calls_for("twilio", "GET")[0]["path"]

    async def test_own_twilio_wins_over_the_platform_account(
        self, client, owner, twilio_connected, platform_twilio
    ):
        """Asking for Twilio spends the user's own credit, not Voicecon's."""
        res = await as_user(client, owner).get("/api/v1/phone-numbers/search?provider=twilio")
        assert res.status_code == 200
        assert "ACfakesid" in calls_for("twilio", "GET")[0]["path"]

    async def test_platform_account_can_be_chosen_explicitly(
        self, client, owner, twilio_connected, platform_twilio
    ):
        """Both accounts are offered, so the user must be able to pick ours."""
        res = await as_user(client, owner).get(
            "/api/v1/phone-numbers/search?provider=twilio&connection_id=platform:twilio"
        )
        assert res.status_code == 200
        assert "AC_platform_sid" in calls_for("twilio", "GET")[0]["path"]


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

    async def test_voicecon_purchase_never_names_the_carrier(
        self, client, owner, agent, twilio_connected, platform_twilio
    ):
        """source=voicecon buys on our account even when the user has their own."""
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={"phone_number": "+14155550100", "agent_id": str(agent.id), "source": "voicecon"},
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["source"] == "voicecon"
        assert body["provider"] == "voicecon"
        assert body["provider_sid"] is None
        assert "AC_platform_sid" in calls_for("twilio", "POST", "IncomingPhoneNumbers")[0]["path"]

        listed = (await as_user(client, owner).get("/api/v1/phone-numbers")).json()
        assert [(n["source"], n["provider"], n["provider_sid"]) for n in listed] == [
            ("voicecon", "voicecon", None)
        ]
        assert "twilio" not in str(listed).lower()

    async def test_own_purchase_shows_the_users_carrier(
        self, client, owner, agent, telnyx_connected, platform_twilio
    ):
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={
                "phone_number": "+13015550100",
                "agent_id": str(agent.id),
                "source": "own",
                "connection_id": str(telnyx_connected.id),
            },
        )
        assert res.status_code == 201, res.text
        assert (res.json()["source"], res.json()["provider"]) == ("own", "telnyx")
        assert not calls_for("twilio")

    async def test_voicecon_carrier_failure_is_a_plain_message(
        self, client, owner, agent, platform_twilio, monkeypatch
    ):
        from app.services.telephony.providers import NumberProviderError

        async def outage(self, method, path, **kwargs):
            raise NumberProviderError(
                "Twilio: 503 Service Unavailable at api.twilio.com (AC_platform_sid)",
                public_message="Twilio is having problems right now. Try again shortly.",
                status_code=503,
            )

        monkeypatch.setattr(NumberProvider, "_request", outage)
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={"phone_number": "+14155550100", "agent_id": str(agent.id), "source": "voicecon"},
        )
        # 502 leaves the app as 503 (see main.py), with our message intact.
        assert res.status_code == 503
        assert res.json()["detail"] == "Unable to complete the purchase. Please try again or contact support."

        res = await as_user(client, owner).get("/api/v1/phone-numbers/search?source=voicecon")
        assert res.status_code == 503
        assert res.json()["detail"] == "We couldn't load available numbers right now. Please try again."

    async def test_a_taken_number_says_so(self, client, owner, agent, platform_twilio, monkeypatch):
        from app.services.telephony.providers import NumberProviderError

        async def gone(self, method, path, **kwargs):
            if method == "POST" and "IncomingPhoneNumbers" in path:
                raise NumberProviderError("Twilio: 21422 number not available", public_message="x", status_code=400)
            return None

        monkeypatch.setattr(NumberProvider, "_request", gone)
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={"phone_number": "+14155550100", "agent_id": str(agent.id), "source": "voicecon"},
        )
        assert res.status_code == 409
        assert res.json()["detail"] == "That number is no longer available. Please choose another one."

    async def test_purchase_on_the_platform_account_records_no_connection(
        self, client, owner, agent, platform_twilio, db_session
    ):
        """
        A number bought on the shared account belongs to no user connection —
        but which account it came from has to survive, or a later release would
        be aimed at the wrong Twilio.
        """
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={
                "phone_number": "+14155550100",
                "agent_id": str(agent.id),
                "provider": "twilio",
                "connection_id": "platform:twilio",
            },
        )
        assert res.status_code == 201, res.text

        bought = calls_for("twilio", "POST", "IncomingPhoneNumbers")[0]
        assert "AC_platform_sid" in bought["path"]

        row = (
            await db_session.execute(
                select(PhoneNumber).where(PhoneNumber.phone_number == "+14155550100")
            )
        ).scalar_one()
        assert row.integration_connection_id is None
        assert row.provider_metadata["credential_source"] == "platform"
        assert row.user_id == owner.id

    async def test_purchase_on_own_twilio_records_the_connection(
        self, client, owner, agent, twilio_connected, platform_twilio, db_session
    ):
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={
                "phone_number": "+14155550100",
                "agent_id": str(agent.id),
                "provider": "twilio",
                "connection_id": str(twilio_connected.id),
            },
        )
        assert res.status_code == 201, res.text

        bought = calls_for("twilio", "POST", "IncomingPhoneNumbers")[0]
        assert "ACfakesid" in bought["path"]

        row = (
            await db_session.execute(
                select(PhoneNumber).where(PhoneNumber.phone_number == "+14155550100")
            )
        ).scalar_one()
        assert row.integration_connection_id == twilio_connected.id
        assert row.provider_metadata["credential_source"] == "integration"

    async def test_platform_number_is_released_from_the_platform_account(
        self, client, owner, agent, twilio_connected, platform_twilio
    ):
        """
        The dangerous case: the user has since connected their own Twilio. The
        release must still go to the account that actually owns the number.
        """
        bought = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={
                "phone_number": "+14155550100",
                "agent_id": str(agent.id),
                "provider": "twilio",
                "connection_id": "platform:twilio",
            },
        )
        assert bought.status_code == 201, bought.text
        CARRIER_CALLS.clear()

        res = await as_user(client, owner).delete(
            f"/api/v1/phone-numbers/{bought.json()['id']}"
        )
        assert res.status_code == 204

        released = calls_for("twilio", "DELETE")
        assert released, "number should be released at Twilio"
        assert "AC_platform_sid" in released[0]["path"]

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

    async def test_purchase_without_choosing_uses_twilio(
        self, client, owner, agent, telnyx_connected, twilio_connected
    ):
        """Twilio is the default carrier, so an unqualified purchase lands there."""
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={"phone_number": "+14155550100", "agent_id": str(agent.id)},
        )
        assert res.status_code == 201, res.text
        assert res.json()["provider"] == "twilio"
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
        assert "already in use" in second.json()["detail"]
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

    async def test_an_incoming_call_reaches_the_newly_assigned_agent(
        self, client, owner, agent, telnyx_number, second_agent, db_session
    ):
        """Calls follow the saved assignment, even through a webhook URL that
        still names the old agent (a carrier update that never landed)."""
        from app.models.call import Call

        res = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{telnyx_number.id}",
            json={"agent_id": str(second_agent.id)},
        )
        assert res.status_code == 200, res.text

        answer = await client.post(
            f"/api/v1/telephony/telnyx/voice/{agent.id}",  # the OLD agent's URL
            data={
                "CallSid": "CA-reassigned-1",
                "From": "+15550009999",
                "To": telnyx_number.phone_number,
                "CallStatus": "ringing",
            },
        )
        assert answer.status_code == 200, answer.text
        assert "Stream" in answer.text or "stream" in answer.text, answer.text

        call = (
            await db_session.execute(select(Call).where(Call.provider_call_sid == "CA-reassigned-1"))
        ).scalar_one()
        assert call.agent_id == second_agent.id
        assert call.direction == "inbound"

    async def test_reassigning_one_number_leaves_the_others_alone(
        self, client, owner, agent, telnyx_number, second_agent, db_session
    ):
        other = PhoneNumber(
            user_id=owner.id,
            organization_id=telnyx_number.organization_id,
            agent_id=agent.id,
            phone_number="+13015550199",
            provider="telnyx",
            status="active",
        )
        db_session.add(other)
        await db_session.commit()

        res = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{telnyx_number.id}",
            json={"agent_id": str(second_agent.id)},
        )
        assert res.status_code == 200, res.text

        await db_session.refresh(other)
        assert other.agent_id == agent.id
        listed = {
            n["phone_number"]: n["agent_id"]
            for n in (await as_user(client, owner).get("/api/v1/phone-numbers")).json()
        }
        assert listed == {
            "+13015550100": str(second_agent.id),
            "+13015550199": str(agent.id),
        }

    async def test_picking_the_current_agent_does_not_touch_the_carrier(
        self, client, owner, agent, telnyx_number
    ):
        res = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{telnyx_number.id}",
            json={"agent_id": str(agent.id)},
        )
        assert res.status_code == 200, res.text
        assert res.json()["agent_id"] == str(agent.id)
        assert CARRIER_CALLS == []

    async def test_a_turned_off_agent_cannot_take_the_number(
        self, client, owner, agent, telnyx_number, second_agent, db_session
    ):
        second_agent.is_active = False
        await db_session.commit()

        res = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{telnyx_number.id}",
            json={"agent_id": str(second_agent.id)},
        )
        assert res.status_code == 400
        assert "turned off" in res.json()["detail"]
        await db_session.refresh(telnyx_number)
        assert telnyx_number.agent_id == agent.id
        assert CARRIER_CALLS == []

    async def test_a_carrier_failure_keeps_the_old_agent(
        self, client, owner, agent, telnyx_number, second_agent, db_session, monkeypatch
    ):
        from app.services.telephony.providers.base import NumberProviderError

        async def refuse(self, method, path, **kwargs):
            raise NumberProviderError("carrier is down")

        monkeypatch.setattr(NumberProvider, "_request", refuse)

        res = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{telnyx_number.id}",
            json={"agent_id": str(second_agent.id)},
        )
        assert res.status_code >= 400
        await db_session.refresh(telnyx_number)
        assert telnyx_number.agent_id == agent.id

    async def test_another_workspaces_agent_is_refused(
        self, client, owner, other_user, telnyx_number, db_session
    ):
        foreign = Agent(
            user_id=other_user.id,
            organization_id=await _org_id_of(db_session, other_user),
            name="Not yours",
            system_prompt="x",
        )
        db_session.add(foreign)
        await db_session.commit()

        res = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{telnyx_number.id}",
            json={"agent_id": str(foreign.id)},
        )
        assert res.status_code == 404
        assert CARRIER_CALLS == []

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


# ---------- onboarding never buys a number ----------


@pytest.mark.integration
@pytest.mark.asyncio
class TestOnboardingDoesNotSellNumbers:
    """Numbers are bought on the Phone Numbers page, behind a paid plan."""

    async def test_the_claim_route_is_gone(self, client, owner, platform_twilio):
        res = await as_user(client, owner).post(
            "/api/v1/onboarding/phone-number",
            json={"phone_number": "+14155550100", "assistant_name": "Aria"},
        )
        assert res.status_code in (404, 405)
        assert not calls_for("twilio", "POST")


# ---------- numbers already on the user's own account ----------


OWN_TWILIO_NUMBERS = {
    "incoming_phone_numbers": [
        {
            "sid": "PN_existing_1",
            "phone_number": "+12125550101",
            "friendly_name": "Main line",
            "capabilities": {"voice": True, "sms": True},
            "voice_url": "https://their-old-ivr.example.com/voice",
        },
        {
            "sid": "PN_existing_2",
            "phone_number": "+12125550102",
            "friendly_name": "Support",
            "capabilities": {"voice": True, "sms": False},
            "voice_url": "",
        },
    ],
    "next_page_uri": None,
}


@pytest.fixture
def own_twilio_account(monkeypatch):
    """A connected Twilio account that already holds two numbers."""
    CARRIER_CALLS.clear()

    async def fake_request(self, method, path, **kwargs):
        CARRIER_CALLS.append({"provider": self.slug, "method": method, "path": path, **kwargs})
        if method == "GET" and path.endswith("IncomingPhoneNumbers.json"):
            return OWN_TWILIO_NUMBERS
        if method == "POST" and "IncomingPhoneNumbers/" in path:
            return None  # webhook update
        raise AssertionError(f"unexpected call: {method} {path}")

    monkeypatch.setattr(NumberProvider, "_request", fake_request)
    return CARRIER_CALLS


@pytest.mark.integration
@pytest.mark.asyncio
class TestOwnAccountNumbers:
    async def test_existing_numbers_on_the_account_are_listed(
        self, client, owner, twilio_connected, own_twilio_account
    ):
        res = await as_user(client, owner).get(
            "/api/v1/phone-numbers/own-numbers",
            params={"connection_id": str(twilio_connected.id)},
        )
        assert res.status_code == 200, res.text
        body = {n["phone_number"]: n for n in res.json()}
        assert set(body) == {"+12125550101", "+12125550102"}
        assert body["+12125550101"]["available"] is True
        assert body["+12125550101"]["phone_number_id"] is None
        assert body["+12125550102"]["capabilities"]["sms"] is False

    async def test_import_with_an_agent_points_the_number_at_it(
        self, client, owner, agent, twilio_connected, own_twilio_account, db_session
    ):
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/import",
            json={
                "connection_id": str(twilio_connected.id),
                "phone_number": "+12125550101",
                "agent_id": str(agent.id),
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["agent_id"] == str(agent.id)
        assert body["source"] == "own"
        assert body["imported"] is True
        assert body["provider"] == "twilio"

        update = calls_for("twilio", "POST", "IncomingPhoneNumbers/PN_existing_1")[0]
        assert update["form"]["VoiceUrl"].endswith(f"/api/v1/telephony/twilio/voice/{agent.id}")

        row = (
            await db_session.execute(
                select(PhoneNumber).where(PhoneNumber.phone_number == "+12125550101")
            )
        ).scalar_one()
        assert row.integration_connection_id == twilio_connected.id
        assert row.provider_metadata["original_voice_url"] == "https://their-old-ivr.example.com/voice"

        listed = await as_user(client, owner).get(
            "/api/v1/phone-numbers/own-numbers",
            params={"connection_id": str(twilio_connected.id)},
        )
        imported = next(n for n in listed.json() if n["phone_number"] == "+12125550101")
        assert imported["phone_number_id"] == str(row.id)
        assert imported["available"] is False

    async def test_import_without_an_agent_touches_nothing_at_the_carrier(
        self, client, owner, twilio_connected, own_twilio_account
    ):
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/import",
            json={"connection_id": str(twilio_connected.id), "phone_number": "+12125550102"},
        )
        assert res.status_code == 201, res.text
        assert res.json()["agent_id"] is None
        assert not calls_for("twilio", "POST")

    async def test_a_number_not_on_the_account_is_refused(
        self, client, owner, twilio_connected, own_twilio_account
    ):
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/import",
            json={"connection_id": str(twilio_connected.id), "phone_number": "+19995550000"},
        )
        assert res.status_code == 404

    async def test_importing_twice_is_refused(
        self, client, owner, twilio_connected, own_twilio_account
    ):
        payload = {"connection_id": str(twilio_connected.id), "phone_number": "+12125550102"}
        assert (await as_user(client, owner).post("/api/v1/phone-numbers/import", json=payload)).status_code == 201
        again = await as_user(client, owner).post("/api/v1/phone-numbers/import", json=payload)
        assert again.status_code == 409

    async def test_another_users_connection_cannot_be_used(
        self, client, other_user, twilio_connected, own_twilio_account
    ):
        res = await as_user(client, other_user).get(
            "/api/v1/phone-numbers/own-numbers",
            params={"connection_id": str(twilio_connected.id)},
        )
        assert res.status_code == 400
        assert not own_twilio_account

    async def test_attach_detach_and_reattach(
        self, client, owner, agent, second_agent, twilio_connected, own_twilio_account
    ):
        imported = await as_user(client, owner).post(
            "/api/v1/phone-numbers/import",
            json={"connection_id": str(twilio_connected.id), "phone_number": "+12125550102"},
        )
        number_id = imported.json()["id"]

        attached = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{number_id}", json={"agent_id": str(agent.id)}
        )
        assert attached.status_code == 200, attached.text
        assert attached.json()["agent_id"] == str(agent.id)

        detached = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{number_id}", json={"agent_id": None}
        )
        assert detached.status_code == 200, detached.text
        assert detached.json()["agent_id"] is None

        reattached = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{number_id}", json={"agent_id": str(second_agent.id)}
        )
        assert reattached.json()["agent_id"] == str(second_agent.id)
        last = calls_for("twilio", "POST", "IncomingPhoneNumbers/PN_existing_2")[-1]
        assert last["form"]["VoiceUrl"].endswith(f"/voice/{second_agent.id}")

    async def test_removing_an_imported_number_never_releases_it(
        self, client, owner, agent, twilio_connected, own_twilio_account, db_session
    ):
        imported = await as_user(client, owner).post(
            "/api/v1/phone-numbers/import",
            json={
                "connection_id": str(twilio_connected.id),
                "phone_number": "+12125550101",
                "agent_id": str(agent.id),
            },
        )
        own_twilio_account.clear()

        res = await as_user(client, owner).delete(f"/api/v1/phone-numbers/{imported.json()['id']}")
        assert res.status_code == 204

        assert not calls_for("twilio", "DELETE"), "an imported number must stay on the user's account"
        restore = calls_for("twilio", "POST", "IncomingPhoneNumbers/PN_existing_1")[0]
        assert restore["form"]["VoiceUrl"] == "https://their-old-ivr.example.com/voice"
        remaining = (
            await db_session.execute(
                select(PhoneNumber).where(PhoneNumber.phone_number == "+12125550101")
            )
        ).scalar_one_or_none()
        assert remaining is None


@pytest.mark.integration
@pytest.mark.asyncio
class TestDetach:
    async def test_a_detached_number_stops_answering(
        self, client, owner, agent, telnyx_number
    ):
        res = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{telnyx_number.id}", json={"agent_id": None}
        )
        assert res.status_code == 200, res.text
        assert res.json()["agent_id"] is None
        assert CARRIER_CALLS == []

        answer = await client.post(
            f"/api/v1/telephony/telnyx/voice/{agent.id}",  # the carrier still names the old agent
            data={
                "CallSid": "CA-detached-1",
                "From": "+15550009999",
                "To": telnyx_number.phone_number,
                "CallStatus": "ringing",
            },
        )
        assert answer.status_code == 200
        assert "not available" in answer.text

    async def test_leaving_agent_out_keeps_it(self, client, owner, agent, telnyx_number):
        res = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{telnyx_number.id}", json={"status": "active"}
        )
        assert res.status_code == 200, res.text
        assert res.json()["agent_id"] == str(agent.id)


@pytest.fixture
def own_telnyx_account(monkeypatch):
    """
    A connected Telnyx account holding numbers across two pages: one routed
    through the customer's own SIP connection, one routed nowhere.
    """
    CARRIER_CALLS.clear()
    texml_apps: dict = {"https://their-pbx.example.com/texml": "app-theirs"}
    pages = {
        1: [{"id": "num-own-1", "phone_number": "+13125550101", "status": "active",
             "connection_id": "conn-sip-1", "customer_reference": "Front desk"}],
        2: [{"id": "num-own-2", "phone_number": "+13125550102", "status": "active",
             "connection_id": None}],
    }

    async def fake_request(self, method, path, **kwargs):
        CARRIER_CALLS.append({"provider": self.slug, "method": method, "path": path, **kwargs})
        key = f"{method} {path}"
        if key == "GET /v2/phone_numbers":
            params = kwargs.get("params") or {}
            if "filter[phone_number]" in params:
                match = [n for page in pages.values() for n in page
                         if n["phone_number"] == params["filter[phone_number]"]]
                return {"data": match}
            return {"data": pages.get(params.get("page[number]", 1), []),
                    "meta": {"total_pages": len(pages)}}
        if key == "GET /v2/texml_applications":
            return {"data": [{"id": i, "voice_url": u} for u, i in texml_apps.items()]}
        if key == "POST /v2/texml_applications":
            url = kwargs["json_body"]["voice_url"]
            texml_apps[url] = f"app-{len(texml_apps) + 1}"
            return {"data": {"id": texml_apps[url]}}
        if method == "PATCH" and path.startswith("/v2/phone_numbers/"):
            return {"data": {}}
        raise AssertionError(f"unexpected call: {key}")

    monkeypatch.setattr(NumberProvider, "_request", fake_request)
    return CARRIER_CALLS


@pytest.mark.integration
@pytest.mark.asyncio
class TestOwnTelnyxNumbers:
    async def test_every_page_of_the_account_is_listed(
        self, client, owner, telnyx_connected, own_telnyx_account
    ):
        res = await as_user(client, owner).get(
            "/api/v1/phone-numbers/own-numbers",
            params={"connection_id": str(telnyx_connected.id)},
        )
        assert res.status_code == 200, res.text
        body = {n["phone_number"]: n for n in res.json()}
        assert set(body) == {"+13125550101", "+13125550102"}
        assert body["+13125550101"]["friendly_name"] == "Front desk"
        assert all(n["available"] for n in body.values())

    async def test_import_with_an_agent_attaches_its_texml_app(
        self, client, owner, agent, telnyx_connected, own_telnyx_account, db_session
    ):
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/import",
            json={
                "connection_id": str(telnyx_connected.id),
                "phone_number": "+13125550101",
                "agent_id": str(agent.id),
            },
        )
        assert res.status_code == 201, res.text
        assert res.json()["provider"] == "telnyx"
        assert res.json()["imported"] is True

        app = calls_for("telnyx", "POST", "/v2/texml_applications")[0]
        assert app["json_body"]["voice_url"].endswith(f"/api/v1/telephony/telnyx/voice/{agent.id}")
        attach = calls_for("telnyx", "PATCH", "/v2/phone_numbers/num-own-1")[0]
        assert attach["json_body"]["connection_id"] == "app-2"

        row = (
            await db_session.execute(
                select(PhoneNumber).where(PhoneNumber.phone_number == "+13125550101")
            )
        ).scalar_one()
        assert row.provider_sid == "num-own-1"
        assert row.integration_connection_id == telnyx_connected.id
        assert row.provider_metadata["original_connection_id"] == "conn-sip-1"

    async def test_attach_detach_and_reattach(
        self, client, owner, agent, second_agent, telnyx_connected, own_telnyx_account
    ):
        imported = await as_user(client, owner).post(
            "/api/v1/phone-numbers/import",
            json={"connection_id": str(telnyx_connected.id), "phone_number": "+13125550102"},
        )
        assert imported.status_code == 201, imported.text
        assert not calls_for("telnyx", "PATCH")
        number_id = imported.json()["id"]

        attached = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{number_id}", json={"agent_id": str(agent.id)}
        )
        assert attached.json()["agent_id"] == str(agent.id)

        detached = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{number_id}", json={"agent_id": None}
        )
        assert detached.status_code == 200, detached.text
        assert detached.json()["agent_id"] is None

        reattached = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{number_id}", json={"agent_id": str(second_agent.id)}
        )
        assert reattached.json()["agent_id"] == str(second_agent.id)
        apps = [c["json_body"]["voice_url"] for c in calls_for("telnyx", "POST", "/v2/texml_applications")]
        assert apps[-1].endswith(f"/voice/{second_agent.id}")

    async def test_a_detached_telnyx_number_stops_answering(
        self, client, owner, agent, telnyx_connected, own_telnyx_account
    ):
        imported = await as_user(client, owner).post(
            "/api/v1/phone-numbers/import",
            json={
                "connection_id": str(telnyx_connected.id),
                "phone_number": "+13125550101",
                "agent_id": str(agent.id),
            },
        )
        await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{imported.json()['id']}", json={"agent_id": None}
        )
        answer = await client.post(
            f"/api/v1/telephony/telnyx/voice/{agent.id}",
            data={"CallSid": "CA-own-detached", "From": "+15550009999",
                  "To": "+13125550101", "CallStatus": "ringing"},
        )
        assert "not available" in answer.text

    async def test_removing_restores_the_original_connection_and_never_releases(
        self, client, owner, agent, telnyx_connected, own_telnyx_account, db_session
    ):
        imported = await as_user(client, owner).post(
            "/api/v1/phone-numbers/import",
            json={
                "connection_id": str(telnyx_connected.id),
                "phone_number": "+13125550101",
                "agent_id": str(agent.id),
            },
        )
        own_telnyx_account.clear()

        res = await as_user(client, owner).delete(f"/api/v1/phone-numbers/{imported.json()['id']}")
        assert res.status_code == 204

        assert not calls_for("telnyx", "DELETE"), "an imported number must stay on the user's account"
        restore = calls_for("telnyx", "PATCH", "/v2/phone_numbers/num-own-1")[0]
        assert restore["json_body"] == {"connection_id": "conn-sip-1"}
        remaining = (
            await db_session.execute(
                select(PhoneNumber).where(PhoneNumber.phone_number == "+13125550101")
            )
        ).scalar_one_or_none()
        assert remaining is None

    async def test_a_number_with_no_prior_routing_is_unrouted_on_removal(
        self, client, owner, agent, telnyx_connected, own_telnyx_account
    ):
        imported = await as_user(client, owner).post(
            "/api/v1/phone-numbers/import",
            json={
                "connection_id": str(telnyx_connected.id),
                "phone_number": "+13125550102",
                "agent_id": str(agent.id),
            },
        )
        own_telnyx_account.clear()
        await as_user(client, owner).delete(f"/api/v1/phone-numbers/{imported.json()['id']}")
        restore = calls_for("telnyx", "PATCH", "/v2/phone_numbers/num-own-2")[0]
        assert restore["json_body"] == {"connection_id": None}

    async def test_a_number_already_on_a_voicecon_app_is_not_remembered_as_original(
        self, client, owner, agent, telnyx_connected, own_telnyx_account, db_session, monkeypatch
    ):
        """Re-adding a number whose Telnyx routing still points at Voicecon must
        not 'restore' Voicecon's own app when it is removed."""
        from app.services.telephony.providers.telnyx_provider import TelnyxNumberProvider

        original = TelnyxNumberProvider._texml_application_urls

        async def with_voicecon_app(self):
            urls = await original(self)
            urls["conn-sip-1"] = f"https://api.voicecon.test/api/v1/telephony/telnyx/voice/{agent.id}"
            return urls

        monkeypatch.setattr(TelnyxNumberProvider, "_texml_application_urls", with_voicecon_app)
        res = await as_user(client, owner).post(
            "/api/v1/phone-numbers/import",
            json={"connection_id": str(telnyx_connected.id), "phone_number": "+13125550101"},
        )
        assert res.status_code == 201, res.text
        row = (
            await db_session.execute(
                select(PhoneNumber).where(PhoneNumber.phone_number == "+13125550101")
            )
        ).scalar_one()
        assert "original_connection_id" not in row.provider_metadata


# ---------- guards on getting a number: one at a time, and daily caps ----------


async def _limit_numbers(db_session, user: User, limit: int) -> None:
    """Give the user's workspace a plan allowance of ``limit`` phone numbers."""
    from app.models.subscription import OrganizationEntitlementOverride
    from app.services.billing.entitlements import get_entitlement_service

    db_session.add(
        OrganizationEntitlementOverride(
            organization_id=await _org_id_of(db_session, user),
            overrides={"limits": {"phone_numbers": limit}},
        )
    )
    await db_session.commit()
    get_entitlement_service().invalidate_all()


async def _buy_voicecon(client, user: User, agent: Agent, number: str):
    return await as_user(client, user).post(
        "/api/v1/phone-numbers/provision",
        json={"phone_number": number, "agent_id": str(agent.id), "source": "voicecon"},
    )


async def _agent_for(db_session, user: User) -> Agent:
    agent = Agent(
        user_id=user.id,
        organization_id=await _org_id_of(db_session, user),
        name="Other Bot",
        system_prompt="You are helpful.",
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest.fixture
def sent_mail(monkeypatch):
    """Every billing notice the app tried to send."""
    from app.services.email.service import email_service

    sent: list = []

    async def record(**kwargs):
        sent.append(kwargs)
        return True

    monkeypatch.setattr(email_service, "send_billing_notice", record)
    return sent


def _purchases() -> list:
    return calls_for("twilio", "POST", "IncomingPhoneNumbers.json")


@pytest.mark.integration
@pytest.mark.asyncio
class TestPurchaseGuards:
    """A number costs money the moment it exists, so the plan allowance has to
    hold under concurrency and the platform account has a daily ceiling."""

    async def test_two_purchases_at_once_cannot_both_take_the_last_slot(
        self, client, owner, agent, platform_twilio, db_session, monkeypatch
    ):
        import asyncio

        await _limit_numbers(db_session, owner, 1)

        # A carrier that takes a moment, so both requests are in flight together.
        instant = NumberProvider._request

        async def slow(self, method, path, **kwargs):
            if method == "POST" and path.endswith("IncomingPhoneNumbers.json"):
                await asyncio.sleep(0.3)
            return await instant(self, method, path, **kwargs)

        monkeypatch.setattr(NumberProvider, "_request", slow)

        first, second = await asyncio.gather(
            _buy_voicecon(client, owner, agent, "+14155550101"),
            _buy_voicecon(client, owner, agent, "+14155550102"),
        )

        assert sorted([first.status_code, second.status_code]) == [201, 402]
        assert len(_purchases()) == 1, "the carrier was asked for two numbers"
        rows = (await db_session.execute(select(PhoneNumber))).scalars().all()
        assert len(rows) == 1

    async def test_switching_a_number_off_does_not_free_its_slot(
        self, client, owner, agent, platform_twilio, db_session
    ):
        await _limit_numbers(db_session, owner, 1)
        bought = await _buy_voicecon(client, owner, agent, "+14155550101")
        assert bought.status_code == 201, bought.text

        off = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{bought.json()['id']}", json={"status": "inactive"}
        )
        assert off.status_code == 200, off.text

        again = await _buy_voicecon(client, owner, agent, "+14155550102")
        assert again.status_code == 402
        assert len(_purchases()) == 1

    async def test_a_number_cannot_be_given_a_made_up_status(
        self, client, owner, agent, platform_twilio
    ):
        bought = await _buy_voicecon(client, owner, agent, "+14155550101")
        res = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{bought.json()['id']}", json={"status": "released"}
        )
        assert res.status_code == 400

    async def test_buying_and_releasing_in_a_loop_runs_into_the_daily_limit(
        self, client, owner, agent, platform_twilio, db_session
    ):
        """Each purchase is a month's rent at the carrier even if the number is
        released a minute later, so released numbers still count for the day."""
        await _limit_numbers(db_session, owner, 1)

        for number in ("+14155550101", "+14155550102"):
            bought = await _buy_voicecon(client, owner, agent, number)
            assert bought.status_code == 201, bought.text
            gone = await as_user(client, owner).delete(
                f"/api/v1/phone-numbers/{bought.json()['id']}"
            )
            assert gone.status_code == 204

        third = await _buy_voicecon(client, owner, agent, "+14155550103")
        assert third.status_code == 429
        assert "today's limit" in third.json()["detail"]
        assert len(_purchases()) == 2

    async def test_the_platform_daily_cap_stops_everyone_and_tells_the_admins(
        self, client, owner, other_user, agent, platform_twilio, db_session, monkeypatch, sent_mail
    ):
        import asyncio

        from app.models.subscription import SubscriptionEvent

        monkeypatch.setattr(settings, "VOICECON_NUMBER_DAILY_PURCHASE_CAP", 1)
        admin = User(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("password123"),
            full_name="Admin",
            is_active=True,
            is_platform_admin=True,
        )
        db_session.add(admin)
        await db_session.commit()
        other_agent = await _agent_for(db_session, other_user)

        first = await _buy_voicecon(client, owner, agent, "+14155550101")
        assert first.status_code == 201, first.text

        second = await _buy_voicecon(client, other_user, other_agent, "+14155550102")
        assert second.status_code == 503
        assert "Twilio" not in second.json()["detail"]
        assert len(_purchases()) == 1

        await asyncio.sleep(0.1)  # the alert email is sent in the background
        alerts = (
            await db_session.execute(
                select(SubscriptionEvent).where(SubscriptionEvent.event_type == "number_cap_reached")
            )
        ).scalars().all()
        assert len(alerts) == 1, "the admins are told once a day, not once per refusal"
        assert [m["to_email"] for m in sent_mail] == [admin.email]

    async def test_the_cap_does_not_apply_to_a_customers_own_provider(
        self, client, owner, agent, twilio_connected, platform_twilio, monkeypatch
    ):
        monkeypatch.setattr(settings, "VOICECON_NUMBER_DAILY_PURCHASE_CAP", 0)

        ours = await _buy_voicecon(client, owner, agent, "+14155550101")
        assert ours.status_code == 503
        assert not _purchases()

        theirs = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={
                "phone_number": "+14155550102",
                "agent_id": str(agent.id),
                "source": "own",
                "connection_id": str(twilio_connected.id),
            },
        )
        assert theirs.status_code == 201, theirs.text
        assert "ACfakesid" in _purchases()[0]["path"]


# ---------- taking back numbers nobody is paying for ----------


async def _set_subscription(db_session, user: User, status: str) -> None:
    from app.models.subscription import Subscription
    from app.services.billing.entitlements import get_entitlement_service

    subscription = (
        await db_session.execute(
            select(Subscription).where(
                Subscription.organization_id == await _org_id_of(db_session, user)
            )
        )
    ).scalar_one()
    subscription.status = status
    await db_session.commit()
    get_entitlement_service().invalidate_all()


async def _sweep(db_engine, now):
    """One reclaim pass on a session of its own, as the scheduler runs it."""
    from app.services.telephony.number_reclaim import reclaim_numbers

    async with async_sessionmaker(db_engine, expire_on_commit=False)() as session:
        return await reclaim_numbers(session, now=now)


async def _number(db_engine, phone_number: str):
    async with async_sessionmaker(db_engine, expire_on_commit=False)() as session:
        return (
            await session.execute(
                select(PhoneNumber).where(PhoneNumber.phone_number == phone_number)
            )
        ).scalar_one_or_none()


def _releases() -> list:
    return calls_for("twilio", "DELETE", "IncomingPhoneNumbers")


@pytest.mark.integration
@pytest.mark.asyncio
class TestNumberReclaim:
    """A Voicecon number is held when its workspace stops paying, released
    after the grace period, and handed back if the workspace returns first."""

    NUMBER = "+14155550101"

    @pytest.fixture(autouse=True)
    def _grace(self, monkeypatch):
        monkeypatch.setattr(settings, "VOICECON_NUMBER_RELEASE_GRACE_DAYS", 14)

    async def _lapsed(self, client, owner, agent, db_session):
        bought = await _buy_voicecon(client, owner, agent, self.NUMBER)
        assert bought.status_code == 201, bought.text
        await _set_subscription(db_session, owner, "expired")
        return bought.json()

    async def test_a_paying_workspace_is_left_alone(
        self, client, owner, agent, platform_twilio, db_engine, sent_mail
    ):
        from datetime import datetime

        await _buy_voicecon(client, owner, agent, self.NUMBER)
        report = await _sweep(db_engine, datetime.utcnow())

        assert report.changed == 0
        assert (await _number(db_engine, self.NUMBER)).status == "active"
        assert not sent_mail and not _releases()

    async def test_a_lapsed_workspace_has_its_number_held_and_is_told_the_date(
        self, client, owner, agent, platform_twilio, db_session, db_engine, sent_mail
    ):
        from datetime import datetime, timedelta

        await self._lapsed(client, owner, agent, db_session)
        now = datetime(2026, 10, 1, 12, 0)

        report = await _sweep(db_engine, now)
        assert report.suspended == 1

        row = await _number(db_engine, self.NUMBER)
        assert row.status == "suspended"
        assert row.provider_metadata["reclaim"]["release_after"] == (now + timedelta(days=14)).isoformat()
        # Held, not released: the customer can still come back for it.
        assert not _releases()

        assert len(sent_mail) == 1
        assert sent_mail[0]["to_email"] == owner.email
        assert "15 October 2026" in sent_mail[0]["subject"]
        assert self.NUMBER in sent_mail[0]["intro"]
        assert "Twilio" not in str(sent_mail[0])

        # Running again changes nothing and sends nothing.
        again = await _sweep(db_engine, now + timedelta(hours=1))
        assert again.changed == 0
        assert len(sent_mail) == 1

        listed = await as_user(client, owner).get("/api/v1/phone-numbers")
        assert listed.json()[0]["status"] == "suspended"
        assert listed.json()[0]["release_after"].startswith("2026-10-15T12:00:00")

    async def test_reminded_once_then_released_on_the_date(
        self, client, owner, agent, platform_twilio, db_session, db_engine, sent_mail
    ):
        from datetime import datetime, timedelta

        from app.models.subscription import SubscriptionEvent

        await self._lapsed(client, owner, agent, db_session)
        now = datetime(2026, 10, 1, 12, 0)
        await _sweep(db_engine, now)

        early = await _sweep(db_engine, now + timedelta(days=5))
        assert early.changed == 0

        reminder = await _sweep(db_engine, now + timedelta(days=12))
        assert reminder.reminded == 1
        assert (await _sweep(db_engine, now + timedelta(days=13))).reminded == 0
        assert len(sent_mail) == 2
        assert sent_mail[1]["subject"].startswith("Last reminder")
        assert not _releases()

        released = await _sweep(db_engine, now + timedelta(days=14, minutes=1))
        assert released.released == 1
        assert len(_releases()) == 1
        assert "AC_platform_sid" in _releases()[0]["path"]
        assert await _number(db_engine, self.NUMBER) is None
        assert len(sent_mail) == 3
        assert "released" in sent_mail[2]["subject"]

        event = (
            await db_session.execute(
                select(SubscriptionEvent).where(SubscriptionEvent.event_type == "number_released")
            )
        ).scalar_one()
        assert event.payload == {"phone_number": self.NUMBER, "reason": "subscription_ended"}

        # Nothing left to do.
        assert (await _sweep(db_engine, now + timedelta(days=20))).changed == 0

    async def test_subscribing_again_gets_the_number_back_straight_away(
        self, client, owner, agent, platform_twilio, db_session, db_engine
    ):
        from datetime import datetime

        await self._lapsed(client, owner, agent, db_session)
        await _sweep(db_engine, datetime.utcnow())
        assert (await _number(db_engine, self.NUMBER)).status == "suspended"

        await _set_subscription(db_session, owner, "active")
        listed = await as_user(client, owner).get("/api/v1/phone-numbers")

        assert listed.status_code == 200
        assert listed.json()[0]["status"] == "active"
        assert listed.json()[0]["release_after"] is None
        row = await _number(db_engine, self.NUMBER)
        assert row.status == "active"
        assert "reclaim" not in row.provider_metadata
        # Still knows which account it lives on.
        assert row.provider_metadata["credential_source"] == "platform"
        assert not _releases()

    async def test_the_sweep_also_restores_a_returning_workspace(
        self, client, owner, agent, platform_twilio, db_session, db_engine
    ):
        from datetime import datetime, timedelta

        await self._lapsed(client, owner, agent, db_session)
        now = datetime.utcnow()
        await _sweep(db_engine, now)
        await _set_subscription(db_session, owner, "active")

        # Well past the release date: paying again is what counts.
        report = await _sweep(db_engine, now + timedelta(days=30))
        assert report.restored == 1 and report.released == 0
        assert (await _number(db_engine, self.NUMBER)).status == "active"
        assert not _releases()

    async def test_only_as_many_come_back_as_the_new_plan_has_room_for(
        self, client, owner, agent, platform_twilio, db_session, db_engine
    ):
        from datetime import datetime

        await _buy_voicecon(client, owner, agent, "+14155550101")
        await _buy_voicecon(client, owner, agent, "+14155550102")
        await _set_subscription(db_session, owner, "expired")
        await _sweep(db_engine, datetime.utcnow())

        await _set_subscription(db_session, owner, "active")
        await _limit_numbers(db_session, owner, 1)
        await as_user(client, owner).get("/api/v1/phone-numbers")

        assert (await _number(db_engine, "+14155550101")).status == "active"
        held = await _number(db_engine, "+14155550102")
        assert held.status == "suspended"
        assert held.provider_metadata["reclaim"]["release_after"]

        # And it cannot simply be switched back on.
        res = await as_user(client, owner).patch(
            f"/api/v1/phone-numbers/{held.id}", json={"status": "active"}
        )
        assert res.status_code == 400

    async def test_a_number_on_the_customers_own_account_is_never_touched(
        self, client, owner, agent, twilio_connected, platform_twilio, db_session, db_engine, sent_mail
    ):
        from datetime import datetime, timedelta

        bought = await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={
                "phone_number": self.NUMBER,
                "agent_id": str(agent.id),
                "source": "own",
                "connection_id": str(twilio_connected.id),
            },
        )
        assert bought.status_code == 201, bought.text
        await _set_subscription(db_session, owner, "expired")

        now = datetime.utcnow()
        await _sweep(db_engine, now)
        report = await _sweep(db_engine, now + timedelta(days=60))

        assert report.changed == 0
        assert (await _number(db_engine, self.NUMBER)).status == "active"
        assert not _releases() and not sent_mail

    async def test_a_carrier_failure_keeps_the_number_and_tries_again(
        self, client, owner, agent, platform_twilio, db_session, db_engine, monkeypatch, sent_mail
    ):
        from datetime import datetime, timedelta

        from app.services.telephony.providers import NumberProviderError

        await self._lapsed(client, owner, agent, db_session)
        now = datetime.utcnow()
        await _sweep(db_engine, now)

        working = NumberProvider._request

        async def down(self, method, path, **kwargs):
            if method == "DELETE":
                raise NumberProviderError("carrier is down", status_code=503)
            return await working(self, method, path, **kwargs)

        monkeypatch.setattr(NumberProvider, "_request", down)
        failed = await _sweep(db_engine, now + timedelta(days=15))
        assert failed.released == 0 and failed.failed == 1
        row = await _number(db_engine, self.NUMBER)
        assert row.status == "suspended"
        assert row.provider_metadata["reclaim"]["attempts"] == 1
        assert not any("released" in m["subject"] and "will be" not in m["subject"] for m in sent_mail)

        monkeypatch.setattr(NumberProvider, "_request", working)
        retried = await _sweep(db_engine, now + timedelta(days=15, minutes=15))
        assert retried.released == 1
        assert await _number(db_engine, self.NUMBER) is None

    async def test_a_number_already_gone_at_the_carrier_is_cleared(
        self, client, owner, agent, platform_twilio, db_session, db_engine, monkeypatch
    ):
        from datetime import datetime, timedelta

        from app.services.telephony.providers import NumberProviderError

        await self._lapsed(client, owner, agent, db_session)
        now = datetime.utcnow()
        await _sweep(db_engine, now)

        working = NumberProvider._request

        async def missing(self, method, path, **kwargs):
            if method == "DELETE":
                raise NumberProviderError("not found", status_code=404)
            return await working(self, method, path, **kwargs)

        monkeypatch.setattr(NumberProvider, "_request", missing)
        report = await _sweep(db_engine, now + timedelta(days=15))
        assert report.released == 1
        assert await _number(db_engine, self.NUMBER) is None

    async def test_with_no_grace_period_numbers_are_held_but_never_released(
        self, client, owner, agent, platform_twilio, db_session, db_engine, monkeypatch, sent_mail
    ):
        from datetime import datetime, timedelta

        monkeypatch.setattr(settings, "VOICECON_NUMBER_RELEASE_GRACE_DAYS", 0)
        await self._lapsed(client, owner, agent, db_session)
        now = datetime.utcnow()

        await _sweep(db_engine, now)
        await _sweep(db_engine, now + timedelta(days=90))

        row = await _number(db_engine, self.NUMBER)
        assert row.status == "suspended"
        assert row.provider_metadata["reclaim"]["release_after"] is None
        assert not _releases()
        assert len(sent_mail) == 1 and "released" not in sent_mail[0]["subject"]

    async def test_a_suspended_workspace_is_treated_as_not_paying(
        self, client, owner, agent, platform_twilio, db_session, db_engine
    ):
        from datetime import datetime

        await _buy_voicecon(client, owner, agent, self.NUMBER)
        org = await db_session.get(Organization, await _org_id_of(db_session, owner))
        org.is_active = False
        await db_session.commit()

        report = await _sweep(db_engine, datetime.utcnow())
        assert report.suspended == 1

    async def test_the_reconciler_runs_the_sweep(
        self, client, owner, agent, platform_twilio, db_session, db_engine
    ):
        from app.services.billing.reconciler import reconcile_subscriptions

        await self._lapsed(client, owner, agent, db_session)
        async with async_sessionmaker(db_engine, expire_on_commit=False)() as session:
            await reconcile_subscriptions(session)

        assert (await _number(db_engine, self.NUMBER)).status == "suspended"


@pytest_asyncio.fixture
async def platform_admin(db_session) -> User:
    user = User(
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="Admin",
        is_active=True,
        is_platform_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.integration
@pytest.mark.asyncio
class TestAdminNumberControls:
    """What an operator sees and can do about numbers nobody is paying for."""

    NUMBER = "+14155550101"

    async def _held(self, client, owner, agent, db_session, db_engine, now):
        await _buy_voicecon(client, owner, agent, self.NUMBER)
        await _set_subscription(db_session, owner, "expired")
        await _sweep(db_engine, now)

    async def test_the_list_shows_what_is_on_hold_and_how_close_the_cap_is(
        self, client, owner, agent, platform_twilio, platform_admin, db_session, db_engine, monkeypatch
    ):
        from datetime import datetime

        monkeypatch.setattr(settings, "VOICECON_NUMBER_DAILY_PURCHASE_CAP", 25)
        monkeypatch.setattr(settings, "VOICECON_NUMBER_RELEASE_GRACE_DAYS", 14)
        await self._held(client, owner, agent, db_session, db_engine, datetime(2026, 10, 1, 12, 0))

        res = await as_user(client, platform_admin).get(
            "/api/v1/admin/phone-numbers", params={"status": "suspended"}
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["summary"] == {
            "on_hold": 1,
            "release_grace_days": 14,
            "purchases_24h": 1,
            "daily_purchase_cap": 25,
        }
        row = body["items"][0]
        assert row["phone_number"] == self.NUMBER
        assert row["voicecon"] is True
        assert row["release_after"].startswith("2026-10-15T12:00:00")

    async def test_a_customer_cannot_use_the_admin_controls(
        self, client, owner, agent, platform_twilio, db_session, db_engine
    ):
        from datetime import datetime

        await self._held(client, owner, agent, db_session, db_engine, datetime.utcnow())
        row = await _number(db_engine, self.NUMBER)

        res = await as_user(client, owner).post(f"/api/v1/admin/phone-numbers/{row.id}/release")
        assert res.status_code in (401, 403)
        assert not _releases()

    async def test_release_now_gives_the_number_back_to_the_carrier(
        self, client, owner, agent, platform_twilio, platform_admin, db_session, db_engine
    ):
        from datetime import datetime

        await self._held(client, owner, agent, db_session, db_engine, datetime.utcnow())
        row = await _number(db_engine, self.NUMBER)

        res = await as_user(client, platform_admin).post(
            f"/api/v1/admin/phone-numbers/{row.id}/release"
        )
        assert res.status_code == 200, res.text
        assert len(_releases()) == 1
        assert await _number(db_engine, self.NUMBER) is None

    async def test_keep_pushes_the_release_date_back(
        self, client, owner, agent, platform_twilio, platform_admin, db_session, db_engine
    ):
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        await self._held(client, owner, agent, db_session, db_engine, now - timedelta(days=13))
        row = await _number(db_engine, self.NUMBER)

        res = await as_user(client, platform_admin).post(
            f"/api/v1/admin/phone-numbers/{row.id}/hold", json={"days": 14}
        )
        assert res.status_code == 200, res.text

        # Past the original date, still inside the extension: not released.
        report = await _sweep(db_engine, now + timedelta(days=5))
        assert report.released == 0
        assert (await _number(db_engine, self.NUMBER)).status == "suspended"

    async def test_a_customers_own_number_cannot_be_released_from_the_console(
        self, client, owner, agent, twilio_connected, platform_twilio, platform_admin, db_engine
    ):
        await as_user(client, owner).post(
            "/api/v1/phone-numbers/provision",
            json={
                "phone_number": self.NUMBER,
                "agent_id": str(agent.id),
                "source": "own",
                "connection_id": str(twilio_connected.id),
            },
        )
        row = await _number(db_engine, self.NUMBER)

        res = await as_user(client, platform_admin).post(
            f"/api/v1/admin/phone-numbers/{row.id}/release"
        )
        assert res.status_code == 400
        assert not _releases()
