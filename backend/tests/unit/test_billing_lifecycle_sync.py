"""
Trial and paid-plan expiry, kept in step with Stripe and Polar.

Covers the parts of the lifecycle that depend on provider webhooks arriving —
and on the reconciler catching the ones that do not:

* trial reminders go out at T-3 *and* T-1;
* a Stripe subscription that ends (deleted, unpaid, revoked) ends access at the
  provider's end date, not at a period end still in the future;
* a Stripe renewal records the period being paid for, not the one just ended;
* a queued downgrade is applied when the provider starts the next period;
* a paid subscription whose webhooks were lost is re-synced from its provider.

Uses in-memory SQLite, like ``test_subscription_lifecycle``; no network.
"""

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database import Base
from app.models.subscription import (
    SOURCE_MANUAL,
    SOURCE_POLAR,
    SOURCE_STRIPE,
    SOURCE_TRIAL,
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_EXPIRED,
    STATUS_PAST_DUE,
    STATUS_TRIALING,
    Subscription,
    SubscriptionEvent,
    SubscriptionPlan,
)
from app.models.user import Organization, OrganizationMember, User
from app.services.billing import catalog, events, polar_service
from app.services.billing import stripe_service as stripe_module
from app.services.billing.entitlements import EntitlementService
from app.services.billing.reconciler import (
    reconcile_subscriptions,
    reset_expired_period_counters,
)
from app.services.billing.stripe_service import StripeService

pytestmark = [pytest.mark.unit, pytest.mark.billing]


# ==================== Fixtures ====================


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
    organization = Organization(name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}", owner_id=user.id)
    db.add(organization)
    await db.flush()
    db.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    await db.commit()
    return organization


def _plan(slug: str, tier: int, price: int) -> SubscriptionPlan:
    document = catalog.PLAN_ENTITLEMENTS["voice-ai"]
    return SubscriptionPlan(
        slug=slug,
        name=slug.title(),
        tier=tier,
        stripe_product_id=f"prod_{uuid.uuid4().hex[:10]}",
        stripe_price_id=f"price_{uuid.uuid4().hex[:10]}",
        polar_product_id=f"polar-{slug}-monthly",
        polar_product_id_yearly=f"polar-{slug}-yearly",
        price_monthly=price,
        entitlements={
            "features": dict(document["features"]),
            "limits": dict(document["limits"]),
            "overage": dict(document["overage"]),
        },
        trial_days=7,
        is_trialable=True,
    )


@pytest_asyncio.fixture
async def plan(db: AsyncSession) -> SubscriptionPlan:
    p = _plan("voice-ai", 2, 359)
    db.add(p)
    await db.commit()
    return p


@pytest_asyncio.fixture
async def small_plan(db: AsyncSession) -> SubscriptionPlan:
    p = _plan("sales-chatbot", 1, 99)
    db.add(p)
    await db.commit()
    return p


def _ts(value: datetime) -> int:
    return int((value - datetime(1970, 1, 1)).total_seconds())


async def paid(
    db, org, plan, *, source=SOURCE_STRIPE, started_days_ago=10, length_days=30, **extra
) -> Subscription:
    start = datetime.utcnow().replace(microsecond=0) - timedelta(days=started_days_ago)
    sub = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        status=STATUS_ACTIVE,
        source=source,
        billing_period="monthly",
        current_period_start=start,
        current_period_end=start + timedelta(days=length_days),
        current_period_minutes=77,
    )
    if source == SOURCE_STRIPE:
        sub.stripe_subscription_id = f"sub_{uuid.uuid4().hex[:10]}"
        sub.stripe_customer_id = "cus_x"
    elif source == SOURCE_POLAR:
        sub.polar_subscription_id = f"psub_{uuid.uuid4().hex[:10]}"
        sub.polar_customer_id = "pcus_x"
    for key, value in extra.items():
        setattr(sub, key, value)
    db.add(sub)
    await db.commit()
    return sub


@pytest.fixture
def stripe(monkeypatch) -> StripeService:
    """A Stripe service that never calls Stripe: invoice sync is stubbed out."""
    service = StripeService(api_key="", webhook_secret="", configure_sdk=False)

    async def no_sync(db, stripe_invoice_id):
        return None

    monkeypatch.setattr(service, "sync_invoice", no_sync)
    return service


async def deliver(service: StripeService, db, event_type: str, data: dict) -> bool:
    return await service.handle_webhook_event(
        db, {"id": f"evt_{uuid.uuid4().hex}", "type": event_type, "data": {"object": data}}
    )


async def resolve(db, org):
    return await EntitlementService().resolve(db, org.id, fresh=True)


async def event_types(db, sub_id) -> list:
    result = await db.execute(
        select(SubscriptionEvent.event_type).where(SubscriptionEvent.subscription_id == sub_id)
    )
    return [row[0] for row in result]


# ==================== Trial reminders ====================


class TestTrialReminders:
    async def test_the_one_day_reminder_follows_the_three_day_one(self, db, org, plan):
        now = datetime.utcnow()
        sub = Subscription(
            organization_id=org.id,
            plan_id=plan.id,
            status=STATUS_TRIALING,
            source=SOURCE_TRIAL,
            billing_period="monthly",
            current_period_start=now - timedelta(days=4),
            current_period_end=now + timedelta(days=2, hours=12),
            trial_start=now - timedelta(days=4),
            trial_end=now + timedelta(days=2, hours=12),
        )
        db.add(sub)
        await db.commit()

        at_three_days = await reconcile_subscriptions(db, now=now)
        a_day_later = await reconcile_subscriptions(db, now=now + timedelta(days=2))
        again = await reconcile_subscriptions(db, now=now + timedelta(days=2, minutes=15))

        notices = (
            await db.execute(
                select(SubscriptionEvent.payload).where(
                    SubscriptionEvent.subscription_id == sub.id,
                    SubscriptionEvent.event_type == events.NOTICE_SENT,
                )
            )
        ).scalars().all()
        assert at_three_days.notices_sent == 1
        assert a_day_later.notices_sent == 1
        assert again.notices_sent == 0
        assert sorted(n["notice"] for n in notices) == ["trial_t_minus_1", "trial_t_minus_3"]


# ==================== Stripe status sync ====================


class TestStripeSubscriptionSync:
    async def test_deleted_subscription_ends_access_now_not_at_period_end(
        self, db, org, plan, stripe
    ):
        """Dunning exhausted: the new period was never paid for."""
        sub = await paid(db, org, plan, started_days_ago=2)
        ended = datetime.utcnow().replace(microsecond=0)

        assert await deliver(stripe, db, "customer.subscription.deleted", {
            "id": sub.stripe_subscription_id,
            "status": "canceled",
            "current_period_start": _ts(sub.current_period_start),
            "current_period_end": _ts(sub.current_period_end),
            "ended_at": _ts(ended),
            "cancel_at_period_end": False,
        })

        await db.refresh(sub)
        assert sub.status == STATUS_CANCELED
        assert sub.current_period_end <= ended
        assert (await resolve(db, org)).status == STATUS_EXPIRED

    async def test_deleted_at_period_end_keeps_the_paid_period(self, db, org, plan, stripe):
        sub = await paid(db, org, plan, started_days_ago=30)  # period ends now
        end = sub.current_period_end

        await deliver(stripe, db, "customer.subscription.deleted", {
            "id": sub.stripe_subscription_id,
            "status": "canceled",
            "current_period_start": _ts(sub.current_period_start),
            "current_period_end": _ts(end),
            "ended_at": _ts(end),
        })

        await db.refresh(sub)
        assert sub.current_period_end == end
        report = await reconcile_subscriptions(db, now=end + timedelta(minutes=1))
        assert report.canceled_to_expired == 1

    async def test_unpaid_is_past_due_with_a_dunning_deadline(self, db, org, plan, stripe):
        sub = await paid(db, org, plan)

        await deliver(stripe, db, "customer.subscription.updated", {
            "id": sub.stripe_subscription_id,
            "status": "unpaid",
            "current_period_start": _ts(sub.current_period_start),
            "current_period_end": _ts(sub.current_period_end),
        })

        await db.refresh(sub)
        assert sub.status == STATUS_PAST_DUE
        assert sub.grace_period_end is not None
        assert (await resolve(db, org)).is_live

    async def test_a_stripe_trialing_status_never_hands_out_trial_limits(
        self, db, org, plan, stripe
    ):
        sub = await paid(db, org, plan)

        await deliver(stripe, db, "customer.subscription.updated", {
            "id": sub.stripe_subscription_id,
            "status": "trialing",
            "current_period_start": _ts(sub.current_period_start),
            "current_period_end": _ts(sub.current_period_end),
        })

        await db.refresh(sub)
        assert sub.status == STATUS_ACTIVE
        ent = await resolve(db, org)
        assert ent.limit(catalog.LIMIT_AGENTS) == plan.entitlements["limits"][catalog.LIMIT_AGENTS]

    async def test_periods_are_read_from_items_on_newer_api_versions(
        self, db, org, plan, stripe
    ):
        """Webhook endpoints on API 2025-03-31+ put the period on the item."""
        sub = await paid(db, org, plan, started_days_ago=31)
        new_start = sub.current_period_end
        new_end = new_start + timedelta(days=30)

        await deliver(stripe, db, "customer.subscription.updated", {
            "id": sub.stripe_subscription_id,
            "status": "active",
            "items": {"data": [{"current_period_start": _ts(new_start), "current_period_end": _ts(new_end)}]},
        })

        await db.refresh(sub)
        assert sub.current_period_end == new_end


# ==================== Stripe renewals ====================


def renewal_invoice(sub: Subscription, *, new_end: datetime, basil=False) -> dict:
    """A ``subscription_cycle`` invoice: its own period is the one that ended."""
    data = {
        "id": f"in_{uuid.uuid4().hex[:10]}",
        "billing_reason": "subscription_cycle",
        "period_start": _ts(sub.current_period_start),
        "period_end": _ts(sub.current_period_end),
        "lines": {"data": [{"period": {"start": _ts(sub.current_period_end), "end": _ts(new_end)}}]},
    }
    if basil:
        data["parent"] = {"subscription_details": {"subscription": sub.stripe_subscription_id}}
    else:
        data["subscription"] = sub.stripe_subscription_id
    return data


class TestStripeRenewal:
    async def test_renewal_records_the_new_period_not_the_one_that_ended(
        self, db, org, plan, stripe
    ):
        sub = await paid(db, org, plan, started_days_ago=30)
        new_end = sub.current_period_end + timedelta(days=30)

        await deliver(stripe, db, "invoice.paid", renewal_invoice(sub, new_end=new_end))

        await db.refresh(sub)
        assert sub.current_period_end == new_end
        assert sub.current_period_minutes == 0
        assert events.RENEWED in await event_types(db, sub.id)

    async def test_renewal_invoice_in_the_newer_shape_is_matched(self, db, org, plan, stripe):
        sub = await paid(db, org, plan, started_days_ago=30)
        new_end = sub.current_period_end + timedelta(days=30)

        await deliver(stripe, db, "invoice.paid", renewal_invoice(sub, new_end=new_end, basil=True))

        await db.refresh(sub)
        assert sub.current_period_end == new_end

    async def test_a_proration_invoice_does_not_reset_usage(self, db, org, plan, stripe):
        sub = await paid(db, org, plan)
        end = sub.current_period_end

        await deliver(stripe, db, "invoice.paid", {
            "id": "in_proration",
            "subscription": sub.stripe_subscription_id,
            "billing_reason": "subscription_update",
            "lines": {"data": []},
        })

        await db.refresh(sub)
        assert sub.current_period_minutes == 77
        assert sub.current_period_end == end

    async def test_queued_downgrade_applies_when_the_period_rolls(
        self, db, org, plan, small_plan, stripe
    ):
        sub = await paid(db, org, plan, started_days_ago=30, scheduled_plan_id=small_plan.id)
        new_end = sub.current_period_end + timedelta(days=30)

        await deliver(stripe, db, "invoice.paid", renewal_invoice(sub, new_end=new_end))

        await db.refresh(sub)
        assert sub.plan_id == small_plan.id
        assert sub.scheduled_plan_id is None
        assert events.PLAN_CHANGED in await event_types(db, sub.id)

    async def test_queued_downgrade_waits_while_the_period_is_unchanged(
        self, db, org, plan, small_plan, stripe
    ):
        """The price change at downgrade time fires subscription.updated mid-period."""
        sub = await paid(db, org, plan, scheduled_plan_id=small_plan.id)

        await deliver(stripe, db, "customer.subscription.updated", {
            "id": sub.stripe_subscription_id,
            "status": "active",
            "current_period_start": _ts(sub.current_period_start),
            "current_period_end": _ts(sub.current_period_end),
        })

        await db.refresh(sub)
        assert sub.plan_id == plan.id
        assert sub.scheduled_plan_id == small_plan.id


class TestManualComps:
    async def test_counter_roll_applies_a_queued_downgrade(self, db, org, plan, small_plan):
        sub = await paid(
            db, org, plan, source=SOURCE_MANUAL, started_days_ago=31, scheduled_plan_id=small_plan.id
        )

        assert await reset_expired_period_counters(db) == 1

        await db.refresh(sub)
        assert sub.plan_id == small_plan.id
        assert sub.scheduled_plan_id is None


# ==================== Lost webhooks ====================


class _FakePolar:
    def __init__(self, remote=None, error=None):
        self.remote, self.error = remote, error

    async def get_subscription(self, subscription_id):
        if self.error:
            raise self.error
        return self.remote


class TestProviderResync:
    async def test_a_polar_revocation_missed_by_webhook_is_picked_up(
        self, db, org, plan, monkeypatch
    ):
        sub = await paid(db, org, plan, source=SOURCE_POLAR, started_days_ago=40)
        ended = datetime.utcnow() - timedelta(days=9)
        remote = {
            "id": sub.polar_subscription_id,
            "status": "canceled",
            "product_id": plan.polar_product_id,
            "current_period_start": sub.current_period_start.isoformat() + "Z",
            "current_period_end": sub.current_period_end.isoformat() + "Z",
            "ended_at": ended.isoformat() + "Z",
            "cancel_at_period_end": False,
        }
        monkeypatch.setattr(settings, "POLAR_ACCESS_TOKEN", "polar_oat_test")
        monkeypatch.setattr(polar_service, "get_polar_client", lambda: _FakePolar(remote))

        report = await reconcile_subscriptions(db)

        await db.refresh(sub)
        assert report.resynced == 1
        assert sub.status in (STATUS_CANCELED, STATUS_EXPIRED)
        assert not (await resolve(db, org)).is_live

    async def test_a_polar_renewal_missed_by_webhook_moves_the_period(
        self, db, org, plan, monkeypatch
    ):
        sub = await paid(db, org, plan, source=SOURCE_POLAR, started_days_ago=40)
        new_end = datetime.utcnow().replace(microsecond=0) + timedelta(days=20)
        remote = {
            "id": sub.polar_subscription_id,
            "status": "active",
            "product_id": plan.polar_product_id,
            "current_period_start": (new_end - timedelta(days=30)).isoformat() + "Z",
            "current_period_end": new_end.isoformat() + "Z",
            "cancel_at_period_end": False,
        }
        monkeypatch.setattr(settings, "POLAR_ACCESS_TOKEN", "polar_oat_test")
        monkeypatch.setattr(polar_service, "get_polar_client", lambda: _FakePolar(remote))

        report = await reconcile_subscriptions(db)

        await db.refresh(sub)
        assert sub.status == STATUS_ACTIVE
        assert sub.current_period_end == new_end
        assert report.stale_active == 0

    async def test_an_unreachable_provider_leaves_the_customer_live(
        self, db, org, plan, monkeypatch
    ):
        sub = await paid(db, org, plan, source=SOURCE_POLAR, started_days_ago=40)
        monkeypatch.setattr(settings, "POLAR_ACCESS_TOKEN", "polar_oat_test")
        monkeypatch.setattr(
            polar_service,
            "get_polar_client",
            lambda: _FakePolar(error=polar_service.PolarError("down")),
        )

        report = await reconcile_subscriptions(db)

        await db.refresh(sub)
        assert sub.status == STATUS_ACTIVE
        assert report.stale_active == 1
        assert (await resolve(db, org)).is_live

    async def test_a_stripe_cancellation_missed_by_webhook_is_picked_up(
        self, db, org, plan, monkeypatch
    ):
        sub = await paid(db, org, plan, started_days_ago=40)
        ended = datetime.utcnow().replace(microsecond=0) - timedelta(days=10)
        remote = {
            "id": sub.stripe_subscription_id,
            "status": "canceled",
            "current_period_start": _ts(sub.current_period_start),
            "current_period_end": _ts(sub.current_period_end),
            "ended_at": _ts(ended),
        }
        monkeypatch.setattr(type(settings), "stripe_configured", property(lambda self: True))

        async def fake_service():
            return StripeService(api_key="", webhook_secret="", configure_sdk=False)

        monkeypatch.setattr(stripe_module, "get_stripe_service", fake_service)
        import stripe as stripe_sdk

        monkeypatch.setattr(stripe_sdk.Subscription, "retrieve", lambda sub_id: remote)

        report = await reconcile_subscriptions(db)

        await db.refresh(sub)
        assert report.resynced == 1
        assert not (await resolve(db, org)).is_live


# ==================== Polar linking ====================


class TestPolarLinking:
    async def test_a_polar_payment_never_orphans_a_stripe_subscription_in_dunning(
        self, db, org, plan
    ):
        stripe_sub = await paid(db, org, plan, status=STATUS_PAST_DUE)
        now = datetime.utcnow()

        await polar_service.handle_webhook_event(db, uuid.uuid4().hex, {
            "type": "subscription.active",
            "data": {
                "id": "psub_dup",
                "status": "active",
                "product_id": plan.polar_product_id,
                "customer_id": "pcus_1",
                "current_period_start": now.isoformat() + "Z",
                "current_period_end": (now + timedelta(days=30)).isoformat() + "Z",
                "metadata": {"organization_id": str(org.id)},
            },
        })

        await db.refresh(stripe_sub)
        assert stripe_sub.source == SOURCE_STRIPE
        assert stripe_sub.polar_subscription_id is None
