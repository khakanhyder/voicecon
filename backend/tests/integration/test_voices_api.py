"""
Integration tests for the voice library (/api/v1/voices).

The provider is stubbed at the ``voice_library`` boundary, so these cover what
the API itself decides: who may see which voices, what is stored, and that a
provider key never comes back out.
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.dependencies import get_current_user
from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models.agent import Agent
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.user import Organization, OrganizationMember, User
from app.models.voice import CustomVoice
from app.services.billing import catalog
from app.services.integrations.credential_manager import get_credential_manager
from app.services.voice import voice_library
from app.services.voice.voice_library import VoiceInfo, VoiceNotFound

VOICE_ID = "AbCdEfGhIjKlMnOpQrSt"
_ACTING: dict = {"id": None}


async def _workspace(db_session, email: str) -> SimpleNamespace:
    """A user who owns a workspace on a live paid plan."""
    user = User(
        email=email,
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
    await db_session.commit()
    return SimpleNamespace(user_id=user.id, org_id=org.id)


@pytest_asyncio.fixture
async def acme(db_session):
    return await _workspace(db_session, "owner@example.com")


@pytest_asyncio.fixture
async def rival(db_session):
    return await _workspace(db_session, "rival@example.com")


@pytest_asyncio.fixture
async def client(db_engine):
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    async def _current_user(db=Depends(get_db)):
        result = await db.execute(select(User).where(User.id == _ACTING["id"]))
        return result.scalar_one()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _current_user
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def acting(client, workspace):
    _ACTING["id"] = workspace.user_id
    client.headers["X-Organization-Id"] = str(workspace.org_id)
    return client


@pytest.fixture
def provider(monkeypatch):
    """Stands in for ElevenLabs. Records the key each call was made with."""
    calls = SimpleNamespace(inspect=[], preview=[], missing=False)

    async def inspect_voice(provider, voice_id, api_key=None):
        calls.inspect.append(api_key)
        if calls.missing:
            raise VoiceNotFound("no such voice")
        return VoiceInfo(
            provider="elevenlabs", voice_id=voice_id.strip(), name="My Clone",
            category="cloned", labels={"accent": "british"},
        )

    async def preview_voice(provider, voice_id, api_key=None):
        calls.preview.append(api_key)
        return SimpleNamespace(audio_data=b"ID3-fake-mp3")

    monkeypatch.setattr(voice_library, "inspect_voice", inspect_voice)
    monkeypatch.setattr(voice_library, "preview_voice", preview_voice)
    return calls


@pytest.mark.integration
@pytest.mark.asyncio
class TestVoiceLibrary:
    async def test_an_empty_library_still_lists_where_voices_can_come_from(self, client, acme):
        res = await acting(client, acme).get("/api/v1/voices")
        assert res.status_code == 200
        body = res.json()
        assert body["custom_voices"] == []
        assert [p["slug"] for p in body["providers"]] == ["elevenlabs"]
        assert {f["key"] for f in body["providers"][0]["fields"]} == {"voice_id", "api_key"}

    async def test_saving_a_voice_stores_the_key_encrypted_and_never_returns_it(
        self, client, acme, provider, db_session
    ):
        res = await acting(client, acme).post(
            "/api/v1/voices/custom",
            json={"provider": "elevenlabs", "voice_id": VOICE_ID, "api_key": "sk_customer_secret"},
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["name"] == "My Clone"
        assert body["uses_own_key"] is True
        assert "sk_customer_secret" not in res.text
        assert "api_key" not in body

        listing = await client.get("/api/v1/voices")
        assert "sk_customer_secret" not in listing.text
        assert [v["voice_id"] for v in listing.json()["custom_voices"]] == [VOICE_ID]

        row = (await db_session.execute(select(CustomVoice))).scalar_one()
        assert row.api_key_encrypted and "sk_customer_secret" not in row.api_key_encrypted
        assert get_credential_manager().decrypt(row.api_key_encrypted) == "sk_customer_secret"
        assert provider.inspect == ["sk_customer_secret"]

    async def test_a_chosen_name_wins_over_the_providers(self, client, acme, provider):
        res = await acting(client, acme).post(
            "/api/v1/voices/custom",
            json={"voice_id": VOICE_ID, "name": "  Front desk  "},
        )
        assert res.status_code == 201
        assert res.json()["name"] == "Front desk"
        assert res.json()["uses_own_key"] is False

    async def test_a_voice_the_provider_does_not_know_is_not_saved(
        self, client, acme, provider, db_session
    ):
        provider.missing = True
        res = await acting(client, acme).post("/api/v1/voices/custom", json={"voice_id": VOICE_ID})
        assert res.status_code == 404
        assert "couldn't find that voice" in res.json()["detail"]
        assert (await db_session.execute(select(CustomVoice))).first() is None

    async def test_the_same_voice_cannot_be_added_twice(self, client, acme, provider):
        first = await acting(client, acme).post("/api/v1/voices/custom", json={"voice_id": VOICE_ID})
        again = await client.post("/api/v1/voices/custom", json={"voice_id": VOICE_ID})
        assert first.status_code == 201
        assert again.status_code == 409

    async def test_checking_a_voice_saves_nothing(self, client, acme, provider, db_session):
        res = await acting(client, acme).post(
            "/api/v1/voices/custom/check", json={"voice_id": VOICE_ID, "api_key": "sk_x"}
        )
        assert res.status_code == 200
        assert res.json()["name"] == "My Clone"
        assert "sk_x" not in res.text
        assert (await db_session.execute(select(CustomVoice))).first() is None

    async def test_one_workspace_cannot_see_or_remove_anothers_voice(
        self, client, acme, rival, provider
    ):
        created = await acting(client, acme).post(
            "/api/v1/voices/custom", json={"voice_id": VOICE_ID, "api_key": "sk_acme"}
        )
        voice_id = created.json()["id"]

        listing = await acting(client, rival).get("/api/v1/voices")
        assert listing.json()["custom_voices"] == []
        removed = await client.delete(f"/api/v1/voices/custom/{voice_id}")
        assert removed.status_code == 404

    async def test_preview_of_a_saved_voice_uses_its_key_and_only_in_its_workspace(
        self, client, acme, rival, provider
    ):
        await acting(client, acme).post(
            "/api/v1/voices/custom", json={"voice_id": VOICE_ID, "api_key": "sk_acme"}
        )

        mine = await client.post("/api/v1/voices/preview", json={"voice_id": VOICE_ID})
        assert mine.status_code == 200
        assert mine.headers["content-type"] == "audio/mpeg"
        assert mine.content == b"ID3-fake-mp3"

        await acting(client, rival).post("/api/v1/voices/preview", json={"voice_id": VOICE_ID})

        assert provider.preview == ["sk_acme", None]

    async def test_a_voice_an_assistant_speaks_with_cannot_be_removed(
        self, client, acme, provider, db_session
    ):
        created = await acting(client, acme).post("/api/v1/voices/custom", json={"voice_id": VOICE_ID})
        db_session.add(Agent(
            organization_id=acme.org_id, user_id=acme.user_id, name="Riley",
            system_prompt="Be helpful.",
            tts_provider="elevenlabs", tts_voice_id=VOICE_ID,
        ))
        await db_session.commit()

        blocked = await client.delete(f"/api/v1/voices/custom/{created.json()['id']}")
        assert blocked.status_code == 409
        assert "Riley" in blocked.json()["detail"]

    async def test_a_voice_nothing_uses_can_be_removed(self, client, acme, provider):
        created = await acting(client, acme).post("/api/v1/voices/custom", json={"voice_id": VOICE_ID})
        removed = await client.delete(f"/api/v1/voices/custom/{created.json()['id']}")
        assert removed.status_code == 204
        assert (await client.get("/api/v1/voices")).json()["custom_voices"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_call_speaks_a_custom_voice_with_its_own_key(db_session, acme):
    db_session.add(CustomVoice(
        organization_id=acme.org_id, provider="elevenlabs", voice_id=VOICE_ID, name="Clone",
        api_key_encrypted=voice_library.encrypt_api_key("sk_acme"),
    ))
    await db_session.commit()

    resolve = voice_library.resolve_tts_api_key
    assert await resolve(db_session, acme.org_id, "elevenlabs", VOICE_ID) == "sk_acme"
    # A built-in voice, and another workspace, fall back to the platform key.
    assert await resolve(db_session, acme.org_id, "elevenlabs", "21m00Tcm4TlvDq8ikWAM") is None
    assert await resolve(db_session, uuid.uuid4(), "elevenlabs", VOICE_ID) is None
