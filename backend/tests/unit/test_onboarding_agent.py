"""
The first agent, created from the assistant details typed during onboarding.

It is created when onboarding *finishes* (a trial starts or a payment lands),
because an agent cannot exist before the workspace has a plan; it is created
once; and it only happens when the user actually gave a name and a description.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.agent import Agent
from app.models.company import CompanyProfile
from app.models.subscription import SubscriptionPlan
from app.models.user import Organization, OrganizationMember, User
from app.services.agent_service import AgentService
from app.services.billing import catalog
from app.services.billing.conversion import mark_onboarding_done
from app.services.billing.trial import grant_trial

pytestmark = pytest.mark.unit

INSTRUCTIONS = "Answer customer calls, qualify leads, and book appointments."


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _workspace(db, *, name="Aria", instructions=INSTRUCTIONS, language="English"):
    user = User(
        email=f"u-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x", full_name="Owner", is_active=True,
    )
    db.add(user)
    await db.flush()
    org = Organization(name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}", owner_id=user.id)
    db.add(org)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    profile = CompanyProfile(
        organization_id=org.id, user_id=user.id, company_name="Acme",
        assistant_name=name, assistant_instructions=instructions,
        preferred_language=language,
    )
    db.add(profile)
    await db.commit()
    return user, org, profile


async def _agents(db, org):
    return (await db.execute(select(Agent).where(Agent.organization_id == org.id))).scalars().all()


@pytest.mark.asyncio
async def test_finishing_onboarding_creates_the_agent_from_the_details(db):
    user, org, profile = await _workspace(db, name="  Aria  ")

    await mark_onboarding_done(db, org.id)
    await db.commit()

    [agent] = await _agents(db, org)
    assert agent.name == "Aria"
    assert agent.system_prompt == INSTRUCTIONS
    # Linked to the right user and workspace.
    assert agent.user_id == user.id
    assert agent.organization_id == org.id
    assert agent.is_active is True


@pytest.mark.asyncio
async def test_the_agent_starts_with_the_same_defaults_as_the_new_agent_form(db):
    _, org, _ = await _workspace(db)
    await mark_onboarding_done(db, org.id)
    await db.commit()

    [agent] = await _agents(db, org)
    assert agent.first_message == "Hello! How can I help you today?"
    assert agent.llm_provider == "openai"
    assert agent.llm_model == "gpt-5.4-nano"
    assert agent.tts_provider == "elevenlabs"
    assert agent.stt_provider == "deepgram"
    assert agent.stt_language == "en"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "chosen,code",
    [("Spanish", "es"), ("french", "fr"), ("Arabic", "ar"), ("Hindi", "hi"), ("Portuguese", "pt"), ("Klingon", "en")],
)
async def test_the_preferred_language_sets_speech_recognition(db, chosen, code):
    _, org, _ = await _workspace(db, language=chosen)
    await mark_onboarding_done(db, org.id)
    await db.commit()

    [agent] = await _agents(db, org)
    assert agent.stt_language == code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,instructions",
    [
        (None, INSTRUCTIONS),   # a description with nothing to call it
        ("   ", INSTRUCTIONS),
        ("Aria", None),         # a name with nothing to say
        ("Aria", "   "),
        (None, None),           # skipped both
    ],
)
async def test_no_agent_unless_both_details_were_given(db, name, instructions):
    _, org, profile = await _workspace(db, name=name, instructions=instructions)

    await mark_onboarding_done(db, org.id)
    await db.commit()

    assert await _agents(db, org) == []
    # ...and onboarding itself still completes.
    await db.refresh(profile)
    assert profile.onboarding_completed is True and profile.onboarding_step == "done"


@pytest.mark.asyncio
async def test_it_is_created_once_and_a_deleted_agent_is_not_brought_back(db):
    _, org, _ = await _workspace(db)

    await mark_onboarding_done(db, org.id)   # trial starts
    await mark_onboarding_done(db, org.id)   # the later paid conversion / webhook retry
    await db.commit()
    [agent] = await _agents(db, org)

    await db.delete(agent)
    await db.commit()
    await mark_onboarding_done(db, org.id)   # the next payment
    await db.commit()

    assert await _agents(db, org) == []


@pytest.mark.asyncio
async def test_a_workspace_that_already_has_an_agent_gets_no_second(db):
    user, org, _ = await _workspace(db)
    db.add(Agent(user_id=user.id, organization_id=org.id, name="Existing", system_prompt="hi"))
    await db.commit()

    await mark_onboarding_done(db, org.id)
    await db.commit()

    assert [a.name for a in await _agents(db, org)] == ["Existing"]


@pytest.mark.asyncio
async def test_a_workspace_without_a_company_profile_is_untouched(db):
    """Workspaces made from the sidebar never had an onboarding form."""
    user = User(email="p@example.com", hashed_password="x", full_name="P", is_active=True)
    db.add(user)
    await db.flush()
    org = Organization(name="Side", slug="side-1", owner_id=user.id)
    db.add(org)
    await db.commit()

    await mark_onboarding_done(db, org.id)
    await db.commit()

    assert await _agents(db, org) == []


@pytest.mark.asyncio
async def test_a_failure_creating_the_agent_never_blocks_onboarding(db, monkeypatch):
    _, org, profile = await _workspace(db)

    def boom(*_args, **_kwargs):
        raise RuntimeError("database said no")

    monkeypatch.setattr(AgentService, "build_agent", staticmethod(boom))

    await mark_onboarding_done(db, org.id)   # must not raise
    await db.commit()

    assert await _agents(db, org) == []
    await db.refresh(profile)
    assert profile.onboarding_completed is True


@pytest.mark.asyncio
async def test_a_name_too_long_to_be_an_agent_is_skipped_not_fatal(db):
    _, org, profile = await _workspace(db, name="A" * 300)

    await mark_onboarding_done(db, org.id)
    await db.commit()

    assert await _agents(db, org) == []
    assert profile.onboarding_completed is True


@pytest.mark.asyncio
async def test_starting_the_free_trial_creates_it(db):
    """The path a real new user takes: Company → Pricing → Start free trial."""
    document = catalog.entitlements_for_plan("voice-ai")
    db.add(SubscriptionPlan(
        slug="voice-ai", name="Voice AI", tier=2,
        stripe_product_id="prod_x", stripe_price_id="price_x", price_monthly=359,
        entitlements={
            "features": dict(document["features"]),
            "limits": dict(document["limits"]),
            "overage": dict(document["overage"]),
        },
        trial_days=7, is_trialable=True,
    ))
    user, org, profile = await _workspace(db)
    await db.commit()

    await grant_trial(db, organization_id=org.id, user=user)
    await db.commit()

    [agent] = await _agents(db, org)
    assert (agent.name, agent.system_prompt) == ("Aria", INSTRUCTIONS)
    assert agent.organization_id == org.id and agent.user_id == user.id
