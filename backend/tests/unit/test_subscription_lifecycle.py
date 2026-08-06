"""
The subscription lifecycle, end to end, against a real database.

Covers the journey a customer actually takes — trial → grace → expired, and
trial → paid — plus the two properties that make the reconciler safe to run on
a schedule: it is idempotent, and it never expires a paying customer over a
missed webhook.

Uses its own in-memory SQLite engine and session rather than the shared
``conftest`` fixtures, so these run without a Postgres test database.
"""

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.subscription import (
    SOURCE_STRIPE,
    SOURCE_TRIAL,
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_EXPIRED,
    STATUS_GRACE,
    STATUS_PAST_DUE,
    STATUS_TRIALING,
    Subscription,
    SubscriptionEvent,
    SubscriptionPlan,
    TrialGrant,
)
from app.models.user import Organization, OrganizationMember, User
from app.api.v1.endpoints.billing import _trial_already_used
from app.services.billing import catalog
from app.services.billing.entitlements import (
    EntitlementService,
    TRIAL_GRACE_DAYS,
)
from app.services.billing.reconciler import reconcile_subscriptions

pytestmark = [pytest.mark.unit, pytest.mark.billing]


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """A throwaway SQLite database with the full schema."""
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


@pytest_asyncio.fixture
async def org(db: AsyncSession) -> Organization:
    """An organization with an owner, so notices have somewhere to go."""
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

    db.add(
        OrganizationMember(
            organization_id=organization.id, user_id=user.id, role="owner"
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
        included_minutes=3000,
        included_calls=600,
        max_agents=5,
        max_phone_numbers=5,
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


async def make_trial(
    db: AsyncSession, org: Organization, plan: SubscriptionPlan, *, started_days_ago: int
) -> Subscription:
    """A trial that began `started_days_ago` days back, still marked trialing."""
    start = datetime.utcnow() - timedelta(days=started_days_ago)
    end = start + timedelta(days=plan.trial_days)
    subscription = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        status=STATUS_TRIALING,
        source=SOURCE_TRIAL,
        billing_period="monthly",
        current_period_start=start,
        current_period_end=end,
        trial_start=start,
        trial_end=end,
    )
    db.add(subscription)
    await db.commit()
    return subscription


async def event_types(db: AsyncSession, subscription_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        select(SubscriptionEvent.event_type).where(
            SubscriptionEvent.subscription_id == subscription_id
        )
    )
    return [row[0] for row in result]


# ==================== Trial expiry ====================


class TestTrialExpiry:
    async def test_running_trial_is_left_alone(self, db, org, plan):
        subscription = await make_trial(db, org, plan, started_days_ago=2)

        await reconcile_subscriptions(db)
        await db.refresh(subscription)

        assert subscription.status == STATUS_TRIALING
        assert subscription.grace_period_end is None

    async def test_lapsed_trial_moves_to_grace(self, db, org, plan):
        subscription = await make_trial(db, org, plan, started_days_ago=8)

        report = await reconcile_subscriptions(db)
        await db.refresh(subscription)

        assert report.trials_to_grace == 1
        assert subscription.status == STATUS_GRACE
        assert subscription.grace_period_end is not None
        assert "trial_expired" in await event_types(db, subscription.id)

    async def test_grace_keeps_runtime_alive(self, db, org, plan):
        """A Friday expiry must not be a weekend outage."""
        subscription = await make_trial(db, org, plan, started_days_ago=8)
        await reconcile_subscriptions(db)

        ent = await EntitlementService().resolve(db, org.id, fresh=True)
        assert ent.status == STATUS_GRACE
        assert ent.is_live
        assert ent.has(catalog.INBOUND_CALLS)

    async def test_grace_runs_out_and_the_account_goes_read_only(self, db, org, plan):
        """A trial whose grace has also lapsed lands on `expired` in one pass.

        The transitions run in order within a single sweep, so a trial that has
        been dead for a while catches up immediately rather than needing one
        pass per stage — which matters after any downtime.
        """
        subscription = await make_trial(
            db, org, plan, started_days_ago=plan.trial_days + TRIAL_GRACE_DAYS + 1
        )

        report = await reconcile_subscriptions(db)
        await db.refresh(subscription)

        assert report.trials_to_grace == 1
        assert report.grace_to_expired == 1
        assert subscription.status == STATUS_EXPIRED
        assert subscription.expired_at is not None

        ent = await EntitlementService().resolve(db, org.id, fresh=True)
        assert ent.is_read_only
        assert not ent.has(catalog.INBOUND_CALLS)

        # And a second sweep leaves it exactly where it is.
        assert (await reconcile_subscriptions(db)).changed == 0

    async def test_grace_ends_on_a_later_pass_when_it_lapses_mid_window(
        self, db, org, plan
    ):
        """The ordinary path: grace is entered, then ends days later."""
        subscription = await make_trial(db, org, plan, started_days_ago=8)

        first = await reconcile_subscriptions(db)
        assert first.trials_to_grace == 1
        assert first.grace_to_expired == 0

        # Time passes and the cushion runs out.
        subscription.grace_period_end = datetime.utcnow() - timedelta(minutes=1)
        await db.commit()

        second = await reconcile_subscriptions(db)
        await db.refresh(subscription)

        assert second.grace_to_expired == 1
        assert subscription.status == STATUS_EXPIRED

    async def test_expiry_is_derived_before_the_reconciler_ever_runs(
        self, db, org, plan
    ):
        """The property the whole design rests on.

        The row still says ``trialing``; access must already be denied. This is
        what makes a dead scheduler a reporting problem rather than a free
        product.
        """
        subscription = await make_trial(
            db, org, plan, started_days_ago=plan.trial_days + TRIAL_GRACE_DAYS + 5
        )
        assert subscription.status == STATUS_TRIALING  # never reconciled

        ent = await EntitlementService().resolve(db, org.id, fresh=True)

        assert ent.status == STATUS_EXPIRED
        assert not ent.is_live
        assert ent.stored_status == STATUS_TRIALING

    async def test_reconciler_is_idempotent(self, db, org, plan):
        """Running twice must change nothing the second time.

        It runs every 15 minutes and may run in several workers at once, so a
        second pass duplicating events would mean duplicate emails.
        """
        subscription = await make_trial(db, org, plan, started_days_ago=8)

        first = await reconcile_subscriptions(db)
        events_after_first = await event_types(db, subscription.id)

        second = await reconcile_subscriptions(db)
        events_after_second = await event_types(db, subscription.id)

        assert first.changed == 1
        assert second.changed == 0
        assert events_after_first == events_after_second

    async def test_notices_send_once_per_threshold(self, db, org, plan):
        """96 reconciler passes a day must not mean 96 emails."""
        await make_trial(db, org, plan, started_days_ago=6)  # 1 day left

        first = await reconcile_subscriptions(db)
        second = await reconcile_subscriptions(db)

        assert first.notices_sent == 1
        assert second.notices_sent == 0


# ==================== Paying customers ====================


class TestPayingCustomers:
    async def test_active_subscription_past_period_end_is_not_expired(
        self, db, org, plan
    ):
        """Fail open for payers: a missed webhook must not lock anyone out."""
        subscription = Subscription(
            organization_id=org.id,
            plan_id=plan.id,
            status=STATUS_ACTIVE,
            source=SOURCE_STRIPE,
            stripe_subscription_id=f"sub_{uuid.uuid4().hex[:10]}",
            stripe_customer_id="cus_x",
            billing_period="monthly",
            current_period_start=datetime.utcnow() - timedelta(days=40),
            current_period_end=datetime.utcnow() - timedelta(days=10),
        )
        db.add(subscription)
        await db.commit()

        report = await reconcile_subscriptions(db)
        await db.refresh(subscription)

        assert subscription.status == STATUS_ACTIVE
        assert report.stale_active == 1  # flagged for investigation, not expired

        ent = await EntitlementService().resolve(db, org.id, fresh=True)
        assert ent.is_live

    async def test_past_due_survives_dunning_then_expires(self, db, org, plan):
        subscription = Subscription(
            organization_id=org.id,
            plan_id=plan.id,
            status=STATUS_PAST_DUE,
            source=SOURCE_STRIPE,
            stripe_subscription_id=f"sub_{uuid.uuid4().hex[:10]}",
            stripe_customer_id="cus_x",
            billing_period="monthly",
            current_period_start=datetime.utcnow() - timedelta(days=10),
            current_period_end=datetime.utcnow() + timedelta(days=20),
            grace_period_end=datetime.utcnow() + timedelta(days=3),
        )
        db.add(subscription)
        await db.commit()

        await reconcile_subscriptions(db)
        await db.refresh(subscription)
        assert subscription.status == STATUS_PAST_DUE

        ent = await EntitlementService().resolve(db, org.id, fresh=True)
        assert ent.is_live  # Stripe is still retrying the card

        # Dunning exhausted.
        subscription.grace_period_end = datetime.utcnow() - timedelta(hours=1)
        await db.commit()

        report = await reconcile_subscriptions(db)
        await db.refresh(subscription)
        assert report.past_due_to_expired == 1
        assert subscription.status == STATUS_EXPIRED

    async def test_cancelled_keeps_access_until_the_period_ends(self, db, org, plan):
        subscription = Subscription(
            organization_id=org.id,
            plan_id=plan.id,
            status=STATUS_CANCELED,
            source=SOURCE_STRIPE,
            stripe_subscription_id=f"sub_{uuid.uuid4().hex[:10]}",
            stripe_customer_id="cus_x",
            billing_period="monthly",
            current_period_start=datetime.utcnow() - timedelta(days=5),
            current_period_end=datetime.utcnow() + timedelta(days=25),
            canceled_at=datetime.utcnow(),
            cancel_at_period_end=True,
        )
        db.add(subscription)
        await db.commit()

        await reconcile_subscriptions(db)
        ent = await EntitlementService().resolve(db, org.id, fresh=True)

        assert ent.is_live
        assert ent.cancel_at_period_end


# ==================== Entitlement resolution ====================


class TestResolution:
    async def test_no_subscription_means_no_access(self, db, org):
        ent = await EntitlementService().resolve(db, org.id, fresh=True)

        assert ent.status == STATUS_EXPIRED
        assert not ent.has_subscription
        assert ent.is_read_only

    async def test_trial_gets_trial_limits_not_plan_limits(self, db, org, plan):
        """Trialling the top plan must not hand out the top plan's allowance."""
        await make_trial(db, org, plan, started_days_ago=1)

        ent = await EntitlementService().resolve(db, org.id, fresh=True)

        assert ent.is_trial
        assert ent.plan_slug == "voice-ai"
        # Every feature, but the trial's own consumption caps.
        assert ent.has(catalog.LEAD_SCORING)
        assert ent.limit(catalog.LIMIT_MINUTES) == (
            catalog.TRIAL_ENTITLEMENTS["limits"][catalog.LIMIT_MINUTES]
        )
        assert ent.limit(catalog.LIMIT_MINUTES) < plan.included_minutes
        assert ent.overage_allowed is False

    async def test_paid_plan_gets_the_plan_document(self, db, org, plan):
        subscription = Subscription(
            organization_id=org.id,
            plan_id=plan.id,
            status=STATUS_ACTIVE,
            source=SOURCE_STRIPE,
            stripe_subscription_id=f"sub_{uuid.uuid4().hex[:10]}",
            stripe_customer_id="cus_x",
            billing_period="monthly",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30),
        )
        db.add(subscription)
        await db.commit()

        ent = await EntitlementService().resolve(db, org.id, fresh=True)

        assert ent.limit(catalog.LIMIT_MINUTES) == 3000
        assert ent.limit(catalog.LIMIT_AGENTS) == 5
        assert ent.overage_allowed is True

    async def test_usage_counters_feed_the_quota_check(self, db, org, plan):
        subscription = await make_trial(db, org, plan, started_days_ago=1)
        cap = catalog.TRIAL_ENTITLEMENTS["limits"][catalog.LIMIT_CALLS]
        subscription.current_period_calls = cap
        await db.commit()

        ent = await EntitlementService().resolve(db, org.id, fresh=True)

        assert ent.used(catalog.LIMIT_CALLS) == cap
        assert not ent.within(catalog.LIMIT_CALLS)
        assert ent.remaining(catalog.LIMIT_CALLS) == 0

    async def test_runtime_check_blocks_a_trial_at_its_cap(self, db, org, plan):
        """No card on file, so the trial stops rather than billing overage."""
        subscription = await make_trial(db, org, plan, started_days_ago=1)
        subscription.current_period_calls = catalog.TRIAL_ENTITLEMENTS["limits"][
            catalog.LIMIT_CALLS
        ]
        await db.commit()

        service = EntitlementService()
        service.invalidate(org.id)
        allowed, reason = await service.check_runtime(
            db, org.id, catalog.INBOUND_CALLS
        )

        assert allowed is False
        assert reason == "limit_exceeded"

    async def test_runtime_check_blocks_an_expired_account(self, db, org, plan):
        await make_trial(
            db, org, plan, started_days_ago=plan.trial_days + TRIAL_GRACE_DAYS + 2
        )

        allowed, reason = await EntitlementService().check_runtime(
            db, org.id, catalog.INBOUND_CALLS
        )

        assert allowed is False
        assert reason == "subscription_expired"

    async def test_cache_is_invalidated_on_change(self, db, org, plan):
        service = EntitlementService()
        subscription = await make_trial(db, org, plan, started_days_ago=1)

        first = await service.resolve(db, org.id)
        assert first.is_trial

        subscription.status = STATUS_EXPIRED
        subscription.expired_at = datetime.utcnow()
        await db.commit()

        # Still cached...
        assert (await service.resolve(db, org.id)).is_trial
        # ...until told otherwise.
        service.invalidate(org.id)
        assert (await service.resolve(db, org.id)).status == STATUS_EXPIRED

    async def test_resource_counts_come_from_the_owning_tables(self, db, org, plan):
        from app.models.agent import Agent

        await make_trial(db, org, plan, started_days_ago=1)
        db.add(
            Agent(
                user_id=uuid.uuid4(),
                organization_id=org.id,
                name="Receptionist",
                system_prompt="Hello",
            )
        )
        await db.commit()

        counts = await EntitlementService().usage_snapshot(db, org.id)

        assert counts[catalog.LIMIT_AGENTS] == 1
        assert counts[catalog.LIMIT_TEAM_MEMBERS] == 1  # the owner
        assert counts[catalog.LIMIT_PHONE_NUMBERS] == 0


# ==================== One trial per account ====================


async def _make_user(db: AsyncSession, email: str) -> User:
    user = User(email=email, hashed_password="x", full_name="Someone", is_active=True)
    db.add(user)
    await db.flush()
    return user


async def _make_org(db: AsyncSession, owner: User) -> Organization:
    organization = Organization(
        name="Other", slug=f"other-{uuid.uuid4().hex[:8]}", owner_id=owner.id
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


async def _grant(
    db: AsyncSession, organization: Organization, user: User
) -> TrialGrant:
    grant = TrialGrant(
        organization_id=organization.id,
        user_id=user.id,
        email_domain=user.email.split("@")[-1].lower(),
        granted_at=datetime.utcnow() - timedelta(days=30),
        expires_at=datetime.utcnow() - timedelta(days=23),
    )
    db.add(grant)
    await db.commit()
    return grant


class TestOneTrialPerAccount:
    """The free trial is once — and "once" has to survive the obvious dodges.

    Each test here is a way someone could otherwise get a second free week:
    coming back after theirs expired, bringing a colleague, or starting a fresh
    workspace. The rule is enforced in ``_trial_already_used``, which the trial
    endpoint consults before it creates anything.
    """

    async def test_a_first_time_workspace_may_start_one(self, db, org):
        owner = await db.get(User, org.owner_id)

        assert await _trial_already_used(db, owner, org.id) is None

    async def test_the_same_user_cannot_start_a_second_one(self, db, org):
        owner = await db.get(User, org.owner_id)
        await _grant(db, org, owner)

        assert await _trial_already_used(db, owner, org.id) == "organization_already_trialed"

    async def test_a_lapsed_trial_does_not_free_up_another(self, db, org, plan):
        """The case the user actually hits: trial ran out, try to start again."""
        owner = await db.get(User, org.owner_id)
        subscription = await make_trial(db, org, plan, started_days_ago=30)
        await _grant(db, org, owner)

        subscription.status = STATUS_EXPIRED
        subscription.expired_at = datetime.utcnow()
        await db.commit()

        # Nothing is live, so the "already subscribed" check would let this
        # through — the grant ledger is what stops it.
        assert await EntitlementService.live_subscription(db, org.id) is None
        assert await _trial_already_used(db, owner, org.id) is not None

    async def test_a_second_admin_cannot_restart_the_workspace_trial(self, db, org):
        """Invite a colleague, get another week — the loophole this closes.

        The newcomer has no grant of their own, so a per-user check alone says
        yes. The trial belongs to the organization.
        """
        owner = await db.get(User, org.owner_id)
        await _grant(db, org, owner)

        colleague = await _make_user(db, f"second-{uuid.uuid4().hex[:6]}@acme.test")
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

    async def test_a_new_workspace_does_not_reset_the_users_trial(self, db, org):
        """Delete the workspace, make another — the other obvious dodge."""
        owner = await db.get(User, org.owner_id)
        await _grant(db, org, owner)

        fresh = await _make_org(db, owner)

        assert await _trial_already_used(db, owner, fresh.id) == "user_already_trialed"

    async def test_a_trial_subscription_counts_even_without_a_grant_row(
        self, db, org, plan
    ):
        """Rows predating the grant ledger must not hand out a second trial."""
        owner = await db.get(User, org.owner_id)
        subscription = await make_trial(db, org, plan, started_days_ago=30)
        subscription.status = STATUS_EXPIRED
        await db.commit()

        assert (
            await _trial_already_used(db, owner, org.id)
            == "organization_has_prior_trial_subscription"
        )

    async def test_a_shared_consumer_domain_never_blocks_a_stranger(self, db, org):
        """Two unrelated gmail signups are not the same company."""
        first = await _make_user(db, f"a-{uuid.uuid4().hex[:6]}@gmail.com")
        first_org = await _make_org(db, first)
        await _grant(db, first_org, first)

        second = await _make_user(db, f"b-{uuid.uuid4().hex[:6]}@gmail.com")
        second_org = await _make_org(db, second)

        assert await _trial_already_used(db, second, second_org.id) is None

    async def test_a_corporate_domain_collision_is_allowed_but_recorded(self, db):
        """Second team at a real company: logged, not refused. See the flag."""
        import app.api.v1.endpoints.billing as billing_module

        assert billing_module.BLOCK_REPEAT_TRIALS_BY_DOMAIN is False

        first = await _make_user(db, f"a-{uuid.uuid4().hex[:6]}@bigco.test")
        first_org = await _make_org(db, first)
        await _grant(db, first_org, first)

        colleague = await _make_user(db, f"b-{uuid.uuid4().hex[:6]}@bigco.test")
        colleague_org = await _make_org(db, colleague)

        assert await _trial_already_used(db, colleague, colleague_org.id) is None
