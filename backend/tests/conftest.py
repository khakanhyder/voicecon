"""
Pytest configuration and fixtures for Voicecon tests.

Tests run against **Postgres**, the same engine as production — so `Numeric`
really returns `Decimal`, and anything that depends on Postgres semantics is
exercised for real rather than approximated.

The default points at the local dev instance (Docker, host port 5435) using a
separate `voicecon_test` database, which is dropped and recreated per test.
Create it once with:

    docker exec voicecon_postgres createdb -U voicecon_user voicecon_test

Override the target with `TEST_DATABASE_URL`. SQLite is still accepted there
(`sqlite+aiosqlite:///:memory:`) for a quick run with no database to hand, but
it is a fallback, not the reference: SQLite returns floats for `Numeric` columns
and does not enforce every constraint Postgres does, so a green SQLite run is
weaker evidence than a green Postgres one.
"""

import asyncio
import os
import uuid
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import settings

# Rate limiting is process-global and its buckets outlive a single test, so
# leaving it on makes this suite order-dependent: a module that performs more
# than the write allowance in a minute starts handing out 429s to whichever
# tests happen to run next. Nothing here is testing the limiter — the
# Playwright `api` project covers it against a live server — so it is off.
settings.RATE_LIMIT_ENABLED = False

# Credential encryption has no default any more. It used to fall back to a
# secret hardcoded in the source, which meant a deployment that never set
# ENCRYPTION_SECRET_KEY encrypted every tenant's OAuth tokens under a key
# published in this repository — so the fallback was removed and an unset key
# now raises. Tests still need *a* key; these values are fixtures, deliberately
# obvious as such, and are never used anywhere real.
settings.ENCRYPTION_SECRET_KEY = "test-only-encryption-key-not-a-real-secret"
settings.ENCRYPTION_SALT = "00112233445566778899aabbccddeeff"

from app.core.dependencies import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.agent import Agent
from app.models.call import PhoneNumber
from app.models.user import Organization, OrganizationMember, User
from app.services.billing import StripeService

#: Where the fixtures build their schema. Defaults to the local dev Postgres on
#: port 5435 — the port the Docker container publishes, and the one `.env` uses.
#: (The previous default named port 5432 with postgres/postgres credentials,
#: which matched nothing here, so every database-backed test errored out.)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://voicecon_user:voicecon_password_dev@localhost:5435/voicecon_test",
)

IS_SQLITE = TEST_DATABASE_URL.startswith("sqlite")

#: bcrypt hash of "password", precomputed so fixtures don't pay ~12 rounds of
#: hashing per test.
TEST_PASSWORD = "password"
TEST_PASSWORD_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeW.ljYR7K7Q9K9Oi"


# ==================== Database Fixtures ====================


#: Sync URL for the one-off DDL below. Schema creation is done with psycopg2
#: rather than asyncpg so it can be a plain session-scoped fixture — a
#: *session*-scoped async fixture would be pinned to an event loop that the
#: function-scoped tests no longer run on.
SYNC_TEST_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)


@pytest.fixture(scope="session")
def _schema():
    """
    Build the schema once for the whole run.

    Dropping and recreating 52 tables per test cost 1.5–3s of setup each and
    dominated the suite. The tables are created once here; `db_engine` below
    truncates between tests instead, which is the same isolation for a fraction
    of the time.
    """
    if IS_SQLITE:
        # An in-memory SQLite database cannot be shared with a separate sync
        # engine, so those runs keep creating the schema per test (it is cheap
        # there — no disk, no network).
        yield
        return

    engine = create_engine(SYNC_TEST_URL)
    with engine.begin() as conn:
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)

    yield

    with engine.begin() as conn:
        Base.metadata.drop_all(conn)
    engine.dispose()


#: Emptied between tests. Built once, since `sorted_tables` is not free.
_TRUNCATE_SQL = text(
    "TRUNCATE TABLE {} RESTART IDENTITY CASCADE".format(
        ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    )
)


@pytest_asyncio.fixture(scope="function")
async def db_engine(_schema):
    """
    An empty database for one test.

    In-memory SQLite gives each *connection* its own database, so the engine is
    pinned to a single connection with `StaticPool` — otherwise the session that
    creates the tables and the session that queries them see different (empty)
    databases.
    """
    if IS_SQLITE:
        engine = create_async_engine(
            TEST_DATABASE_URL,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            echo=False,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)
        # One statement for all 52 tables: CASCADE means foreign keys do not
        # dictate an order, and it is a single round trip.
        async with engine.begin() as conn:
            await conn.execute(_TRUNCATE_SQL)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """A session on the test database. Rolled back when the test ends."""
    async_session = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def client(db_session) -> TestClient:
    """
    Synchronous test client sharing the test session.

    Only safe for read-only endpoints: `TestClient` drives the app on its own
    event loop, so a *write* through this client and the test's own `db_session`
    end up interleaving on one asyncpg connection ("another operation is in
    progress"). Use `async_client` for anything that writes.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """
    In-loop ASGI client, safe for write endpoints.

    Runs on the *test's* event loop rather than a private one, so the app and
    the test share the session without fighting over the connection.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ==================== User & Auth Fixtures ====================


async def create_user(
    db_session: AsyncSession,
    *,
    email: str = "test@example.com",
    full_name: str = "Test User",
    is_active: bool = True,
    is_verified: bool = True,
) -> User:
    """Insert a user. Flushed, not committed, so the caller can keep building."""
    user = User(
        email=email,
        hashed_password=TEST_PASSWORD_HASH,
        full_name=full_name,
        is_active=is_active,
        is_verified=is_verified,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def create_organization(
    db_session: AsyncSession,
    owner: User,
    *,
    name: str = "Test Organization",
    slug: str = "test-org",
    plan_type: str = "starter",
) -> Organization:
    """
    Insert an organization owned by `owner`, plus the owner's membership row.

    `owner_id` is NOT NULL and every request re-checks `organization_members`,
    so an organization without both is not a state the app can produce.
    """
    org = Organization(
        name=name,
        slug=slug,
        owner_id=owner.id,
        plan_type=plan_type,
        is_active=True,
        settings={},
    )
    db_session.add(org)
    await db_session.flush()

    db_session.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=owner.id,
            role="owner",
            permissions={},
        )
    )

    # The workspace the owner's requests resolve to until they switch.
    owner.active_organization_id = org.id
    await db_session.flush()
    return org


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """A user who owns `test_organization`."""
    user = await create_user(db_session)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_organization(
    db_session: AsyncSession, test_user: User
) -> Organization:
    """An organization owned by `test_user`, with the membership row to match."""
    org = await create_organization(db_session, test_user)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest_asyncio.fixture
async def test_member(
    db_session: AsyncSession, test_organization: Organization
) -> User:
    """A second, non-owner user inside `test_organization`."""
    member = await create_user(
        db_session, email="member@example.com", full_name="Member User"
    )
    db_session.add(
        OrganizationMember(
            organization_id=test_organization.id,
            user_id=member.id,
            role="member",
            permissions={},
        )
    )
    member.active_organization_id = test_organization.id
    await db_session.commit()
    await db_session.refresh(member)
    return member


@pytest_asyncio.fixture
async def other_organization(db_session: AsyncSession) -> Organization:
    """
    An unrelated organization with its own owner.

    The counterparty for tenant-isolation tests: anything reachable from here
    must not be reachable from `test_organization`.
    """
    outsider = await create_user(
        db_session, email="outsider@example.com", full_name="Outsider"
    )
    org = await create_organization(
        db_session, outsider, name="Other Org", slug="other-org"
    )
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture
def auth_client(client: TestClient, test_user: User) -> TestClient:
    """`client`, with `test_user` as the authenticated caller."""

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    return client


# ==================== Agent Fixtures ====================


@pytest_asyncio.fixture
async def test_agent(
    db_session: AsyncSession, test_user: User, test_organization: Organization
) -> Agent:
    """An agent belonging to `test_organization`."""
    agent = Agent(
        user_id=test_user.id,
        organization_id=test_organization.id,
        name="Test Agent",
        description="A test agent for testing",
        system_prompt="You are a helpful test assistant.",
        first_message="Hello! How can I help you today?",
        tts_voice_id="en-US-Neural2-F",
        stt_language="en",
        is_active=True,
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def test_phone_number(
    db_session: AsyncSession,
    test_user: User,
    test_organization: Organization,
    test_agent: Agent,
) -> PhoneNumber:
    """A phone number assigned to `test_agent`."""
    phone = PhoneNumber(
        user_id=test_user.id,
        organization_id=test_organization.id,
        phone_number="+15551234567",
        country_code="US",
        capabilities={"voice": True, "sms": True},
        provider="twilio",
        provider_sid="PN1234567890",
        provider_metadata={},
        status="active",
        agent_id=test_agent.id,
    )
    db_session.add(phone)
    await db_session.commit()
    await db_session.refresh(phone)
    return phone


# ==================== Billing Fixtures ====================


@pytest.fixture
def mock_stripe_service(monkeypatch):
    """Mock Stripe service for testing."""

    class MockStripeService:
        def __init__(self, api_key: str, webhook_secret: str):
            self.api_key = api_key
            self.webhook_secret = webhook_secret

        async def create_customer(self, email: str, name: str, organization_id: uuid.UUID):
            return f"cus_test_{organization_id}"

        async def create_subscription(self, **kwargs):
            return type('obj', (object,), {
                'id': 'sub_test_123',
                'status': 'active',
                'current_period_start': 1234567890,
                'current_period_end': 1234567890 + 2592000,
            })()

    return MockStripeService


# ==================== Integration Fixtures ====================


@pytest.fixture
def mock_twilio_client(monkeypatch):
    """Mock Twilio client for testing."""

    class MockTwilioClient:
        class Messages:
            @staticmethod
            def create(**kwargs):
                return type('obj', (object,), {
                    'sid': 'SM1234567890',
                    'status': 'sent'
                })()

        messages = Messages()

    return MockTwilioClient()


# ==================== Template Fixtures ====================


@pytest_asyncio.fixture
async def test_agent_template(db_session: AsyncSession):
    """Create a test agent template."""
    from datetime import datetime

    from app.models.template import AgentTemplate

    template = AgentTemplate(
        name="Test Agent Template",
        slug="test-agent-template",
        description="A test agent template",
        long_description="This is a detailed test agent template",
        category="customer_support",
        tags=["test", "support"],
        version="1.0.0",
        icon="🧪",
        author_name="Test Author",
        is_official=True,
        is_featured=False,
        is_free=True,
        status="published",
        agent_config={"name": "Test Agent"},
        system_prompt="Test prompt",
        published_at=datetime.utcnow(),
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


# ==================== Helper Functions ====================


def assert_valid_uuid(value: str):
    """Assert that a string is a valid UUID."""
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        pytest.fail(f"{value} is not a valid UUID")


def assert_datetime_recent(dt, seconds: int = 60):
    """Assert that a datetime is recent (within last N seconds)."""
    from datetime import datetime, timedelta

    if isinstance(dt, str):
        from dateutil import parser
        dt = parser.parse(dt)

    now = datetime.utcnow()
    assert now - timedelta(seconds=seconds) <= dt <= now, \
        f"Datetime {dt} is not recent (within {seconds}s of {now})"


@pytest.fixture
def assert_response_success():
    """Helper to assert successful API response."""
    def _assert(response, status_code: int = 200):
        assert response.status_code == status_code, \
            f"Expected {status_code}, got {response.status_code}: {response.text}"
        return response.json()
    return _assert


@pytest.fixture
def assert_response_error():
    """Helper to assert error API response."""
    def _assert(response, status_code: int = 400):
        assert response.status_code == status_code, \
            f"Expected error {status_code}, got {response.status_code}"
        return response.json()
    return _assert
