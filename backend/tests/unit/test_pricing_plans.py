"""
The 29 Sep 2026 plans (Starter, Growth, Scale, Agency) against a real database.

Covers what the catalogue unit tests cannot: that startup seeding brings an
existing install onto the new plans without breaking anyone subscribed to the
launch plans, that minutes are metered once per call and priced past the
allowance, and that in-flight calls are counted for the concurrency limit.

Uses its own in-memory SQLite engine, like ``test_subscription_lifecycle``.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.call import Call
from app.models.subscription import (
    SOURCE_STRIPE,
    SOURCE_TRIAL,
    STATUS_ACTIVE,
    STATUS_TRIALING,
    Subscription,
    SubscriptionPlan,
    UsageRecord,
)
from app.models.user import Organization, OrganizationMember, User
from app.services.billing import catalog
from app.services.billing.entitlements import EntitlementService, get_entitlement_service
from app.services.billing.seed_plans import (
    DEFAULT_PLANS,
    LEGACY_PLAN_SLUGS,
    seed_default_plans,
)
from app.services.billing.usage_tracker import UsageTracker

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
    # The resolver cache is process-wide; do not leak answers between tests.
    get_entitlement_service().invalidate_all()


@pytest_asyncio.fixture
async def org(db: AsyncSession) -> Organization:
    user = User(
        email=f"owner-{uuid.uuid4().hex[:8]}@acme.test",
        hashed_password="x",
        full_name="Owner",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    organization = Organization(
        name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}", owner_id=user.id
    )
    db.add(organization)
    await db.flush()
    db.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    await db.commit()
    return organization


def legacy_plan(slug: str, *, stored_document: dict, admin_managed: bool = False) -> SubscriptionPlan:
    """A launch plan as an existing install has it: seeded before 29 Sep."""
    return SubscriptionPlan(
        slug=slug,
        name="Voice AI" if slug == "voice-ai" else "Sales Chatbot",
        tier=2 if slug == "voice-ai" else 1,
        stripe_product_id=f"local_{slug}",
        stripe_price_id=f"local_{slug}_monthly",
        price_monthly=Decimal("359.00"),
        entitlements=stored_document,
        trial_days=30,
        is_trialable=slug == "voice-ai",
        is_active=True,
        is_public=True,
        sort_order=1,
        admin_managed=admin_managed,
    )


def old_document(slug: str) -> dict:
    """A launch-plan document from before concurrent calls / custom voices."""
    doc = catalog.LEGACY_PLAN_ENTITLEMENTS[slug]
    limits = {
        k: v
        for k, v in doc["limits"].items()
        if k not in (catalog.LIMIT_CONCURRENT_CALLS, catalog.LIMIT_CUSTOM_VOICES)
    }
    limits[catalog.LIMIT_CALLS] = catalog.UNLIMITED
    features = dict(doc["features"])
    if slug == "sales-chatbot":
        features[catalog.CUSTOM_VOICE] = False
    return {"features": features, "limits": limits, "overage": {"allowed": True}}


async def plans_by_slug(db: AsyncSession) -> dict:
    result = await db.execute(select(SubscriptionPlan))
    return {plan.slug: plan for plan in result.scalars().all()}


# ==================== Seeding ====================


class TestSeeding:
    async def test_empty_database_gets_the_four_plans(self, db):
        assert await seed_default_plans(db) == 4
        plans = await plans_by_slug(db)
        assert set(plans) == {"starter", "growth", "scale", "agency"}

        growth = plans["growth"]
        assert (growth.price_monthly, growth.price_yearly) == (Decimal("149.00"), Decimal("1428.00"))
        assert growth.overage_rate_per_minute == Decimal("0.25")
        assert growth.entitlements["limits"][catalog.LIMIT_MINUTES] == 750
        assert growth.features["popular"] is True
        assert growth.trial_days == catalog.DEFAULT_TRIAL_DAYS == 14
        # Growth is the plan a trial attaches to, and the only one.
        assert [p.slug for p in plans.values() if p.is_trialable] == ["growth"]

    async def test_seeding_twice_creates_nothing_new(self, db):
        await seed_default_plans(db)
        assert await seed_default_plans(db) == 0
        assert len(await plans_by_slug(db)) == 4

    async def test_existing_install_gets_the_new_plans_and_retires_the_old(self, db):
        for slug in LEGACY_PLAN_SLUGS:
            db.add(legacy_plan(slug, stored_document=old_document(slug)))
        await db.commit()

        assert await seed_default_plans(db) == len(DEFAULT_PLANS)
        plans = await plans_by_slug(db)

        for slug in LEGACY_PLAN_SLUGS:
            old = plans[slug]
            # Off sale everywhere, but still there for its subscribers.
            assert not old.is_active and not old.is_public and not old.is_trialable
            assert old.sort_order > max(spec["sort_order"] for spec in DEFAULT_PLANS)
            limits = old.entitlements["limits"]
            # Keys added since are filled with the plan's own generous values —
            # never read as "zero lines" or "zero voices".
            assert limits[catalog.LIMIT_CONCURRENT_CALLS] == catalog.UNLIMITED
            assert limits[catalog.LIMIT_CUSTOM_VOICES] == catalog.UNLIMITED
            assert limits[catalog.LIMIT_MINUTES] == catalog.UNLIMITED
            # Custom voices were never gated before, so they stay on.
            assert old.entitlements["features"][catalog.CUSTOM_VOICE] is True

    async def test_retirement_happens_once(self, db):
        """An admin who puts a launch plan back on sale is not overruled."""
        db.add(legacy_plan("voice-ai", stored_document=old_document("voice-ai")))
        await db.commit()
        await seed_default_plans(db)

        plans = await plans_by_slug(db)
        plans["voice-ai"].is_active = True
        plans["voice-ai"].is_public = True
        await db.commit()

        await seed_default_plans(db)
        plans = await plans_by_slug(db)
        assert plans["voice-ai"].is_active and plans["voice-ai"].is_public

    async def test_restarts_never_lift_minute_allowances(self, db):
        """The old backfill reset every plan to unlimited minutes on startup."""
        await seed_default_plans(db)
        await seed_default_plans(db)
        plans = await plans_by_slug(db)
        assert plans["starter"].entitlements["limits"][catalog.LIMIT_MINUTES] == 200

    async def test_restart_strips_sms_from_plans_seeded_with_it(self, db):
        await seed_default_plans(db)
        starter = (await plans_by_slug(db))["starter"]
        document = dict(starter.entitlements)
        document["limits"] = {**document["limits"], catalog.LIMIT_SMS: 100}
        document["features"] = {**document["features"], catalog.SMS: True}
        starter.entitlements = document
        await db.commit()

        await seed_default_plans(db)
        starter = (await plans_by_slug(db))["starter"]
        assert catalog.LIMIT_SMS not in starter.entitlements["limits"]
        assert starter.entitlements["features"][catalog.SMS] is False

    async def test_admin_managed_plans_only_gain_missing_keys(self, db):
        document = old_document("voice-ai")
        document["limits"][catalog.LIMIT_AGENTS] = 7  # an admin's edit
        db.add(legacy_plan("voice-ai", stored_document=document, admin_managed=True))
        await db.commit()

        await seed_default_plans(db)
        limits = (await plans_by_slug(db))["voice-ai"].entitlements["limits"]
        assert limits[catalog.LIMIT_AGENTS] == 7
        assert limits[catalog.LIMIT_CONCURRENT_CALLS] == catalog.UNLIMITED


# ==================== Minutes ====================


async def subscribe(db, org, plan, *, trial=False, minutes_used=0) -> Subscription:
    now = datetime.utcnow()
    subscription = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        status=STATUS_TRIALING if trial else STATUS_ACTIVE,
        source=SOURCE_TRIAL if trial else SOURCE_STRIPE,
        billing_period="monthly",
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
        trial_start=now - timedelta(days=1) if trial else None,
        trial_end=now + timedelta(days=13) if trial else None,
        current_period_minutes=minutes_used,
    )
    db.add(subscription)
    await db.commit()
    return subscription


async def finished_call(db, org, seconds: int) -> Call:
    call = Call(
        user_id=org.owner_id,
        organization_id=org.id,
        direction="inbound",
        from_number="+15550000001",
        to_number="+15550000002",
        status="completed",
        duration_seconds=seconds,
        billable_duration_seconds=seconds,
        ended_at=datetime.utcnow(),
    )
    db.add(call)
    await db.commit()
    return call


async def minute_records(db, call_id):
    result = await db.execute(
        select(UsageRecord).where(
            UsageRecord.resource_id == call_id, UsageRecord.usage_type == "minutes"
        )
    )
    return result.scalars().all()


class TestMinuteMetering:
    async def test_minutes_are_counted_once_per_call(self, db, org):
        await seed_default_plans(db)
        plans = await plans_by_slug(db)
        subscription = await subscribe(db, org, plans["growth"])
        call = await finished_call(db, org, seconds=125)  # rounds up to 3

        await UsageTracker.record_call_usage(db, call.id, org.id)
        # The carrier's final callback can arrive twice.
        await UsageTracker.record_call_usage(db, call.id, org.id)

        await db.refresh(subscription)
        assert subscription.current_period_minutes == 3
        assert len(await minute_records(db, call.id)) == 1

    async def test_only_the_minutes_past_the_allowance_are_priced(self, db, org):
        await seed_default_plans(db)
        plans = await plans_by_slug(db)
        # Growth: 750 minutes, then $0.25. 748 used, a 5-minute call → 3 over.
        await subscribe(db, org, plans["growth"], minutes_used=748)
        call = await finished_call(db, org, seconds=300)

        await UsageTracker.record_call_usage(db, call.id, org.id)

        (record,) = await minute_records(db, call.id)
        assert record.quantity == 5
        assert record.unit_price == Decimal("0.25")
        assert record.total_amount == Decimal("0.75")

    async def test_a_call_inside_the_allowance_costs_nothing(self, db, org):
        await seed_default_plans(db)
        plans = await plans_by_slug(db)
        await subscribe(db, org, plans["starter"], minutes_used=10)
        call = await finished_call(db, org, seconds=60)

        await UsageTracker.record_call_usage(db, call.id, org.id)

        (record,) = await minute_records(db, call.id)
        assert record.total_amount == 0

    async def test_a_trial_never_prices_overage(self, db, org):
        await seed_default_plans(db)
        plans = await plans_by_slug(db)
        await subscribe(db, org, plans["growth"], trial=True, minutes_used=29)
        call = await finished_call(db, org, seconds=600)

        await UsageTracker.record_call_usage(db, call.id, org.id)

        (record,) = await minute_records(db, call.id)
        assert record.total_amount == 0

        # …and once the 30 minutes are gone, new calls are refused.
        get_entitlement_service().invalidate(org.id)
        allowed, reason = await EntitlementService().check_runtime(
            db, org.id, catalog.INBOUND_CALLS
        )
        assert (allowed, reason) == (False, "limit_exceeded")


# ==================== Concurrent calls ====================


class TestConcurrentCalls:
    async def live_call(self, db, org, *, status="in_progress", age=timedelta(0)) -> Call:
        call = Call(
            user_id=org.owner_id,
            organization_id=org.id,
            direction="inbound",
            from_number="+15550000001",
            to_number="+15550000002",
            status=status,
            created_at=datetime.utcnow() - age,
        )
        db.add(call)
        await db.commit()
        return call

    async def test_counts_only_calls_still_holding_a_line(self, db, org):
        service = EntitlementService()
        await self.live_call(db, org, status="ringing")
        await self.live_call(db, org, status="in_progress")
        await self.live_call(db, org, status="completed")
        # A row whose final callback was lost must not hold a line for ever.
        await self.live_call(db, org, age=timedelta(hours=6))

        assert await service.active_call_count(db, org.id) == 2

    async def test_the_call_being_answered_is_not_counted_against_itself(self, db, org):
        service = EntitlementService()
        this_call = await self.live_call(db, org)
        assert await service.active_call_count(db, org.id, exclude_call_id=this_call.id) == 0

    async def test_the_plan_limit_refuses_one_call_too_many(self, db, org):
        await seed_default_plans(db)
        plans = await plans_by_slug(db)
        await subscribe(db, org, plans["starter"])  # 3 lines
        for _ in range(3):
            await self.live_call(db, org)
        incoming = await self.live_call(db, org, status="initiated")

        service = EntitlementService()
        allowed, reason = await service.check_concurrency(
            db, org.id, exclude_call_id=incoming.id
        )
        assert (allowed, reason) == (False, "concurrency_limit")

    async def test_a_document_without_the_key_is_unlimited(self, db, org):
        plan = legacy_plan("voice-ai", stored_document=old_document("voice-ai"))
        db.add(plan)
        await db.commit()
        await subscribe(db, org, plan)
        for _ in range(50):
            await self.live_call(db, org)

        allowed, _ = await EntitlementService().check_concurrency(db, org.id)
        assert allowed
