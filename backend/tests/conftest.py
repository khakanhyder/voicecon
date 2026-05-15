"""
Pytest configuration and fixtures for Voicecon tests.
"""

import asyncio
import os
from typing import AsyncGenerator, Generator
import uuid

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User, Organization
from app.models.agent import Agent
from app.models.call import PhoneNumber
from app.services.billing import StripeService
from app.api.deps import get_current_user


# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/voicecon_test"
)


# ==================== Database Fixtures ====================


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
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
    """Create a test client with database session override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ==================== User & Auth Fixtures ====================


@pytest_asyncio.fixture
async def test_organization(db_session: AsyncSession) -> Organization:
    """Create a test organization."""
    org = Organization(
        name="Test Organization",
        slug="test-org",
        is_active=True,
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_organization: Organization) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeW.ljYR7K7Q9K9Oi",  # "password"
        full_name="Test User",
        organization_id=test_organization.id,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_superuser(db_session: AsyncSession, test_organization: Organization) -> User:
    """Create a test superuser."""
    user = User(
        email="admin@example.com",
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeW.ljYR7K7Q9K9Oi",
        full_name="Admin User",
        organization_id=test_organization.id,
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_client(client: TestClient, test_user: User) -> TestClient:
    """Create an authenticated test client."""

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    return client


# ==================== Agent Fixtures ====================


@pytest_asyncio.fixture
async def test_agent(db_session: AsyncSession, test_organization: Organization) -> Agent:
    """Create a test agent."""
    agent = Agent(
        organization_id=test_organization.id,
        name="Test Agent",
        description="A test agent for testing",
        system_prompt="You are a helpful test assistant.",
        first_message="Hello! How can I help you today?",
        voice_id="en-US-Neural2-F",
        language="en-US",
        temperature=0.7,
        max_tokens=150,
        is_active=True,
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def test_phone_number(
    db_session: AsyncSession,
    test_organization: Organization,
    test_agent: Agent
) -> PhoneNumber:
    """Create a test phone number."""
    phone = PhoneNumber(
        organization_id=test_organization.id,
        phone_number="+15551234567",
        friendly_name="Test Number",
        country_code="US",
        number_type="local",
        capabilities={"voice": True, "sms": True},
        provider="twilio",
        provider_sid="PN1234567890",
        status="active",
        assigned_agent_id=test_agent.id,
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
def mock_openai_response(monkeypatch):
    """Mock OpenAI API responses."""

    class MockOpenAIResponse:
        def __init__(self, content: str = "Test response"):
            self.choices = [
                type('obj', (object,), {
                    'message': type('obj', (object,), {
                        'content': content,
                        'role': 'assistant'
                    })()
                })()
            ]
            self.usage = type('obj', (object,), {
                'total_tokens': 100
            })()

    def mock_create(*args, **kwargs):
        return MockOpenAIResponse()

    monkeypatch.setattr("openai.ChatCompletion.create", mock_create)


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
    from app.models.template import AgentTemplate
    from datetime import datetime

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


# ==================== Cleanup ====================


@pytest.fixture(autouse=True)
def cleanup_files():
    """Cleanup any test files after tests."""
    yield
    # Add cleanup logic if needed
    pass
