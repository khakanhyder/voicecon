"""
One free trial per account — and the several different ways of asking for a
second one.

The rule is only worth as much as its weakest arm, so each test here is a
distinct route back to a free product: the same person in a new workspace, a
second admin in the *same* workspace once the first trial lapsed, a workspace
whose grant row was never written, and a client naming its own trial length on
the paid-subscription endpoint.

Uses a throwaway SQLite database like ``test_subscription_lifecycle``, so it
runs without a Postgres test database.
"""

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import billing as billing_endpoints
from app.api.v1.endpoints.billing import (
    CreateSubscriptionRequest,
    _trial_already_used,
    create_subscription,
)
from app.database import Base
from app.models.subscription import (
    SOURCE_STRIPE,
    SOURCE_TRIAL,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_TRIALING,
    Subscription,
    SubscriptionPlan,
    TrialGrant,
)
from app.models.user import Organization, OrganizationMember, User
from app.services.billing import catalog

pytestmark = [pytest.mark.unit, pytest.mark.billing]


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


async def make_user(db: AsyncSession, email: str) -> User:
    user = User(email=email, hashed_password="x", full_name="Someone", is_active=True)
    db.add(user)
    await db.flush()
    await db.commit()
    return user


async def make_org(db: AsyncSession, owner: User, name: str = "Acme") -> Organization:
    organization = Organization(
        name=name, slug=f"{name.lower()}-{uuid.uuid4().hex[:8]}", owner_id=owner.id
    )
    db.add(organization)
    await db.flush()
    db.add(
        OrganizationMember(
            organization_id=organization.id, user_id=owner.id, role="owner"
        )
    )
    await db.commit()
    return organization


@pytest_asyncio.fixture
async def plan(db: AsyncSession) -> SubscriptionPlan:
    document = catalog.PLAN_ENTITLEMENTS["voice-ai"]
    subscription_plan = SubscriptionPlan(
        slug="voice-ai",
        name="Voice AI",
        tier=2,
        stripe_product_id=f"prod_{uuid.uuid4().hex[:10]}",
        stripe_price_id=f"price_{uuid.uuid4().hex[:10]}",
        price_monthly=359,
        entitlements={
            "features": dict(document["features"]),
            "limits": dict(document["limits"]),
            "overage": dict(document["overage"]),
        },
        trial_days=7,
        is_trialable=True,
    )
    db.add(subscription_plan)
    await db.commit()
    return subscription_plan


async def grant_trial(
    db: AsyncSession,
    org: Organization,
    user: User,
    *,
    days_ago: int = 0,
) -> TrialGrant:
    """Record the trial the way ``POST /billing/trial`` does."""
    granted = datetime.utcnow() - timedelta(days=days_ago)
    grant = TrialGrant(
        organization_id=org.id,
        user_id=user.id,
        email_domain=user.email.split("@")[-1].lower(),
        granted_at=granted,
        expires_at=granted + timedelta(days=7),
    )
    db.add(grant)
    await db.commit()
    return grant


async def add_subscription(
    db: AsyncSession,
    org: Organization,
    plan: SubscriptionPlan,
    *,
    status: str,
    source: str,
) -> Subscription:
    now = datetime.utcnow()
    subscription = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        status=status,
        source=source,
        billing_period="monthly",
        current_period_start=now - timedelta(days=10),
        current_period_end=now - timedelta(days=3),
        trial_start=now - timedelta(days=10) if source == SOURCE_TRIAL else None,
        trial_end=now - timedelta(days=3) if source == SOURCE_TRIAL else None,
    )
    db.add(subscription)
    await db.commit()
    return subscription


class TestFirstTrial:
    async def test_a_new_account_may_start_one(self, db):
        user = await make_user(db, "new@acme.test")
        org = await make_org(db, user)

        assert await _trial_already_used(db, user, org.id) is None


class TestTheSamePersonComingBack:
    async def test_a_second_workspace_gets_no_second_trial(self, db):
        """Delete the workspace, make another — the clock does not reset."""
        user = await make_user(db, "serial@acme.test")
        first = await make_org(db, user, name="First")
        await grant_trial(db, first, user, days_ago=30)

        second = await make_org(db, user, name="Second")
        assert await _trial_already_used(db, user, second.id) == "user_already_trialed"

    async def test_an_expired_trial_cannot_be_restarted(self, db, plan):
        """The headline case: the trial ran out, so there is no second one."""
        user = await make_user(db, "lapsed@acme.test")
        org = await make_org(db, user)
        await grant_trial(db, org, user, days_ago=20)
        await add_subscription(
            db, org, plan, status=STATUS_EXPIRED, source=SOURCE_TRIAL
        )

        assert await _trial_already_used(db, user, org.id) is not None


class TestTheSameWorkspaceComingBack:
    async def test_a_second_admin_cannot_restart_the_workspace_trial(self, db):
        """The trial belongs to the organization, not to whoever clicked.

        Otherwise inviting a colleague — or a second account of your own — buys
        another seven days, every seven days, forever.
        """
        owner = await make_user(db, "owner@acme.test")
        org = await make_org(db, owner)
        await grant_trial(db, org, owner, days_ago=20)

        colleague = await make_user(db, "colleague@other.test")
        db.add(
            OrganizationMember(
                organization_id=org.id, user_id=colleague.id, role="admin"
            )
        )
        await db.commit()

        assert (
            await _trial_already_used(db, colleague, org.id)
            == "organization_already_trialed"
        )

    async def test_a_trial_subscription_alone_is_enough_evidence(self, db, plan):
        """No grant row — a pre-ledger trial, or one whose insert was lost.

        The subscription is then the only record that the workspace has had its
        trial, and it still has to count.
        """
        owner = await make_user(db, "legacy@acme.test")
        org = await make_org(db, owner)
        await add_subscription(
            db, org, plan, status=STATUS_EXPIRED, source=SOURCE_TRIAL
        )

        other = await make_user(db, "fresh@elsewhere.test")
        assert (
            await _trial_already_used(db, other, org.id)
            == "organization_has_prior_trial_subscription"
        )

    async def test_a_paid_subscription_does_not_count_as_a_trial(self, db, plan):
        """Someone who only ever paid us has not spent their free trial."""
        owner = await make_user(db, "payer@acme.test")
        org = await make_org(db, owner)
        await add_subscription(
            db, org, plan, status=STATUS_ACTIVE, source=SOURCE_STRIPE
        )

        assert await _trial_already_used(db, owner, org.id) is None


class TestEmailDomain:
    async def test_a_shared_consumer_domain_is_not_evidence(self, db):
        """Two gmail.com signups are two people, not one person twice."""
        first = await make_user(db, "one@gmail.com")
        first_org = await make_org(db, first, name="One")
        await grant_trial(db, first_org, first, days_ago=10)

        second = await make_user(db, "two@gmail.com")
        second_org = await make_org(db, second, name="Two")
        assert await _trial_already_used(db, second, second_org.id) is None

    async def test_a_corporate_domain_collision_is_allowed_by_default(self, db):
        """A second team at the same company is a real, common case."""
        first = await make_user(db, "ada@bigco.test")
        first_org = await make_org(db, first, name="Eng")
        await grant_trial(db, first_org, first, days_ago=10)

        second = await make_user(db, "grace@bigco.test")
        second_org = await make_org(db, second, name="Sales")
        assert await _trial_already_used(db, second, second_org.id) is None

    async def test_a_corporate_domain_collision_is_refused_when_configured(
        self, db, monkeypatch
    ):
        monkeypatch.setattr(
            billing_endpoints, "BLOCK_REPEAT_TRIALS_BY_DOMAIN", True, raising=True
        )
        first = await make_user(db, "ada@bigco.test")
        first_org = await make_org(db, first, name="Eng")
        await grant_trial(db, first_org, first, days_ago=10)

        second = await make_user(db, "grace@bigco.test")
        second_org = await make_org(db, second, name="Sales")
        assert (
            await _trial_already_used(db, second, second_org.id)
            == "domain_already_trialed"
        )


class TestNoTrialsThroughThePaidEndpoint:
    """``POST /billing/subscription`` must not mint trials of its own.

    A client-chosen ``trial_days`` there reached Stripe as
    ``trial_period_days`` and produced a free trial with no grant recorded — a
    way around the whole rule, repeatable every time the last one lapsed.
    """

    async def test_a_requested_trial_length_is_refused(self):
        request = CreateSubscriptionRequest(
            plan_id=uuid.uuid4(), payment_method_id="pm_test", trial_days=30
        )
        with pytest.raises(HTTPException) as caught:
            # Refused before anything else is touched, so the remaining
            # dependencies are never used.
            await create_subscription(request, None, None, None, None)

        assert caught.value.status_code == 400
        assert "/billing/trial" in caught.value.detail

    async def test_the_default_is_no_trial(self):
        request = CreateSubscriptionRequest(
            plan_id=uuid.uuid4(), payment_method_id="pm_test"
        )
        assert request.trial_days == 0
