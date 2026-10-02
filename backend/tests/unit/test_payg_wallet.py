"""
Pay As You Go: the prepaid wallet, end to end, against a real database.

What these tests pin down, in the order a customer meets it:

- the plan is seeded as a prepaid plan, apart from the subscription ladder;
- a top-up credits the wallet exactly once however many times the provider
  says so (Stripe confirm + webhook, a repeated Polar delivery), and a first
  top-up moves a trial onto the plan;
- a call is charged exactly once, at the plan's rate, from the wallet;
- an empty wallet blocks calls, and calls running together cannot spend the
  same credit twice;
- refunds and disputes come back out of the wallet;
- a paid subscription that was queued for Pay As You Go switches when it ends;
- the balance always equals the sum of its ledger, and the check that says so
  notices when it does not.

Uses its own in-memory SQLite engine, like ``test_pricing_plans``. Row locks
are a no-op there; ``TestConcurrentDebits`` runs the same debit path against
Postgres when the test database is reachable.
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from app.api.v1.endpoints import billing
from app.core.entitlement_guard import REASON_BALANCE, EntitlementError, require_entitlement
from app.core.workspace import WorkspaceContext
from app.database import Base
from app.models.call import Call, PhoneNumber
from app.models.subscription import (
    SOURCE_POLAR,
    SOURCE_STRIPE,
    SOURCE_TRIAL,
    SOURCE_WALLET,
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_TRIALING,
    Subscription,
    SubscriptionEvent,
    SubscriptionPlan,
    TrialGrant,
    UsageRecord,
)
from app.models.user import Organization, OrganizationMember, User
from app.models.wallet import (
    NOTICE_EMPTY,
    NOTICE_LOW,
    NOTICE_NONE,
    TXN_NUMBER_FEE,
    TXN_REFUND,
    TXN_TOPUP,
    TXN_USAGE,
    Wallet,
    WalletTransaction,
)
from app.services.billing import (
    call_credit,
    catalog,
    polar_service,
    prepaid,
    providers,
    wallet as wallet_service,
    wallet_notices,
    wallet_topups,
)
from app.services.billing.entitlements import (
    get_entitlement_service,
    resolve_entitlements,
    runtime_allows,
)
from app.services.billing.reconciler import reconcile_subscriptions, reset_expired_period_counters
from app.services.billing.seed_plans import seed_default_plans
from app.services.billing.usage_tracker import UsageTracker

pytestmark = [pytest.mark.unit, pytest.mark.billing]

RATE = Decimal(str(catalog.PAYG_BILLING["per_minute"]))  # 0.35 a minute


class Obj(dict):
    """A stand-in for a StripeObject: attribute and item access on one dict."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


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
        await seed_default_plans(session)
        yield session
    await engine.dispose()
    get_entitlement_service().invalidate_all()


@pytest.fixture(autouse=True)
def quiet_notices(monkeypatch):
    """Capture owner notices instead of rendering and sending email."""
    sent = []

    async def fake_notify(db, organization_id, **kwargs):
        sent.append({"organization_id": organization_id, **kwargs})

    monkeypatch.setattr(wallet_notices, "notify", fake_notify)
    get_entitlement_service().invalidate_all()
    return sent


async def make_org(db: AsyncSession, name: str = "Acme"):
    user = User(
        email=f"owner-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        full_name="Owner",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    organization = Organization(name=name, slug=f"acme-{uuid.uuid4().hex[:8]}", owner_id=user.id)
    db.add(organization)
    await db.flush()
    db.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    await db.commit()
    return organization, user


@pytest_asyncio.fixture
async def org_and_owner(db):
    return await make_org(db)


@pytest_asyncio.fixture
async def org(org_and_owner) -> Organization:
    return org_and_owner[0]


@pytest_asyncio.fixture
async def owner(org_and_owner) -> User:
    return org_and_owner[1]


async def plan_by_slug(db: AsyncSession, slug: str) -> SubscriptionPlan:
    return (
        await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.slug == slug))
    ).scalar_one()


async def payg_plan(db: AsyncSession) -> SubscriptionPlan:
    return await plan_by_slug(db, catalog.PREPAID_PLAN_SLUG)


async def put_on_payg(db: AsyncSession, org: Organization, *, balance_cents: int = 0) -> Subscription:
    subscription = await prepaid.activate(db, org.id)
    if balance_cents:
        await wallet_service.apply(
            db,
            org.id,
            amount_cents=balance_cents,
            type=TXN_TOPUP,
            idempotency_key=f"seed:{uuid.uuid4().hex}",
        )
    await db.commit()
    get_entitlement_service().invalidate(org.id)
    return subscription


async def start_trial(db: AsyncSession, org: Organization, user: User) -> Subscription:
    growth = await plan_by_slug(db, "growth")
    now = datetime.utcnow()
    subscription = Subscription(
        organization_id=org.id,
        plan_id=growth.id,
        status=STATUS_TRIALING,
        source=SOURCE_TRIAL,
        current_period_start=now,
        current_period_end=now + timedelta(days=14),
        trial_start=now,
        trial_end=now + timedelta(days=14),
    )
    db.add(subscription)
    db.add(
        TrialGrant(
            organization_id=org.id,
            user_id=user.id,
            email_domain="example.com",
            granted_at=now,
            expires_at=now + timedelta(days=14),
        )
    )
    await db.commit()
    get_entitlement_service().invalidate(org.id)
    return subscription


async def paid_subscription(
    db: AsyncSession, org: Organization, slug: str = "starter", *, source: str = SOURCE_STRIPE
) -> Subscription:
    plan = await plan_by_slug(db, slug)
    now = datetime.utcnow()
    subscription = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        status=STATUS_ACTIVE,
        source=source,
        stripe_subscription_id=f"sub_{uuid.uuid4().hex[:10]}" if source == SOURCE_STRIPE else None,
        stripe_customer_id="cus_test" if source == SOURCE_STRIPE else None,
        polar_subscription_id=f"polar_{uuid.uuid4().hex[:10]}" if source == SOURCE_POLAR else None,
        current_period_start=now - timedelta(days=10),
        current_period_end=now + timedelta(days=20),
    )
    db.add(subscription)
    await db.commit()
    get_entitlement_service().invalidate(org.id)
    return subscription


async def make_call(
    db: AsyncSession,
    org: Organization,
    user: User,
    *,
    seconds: int = None,
    status: str = "completed",
    direction: str = "inbound",
) -> Call:
    call = Call(
        user_id=user.id,
        organization_id=org.id,
        direction=direction,
        from_number="+14155550100",
        to_number="+14155550199",
        status=status,
        duration_seconds=seconds,
        billable_duration_seconds=seconds,
        ended_at=datetime.utcnow() if status == "completed" else None,
    )
    db.add(call)
    await db.commit()
    return call


async def ledger(db: AsyncSession, org: Organization, type: str = None):
    query = select(WalletTransaction).where(WalletTransaction.organization_id == org.id)
    if type:
        query = query.where(WalletTransaction.type == type)
    return (await db.execute(query.order_by(WalletTransaction.created_at))).scalars().all()


async def balance(db: AsyncSession, org: Organization) -> int:
    return await wallet_service.balance_cents(db, org.id)


def topup_intent(org, user, *, amount=2500, intent_id=None, status="succeeded", **metadata):
    return Obj(
        id=intent_id or f"pi_{uuid.uuid4().hex[:12]}",
        status=status,
        amount=amount,
        amount_received=amount if status == "succeeded" else 0,
        customer="cus_wallet",
        payment_method="pm_card",
        latest_charge=Obj(id="ch_1", receipt_url="https://pay.stripe.com/receipts/1"),
        client_secret="pi_secret",
        last_payment_error=None,
        metadata={
            "kind": wallet_topups.TOPUP_KIND,
            "organization_id": str(org.id),
            "user_id": str(user.id),
            "topup_id": uuid.uuid4().hex,
            "activate": "0",
            "save_card": "0",
            **{k: str(v) for k, v in metadata.items()},
        },
    )


def polar_topup_order(org, user, *, amount=2500, order_id=None, activate=False, **extra):
    return {
        "id": order_id or f"order_{uuid.uuid4().hex[:10]}",
        "status": "paid",
        "paid": True,
        "subscription_id": None,
        "billing_reason": "purchase",
        "product_id": "prod_credit",
        "checkout_id": "chk_1",
        "subtotal_amount": amount,
        "discount_amount": 0,
        "net_amount": amount,
        "tax_amount": 500,
        "total_amount": amount + 500,
        "currency": "usd",
        "customer": {"external_id": str(org.id), "email": user.email},
        "metadata": {
            "kind": wallet_topups.TOPUP_KIND,
            "organization_id": str(org.id),
            "user_id": str(user.id),
            "topup_id": uuid.uuid4().hex,
            "amount_cents": amount,
            "activate": "1" if activate else "0",
        },
        **extra,
    }


# ==================== The plan ====================


class TestPlan:
    async def test_the_plan_is_seeded_as_prepaid(self, db):
        plan = await payg_plan(db)
        assert plan.name == "Pay As You Go"
        assert plan.price_monthly == Decimal("0.00") and plan.price_yearly is None
        assert plan.is_active and plan.is_public and not plan.is_trialable
        billing_doc = plan.entitlements["billing"]
        assert billing_doc["mode"] == catalog.BILLING_PREPAID
        assert Decimal(str(billing_doc["per_minute"])) == RATE
        assert wallet_service.plan_is_prepaid(plan)
        assert (await wallet_service.prepaid_plan(db)).id == plan.id

    async def test_it_sits_below_every_subscription_and_outside_the_ladder(self, db):
        plan = await payg_plan(db)
        others = (
            await db.execute(
                select(SubscriptionPlan).where(
                    SubscriptionPlan.slug.in_(list(catalog.PLAN_ENTITLEMENTS))
                )
            )
        ).scalars().all()
        assert all(plan.tier < other.tier for other in others)
        assert all(plan.sort_order > other.sort_order for other in others)
        # A 402 suggests the next subscription up, never the prepaid plan.
        assert catalog.PREPAID_PLAN_SLUG not in catalog.PLAN_ENTITLEMENTS
        assert catalog.PREPAID_PLAN_SLUG not in catalog.plans_offering(catalog.INBOUND_CALLS)

    async def test_the_rate_is_above_starters_overage(self):
        starter = catalog.PLAN_ENTITLEMENTS["starter"]["overage"]["per_minute"]
        assert catalog.PAYG_BILLING["per_minute"] > starter

    async def test_subscription_plans_are_not_prepaid(self, db):
        for slug in catalog.PLAN_ENTITLEMENTS:
            plan = await plan_by_slug(db, slug)
            assert not wallet_service.plan_is_prepaid(plan), slug
            assert "billing" not in (plan.entitlements or {}), slug

    async def test_a_stored_document_missing_a_new_key_falls_back_to_the_default(self):
        document = {"billing": {"mode": catalog.BILLING_PREPAID, "per_minute": 0.5}}
        config = catalog.billing_config(document)
        assert config["per_minute"] == 0.5
        assert config["topup_min"] == catalog.PAYG_BILLING["topup_min"]

    async def test_a_workspace_on_the_plan_resolves_as_prepaid(self, db, org):
        await put_on_payg(db, org, balance_cents=1000)
        ent = await resolve_entitlements(db, org.id, fresh=True)
        assert ent.is_live and ent.is_prepaid and not ent.is_trial
        assert ent.source == SOURCE_WALLET
        assert ent.is_unlimited(catalog.LIMIT_MINUTES)
        assert not ent.overage_allowed
        assert ent.has(catalog.INBOUND_CALLS) and not ent.has(catalog.OUTBOUND_CALLS)

    async def test_a_subscriber_is_not_prepaid(self, db, org):
        await paid_subscription(db, org)
        ent = await resolve_entitlements(db, org.id, fresh=True)
        assert ent.is_live and not ent.is_prepaid and ent.billing == {}


# ==================== Money ====================


class TestMoney:
    def test_amounts_become_whole_cents(self):
        assert wallet_service.to_cents(10) == 1000
        assert wallet_service.to_cents("0.35") == 35
        assert wallet_service.to_cents(19.999) == 2000
        assert wallet_service.to_cents(0.1 + 0.2) == 30

    def test_a_call_is_priced_once_and_rounded_to_a_cent(self):
        assert wallet_service.call_cost_cents(3, {"per_minute": 0.35}) == 105
        # 7.5 cents a minute: three minutes is 22.5, which rounds to 23.
        assert wallet_service.call_cost_cents(3, {"per_minute": 0.075}) == 23
        assert wallet_service.call_cost_cents(0, {"per_minute": 0.35}) == 0

    def test_minutes_a_balance_pays_for(self):
        assert wallet_service.minutes_affordable(1000, {"per_minute": 0.35}) == 28
        assert wallet_service.minutes_affordable(34, {"per_minute": 0.35}) == 0
        assert wallet_service.minutes_affordable(-50, {"per_minute": 0.35}) == 0
        assert wallet_service.minutes_affordable(0, {"per_minute": 0}) is None

    def test_money_is_formatted_for_people(self):
        assert wallet_service.format_money(1250) == "$12.50"
        assert wallet_service.format_money(-300) == "-$3.00"

    def test_a_topup_must_sit_inside_the_plans_bounds(self):
        bounds = catalog.PAYG_BILLING
        assert wallet_topups.validate_amount(25, bounds) == 2500
        assert wallet_topups.validate_amount("10", bounds) == 1000
        with pytest.raises(wallet_service.WalletError):
            wallet_topups.validate_amount(5, bounds)
        with pytest.raises(wallet_service.WalletError):
            wallet_topups.validate_amount(5000, bounds)
        with pytest.raises(wallet_service.WalletError):
            wallet_topups.validate_amount("abc", bounds)


# ==================== The ledger ====================


class TestLedger:
    async def test_a_movement_writes_one_row_and_moves_the_balance(self, db, org):
        movement = await wallet_service.apply(
            db, org.id, amount_cents=2500, type=TXN_TOPUP, idempotency_key="k1", description="Credit"
        )
        await db.commit()
        assert movement.balance_cents == 2500
        assert await balance(db, org) == 2500
        rows = await ledger(db, org)
        assert [(r.type, r.amount_cents, r.balance_after_cents) for r in rows] == [
            (TXN_TOPUP, 2500, 2500)
        ]

    async def test_the_same_key_is_applied_once(self, db, org):
        first = await wallet_service.apply(
            db, org.id, amount_cents=2500, type=TXN_TOPUP, idempotency_key="pay-1"
        )
        await db.commit()
        again = await wallet_service.apply(
            db, org.id, amount_cents=2500, type=TXN_TOPUP, idempotency_key="pay-1"
        )
        await db.commit()
        assert first is not None and again is None
        assert await balance(db, org) == 2500
        assert len(await ledger(db, org)) == 1

    async def test_the_key_is_unique_in_the_database(self, db, org):
        """The backstop under the check: a second row with the same key cannot exist."""
        from sqlalchemy.exc import IntegrityError

        movement = await wallet_service.apply(
            db, org.id, amount_cents=100, type=TXN_TOPUP, idempotency_key="dup"
        )
        await db.commit()
        db.add(
            WalletTransaction(
                wallet_id=movement.transaction.wallet_id,
                organization_id=org.id,
                type=TXN_TOPUP,
                amount_cents=100,
                balance_after_cents=200,
                idempotency_key="dup",
            )
        )
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

    async def test_a_zero_movement_is_nothing(self, db, org):
        assert await wallet_service.apply(
            db, org.id, amount_cents=0, type=TXN_TOPUP, idempotency_key="zero"
        ) is None

    async def test_the_balance_is_the_sum_of_the_ledger(self, db, org):
        for key, amount in (("a", 5000), ("b", -105), ("c", -70), ("d", 1000), ("e", -2000)):
            await wallet_service.apply(
                db, org.id, amount_cents=amount, type=TXN_TOPUP if amount > 0 else TXN_USAGE,
                idempotency_key=key,
            )
        await db.commit()
        total = (
            await db.execute(
                select(func.sum(WalletTransaction.amount_cents)).where(
                    WalletTransaction.organization_id == org.id
                )
            )
        ).scalar()
        assert total == await balance(db, org) == 3825
        assert await wallet_service.ledger_mismatches(db) == []

    async def test_a_balance_changed_outside_the_ledger_is_noticed(self, db, org):
        await wallet_service.apply(db, org.id, amount_cents=1000, type=TXN_TOPUP, idempotency_key="a")
        await db.commit()
        wallet = await wallet_service.get_wallet(db, org.id)
        wallet.balance_cents = 9999  # what a bug or a hand edit would do
        await db.commit()

        mismatches = await wallet_service.ledger_mismatches(db)
        assert len(mismatches) == 1
        assert mismatches[0]["balance_cents"] == 9999 and mismatches[0]["ledger_cents"] == 1000

        report = await reconcile_subscriptions(db)
        assert report.wallet_mismatches == 1
        # Reported, never "fixed": either side could be the wrong one.
        assert await balance(db, org) == 9999

    async def test_wallets_do_not_share_a_balance(self, db, org):
        other, _ = await make_org(db, "Other")
        await wallet_service.apply(db, org.id, amount_cents=1000, type=TXN_TOPUP, idempotency_key="a")
        await wallet_service.apply(db, other.id, amount_cents=300, type=TXN_TOPUP, idempotency_key="b")
        await db.commit()
        assert await balance(db, org) == 1000
        assert await balance(db, other) == 300


# ==================== Notices ====================


class TestNotices:
    async def test_running_low_is_announced_once(self, db, org, quiet_notices):
        await put_on_payg(db, org, balance_cents=1000)
        first = await wallet_service.apply(
            db, org.id, amount_cents=-600, type=TXN_USAGE, idempotency_key="u1"
        )
        await db.commit()
        assert first.notice == NOTICE_LOW  # 4.00 left, under the 5.00 threshold
        second = await wallet_service.apply(
            db, org.id, amount_cents=-100, type=TXN_USAGE, idempotency_key="u2"
        )
        await db.commit()
        assert second.notice is None

        await wallet_notices.after_movement(db, first)
        await wallet_notices.after_movement(db, second)
        assert len(quiet_notices) == 1
        assert "running low" in quiet_notices[0]["subject"]

    async def test_running_out_is_announced_once_and_resets_after_a_topup(self, db, org):
        await put_on_payg(db, org, balance_cents=1000)
        low = await wallet_service.apply(db, org.id, amount_cents=-700, type=TXN_USAGE, idempotency_key="u1")
        empty = await wallet_service.apply(db, org.id, amount_cents=-300, type=TXN_USAGE, idempotency_key="u2")
        below = await wallet_service.apply(db, org.id, amount_cents=-35, type=TXN_USAGE, idempotency_key="u3")
        await db.commit()
        assert (low.notice, empty.notice, below.notice) == (NOTICE_LOW, NOTICE_EMPTY, None)

        topup = await wallet_service.apply(db, org.id, amount_cents=5000, type=TXN_TOPUP, idempotency_key="t")
        await db.commit()
        assert topup.notice is None
        assert (await wallet_service.get_wallet(db, org.id)).notice_level == NOTICE_NONE

        again = await wallet_service.apply(db, org.id, amount_cents=-4800, type=TXN_USAGE, idempotency_key="u4")
        await db.commit()
        assert again.notice == NOTICE_LOW

    async def test_no_low_balance_email_while_auto_recharge_will_top_up(self, db, org, quiet_notices):
        await put_on_payg(db, org, balance_cents=1000)
        wallet = await wallet_service.get_wallet(db, org.id)
        wallet.auto_recharge_enabled = True
        wallet.auto_recharge_threshold_cents = 500
        wallet.auto_recharge_amount_cents = 2500
        wallet.stripe_payment_method_id = "pm_saved"
        wallet.stripe_customer_id = "cus_saved"
        await db.commit()

        movement = await wallet_service.apply(
            db, org.id, amount_cents=-600, type=TXN_USAGE, idempotency_key="u1"
        )
        await db.commit()
        assert movement.notice == NOTICE_LOW and movement.wants_recharge
        await wallet_notices.after_movement(db, movement)
        assert quiet_notices == []


# ==================== Charging calls ====================


class TestCallCharges:
    async def test_a_call_is_charged_per_started_minute(self, db, org, owner):
        await put_on_payg(db, org, balance_cents=1000)
        call = await make_call(db, org, owner, seconds=125)  # 3 minutes

        await UsageTracker.record_call_usage(db, call.id, org.id)

        assert await balance(db, org) == 1000 - 105
        usage = await ledger(db, org, TXN_USAGE)
        assert len(usage) == 1
        assert usage[0].amount_cents == -105
        assert usage[0].reference_type == "call" and usage[0].reference_id == str(call.id)
        assert usage[0].details["minutes"] == 3

        record = (
            await db.execute(
                select(UsageRecord).where(
                    UsageRecord.resource_id == call.id, UsageRecord.usage_type == "minutes"
                )
            )
        ).scalar_one()
        assert record.quantity == 3
        assert Decimal(str(record.unit_price)) == RATE
        assert Decimal(str(record.total_amount)) == Decimal("1.05")

        subscription = await prepaid.current_subscription(db, org.id)
        assert subscription.current_period_minutes == 3

    async def test_a_repeated_callback_does_not_charge_twice(self, db, org, owner):
        await put_on_payg(db, org, balance_cents=1000)
        call = await make_call(db, org, owner, seconds=60)

        await UsageTracker.record_call_usage(db, call.id, org.id)
        await UsageTracker.record_call_usage(db, call.id, org.id)
        await UsageTracker.record_call_usage(db, call.id, org.id)

        assert await balance(db, org) == 1000 - 35
        assert len(await ledger(db, org, TXN_USAGE)) == 1

    async def test_a_charge_already_in_the_ledger_is_not_repeated(self, db, org, owner):
        """Two callbacks can both get past the usage-record check before either
        commits. The ledger key is what stops the second one."""
        await put_on_payg(db, org, balance_cents=1000)
        call = await make_call(db, org, owner, seconds=60)
        await wallet_service.apply(
            db, org.id, amount_cents=-35, type=TXN_USAGE, idempotency_key=f"usage:call:{call.id}"
        )
        await db.commit()

        assert await UsageTracker.record_call_usage(db, call.id, org.id) is None
        assert await balance(db, org) == 1000 - 35
        assert len(await ledger(db, org, TXN_USAGE)) == 1

    async def test_the_charge_and_the_usage_rows_land_together(self, db, org, owner):
        await put_on_payg(db, org, balance_cents=1000)
        call = await make_call(db, org, owner, seconds=61)
        await UsageTracker.record_call_usage(db, call.id, org.id)

        minutes = (
            await db.execute(select(func.sum(UsageRecord.quantity)).where(UsageRecord.usage_type == "minutes"))
        ).scalar()
        charged = -sum(row.amount_cents for row in await ledger(db, org, TXN_USAGE))
        assert charged == wallet_service.call_cost_cents(minutes, catalog.PAYG_BILLING) == 70

    async def test_a_subscribers_call_never_touches_a_wallet(self, db, org, owner):
        await paid_subscription(db, org)
        await wallet_service.apply(db, org.id, amount_cents=1000, type=TXN_TOPUP, idempotency_key="t")
        await db.commit()
        call = await make_call(db, org, owner, seconds=600)

        await UsageTracker.record_call_usage(db, call.id, org.id)

        assert await balance(db, org) == 1000
        assert await ledger(db, org, TXN_USAGE) == []

    async def test_a_trial_call_never_touches_a_wallet(self, db, org, owner):
        await start_trial(db, org, owner)
        call = await make_call(db, org, owner, seconds=120)
        await UsageTracker.record_call_usage(db, call.id, org.id)
        assert await ledger(db, org) == []

    async def test_the_admins_rate_is_what_is_charged(self, db, org, owner):
        plan = await payg_plan(db)
        plan.entitlements = {
            **plan.entitlements,
            "billing": {**plan.entitlements["billing"], "per_minute": 0.5},
        }
        await db.commit()
        await put_on_payg(db, org, balance_cents=1000)
        call = await make_call(db, org, owner, seconds=120)

        await UsageTracker.record_call_usage(db, call.id, org.id)
        assert await balance(db, org) == 1000 - 100

    async def test_the_usage_period_rolls_without_a_provider(self, db, org):
        subscription = await put_on_payg(db, org, balance_cents=1000)
        subscription.current_period_minutes = 40
        subscription.current_period_end = datetime.utcnow() - timedelta(minutes=1)
        subscription.current_period_start = subscription.current_period_end - prepaid.USAGE_PERIOD
        await db.commit()

        assert await reset_expired_period_counters(db) == 1
        await db.refresh(subscription)
        assert subscription.current_period_minutes == 0
        assert subscription.current_period_end > datetime.utcnow()
        assert subscription.status == STATUS_ACTIVE
        # The money is not part of the period: it carries over untouched.
        assert await balance(db, org) == 1000


# ==================== Blocking and reserving ====================


class TestBalanceGate:
    async def test_an_empty_wallet_blocks_calls(self, db, org):
        await put_on_payg(db, org)
        assert await runtime_allows(db, org.id, catalog.INBOUND_CALLS) == (
            False,
            "insufficient_balance",
        )

    async def test_less_than_a_minute_of_credit_blocks_calls(self, db, org):
        await put_on_payg(db, org, balance_cents=34)
        allowed, reason = await runtime_allows(db, org.id, catalog.INBOUND_CALLS)
        assert (allowed, reason) == (False, "insufficient_balance")

    async def test_a_funded_wallet_allows_calls_and_a_topup_unblocks_at_once(self, db, org):
        await put_on_payg(db, org)
        assert (await runtime_allows(db, org.id, catalog.INBOUND_CALLS))[0] is False
        await wallet_service.apply(db, org.id, amount_cents=1000, type=TXN_TOPUP, idempotency_key="t")
        await db.commit()
        # No cache invalidation in between: the balance is always read fresh.
        assert await runtime_allows(db, org.id, catalog.INBOUND_CALLS) == (True, None)

    async def test_a_negative_balance_blocks_calls(self, db, org):
        await put_on_payg(db, org, balance_cents=1000)
        await wallet_service.apply(db, org.id, amount_cents=-1500, type=TXN_REFUND, idempotency_key="r")
        await db.commit()
        assert (await runtime_allows(db, org.id, catalog.INBOUND_CALLS))[0] is False

    async def test_the_dashboard_gets_a_402_that_says_add_credit(self, db, org, owner):
        plan = await payg_plan(db)
        plan.entitlements = {
            **plan.entitlements,
            "features": {**plan.entitlements["features"], catalog.OUTBOUND_CALLS: True},
        }
        await db.commit()
        await put_on_payg(db, org)

        checker = require_entitlement(feature=catalog.OUTBOUND_CALLS, limit=catalog.LIMIT_MINUTES)
        membership = (await db.execute(select(OrganizationMember))).scalar_one()
        workspace = WorkspaceContext(user=owner, organization=org, membership=membership)
        with pytest.raises(EntitlementError) as refused:
            await checker(workspace=workspace, db=db)
        assert refused.value.payload["reason"] == REASON_BALANCE
        assert "Add credit" in refused.value.payload["detail"]

        await wallet_service.apply(db, org.id, amount_cents=1000, type=TXN_TOPUP, idempotency_key="t")
        await db.commit()
        assert (await checker(workspace=workspace, db=db)).is_prepaid

    async def test_a_subscriber_is_not_asked_for_a_balance(self, db, org):
        await paid_subscription(db, org)
        assert await runtime_allows(db, org.id, catalog.INBOUND_CALLS) == (True, None)


class Agent:
    """As much of an agent as the reservation looks at."""

    def __init__(self, max_call_duration=1800):
        self.max_call_duration = max_call_duration


class TestReservations:
    async def test_a_live_call_reserves_part_of_the_balance(self, db, org, owner):
        await put_on_payg(db, org, balance_cents=1000)  # 28 minutes
        call = await make_call(db, org, owner, status="in_progress")

        seconds = await wallet_service.reserve_for_call(db, call.id, max_seconds=1800)

        # Two lines on the plan: one call takes at most half of what is free.
        assert seconds == 14 * 60
        hold = wallet_service.call_hold(call)
        assert hold["cents"] == 490 and hold["max_seconds"] == 840
        assert await wallet_service.held_cents(db, org.id) == 490
        assert await wallet_service.available_cents(db, org.id) == 510
        # Reserving moves no money: the charge is made when the call ends.
        assert await balance(db, org) == 1000 and await ledger(db, org, TXN_USAGE) == []

    async def test_reserving_twice_for_the_same_call_changes_nothing(self, db, org, owner):
        await put_on_payg(db, org, balance_cents=1000)
        call = await make_call(db, org, owner, status="in_progress")
        first = await wallet_service.reserve_for_call(db, call.id, max_seconds=1800)
        second = await wallet_service.reserve_for_call(db, call.id, max_seconds=1800)
        assert first == second == 840
        assert await wallet_service.held_cents(db, org.id) == 490

    async def test_two_calls_cannot_reserve_the_same_credit(self, db, org, owner):
        await put_on_payg(db, org, balance_cents=100)  # 2 minutes in all
        first = await make_call(db, org, owner, status="in_progress")
        second = await make_call(db, org, owner, status="in_progress")
        third = await make_call(db, org, owner, status="ringing")

        assert await wallet_service.reserve_for_call(db, first.id, max_seconds=1800) == 60
        assert await wallet_service.reserve_for_call(db, second.id, max_seconds=1800) == 60
        with pytest.raises(wallet_service.InsufficientBalance):
            await wallet_service.reserve_for_call(db, third.id, max_seconds=1800)

        assert await wallet_service.held_cents(db, org.id) == 70
        assert await wallet_service.held_cents(db, org.id) <= await balance(db, org)
        assert not await wallet_service.can_start_call(db, org.id, catalog.PAYG_BILLING)

    async def test_a_call_that_outlasts_its_share_gets_more_while_there_is_more(self, db, org, owner):
        await put_on_payg(db, org, balance_cents=1000)
        call = await make_call(db, org, owner, status="in_progress")
        assert await wallet_service.reserve_for_call(db, call.id, max_seconds=1800) == 840

        totals = []
        for _ in range(8):
            totals.append(
                await wallet_service.reserve_for_call(db, call.id, max_seconds=1800, extend=True)
            )
        # 14 minutes, then 7 more, 3, 2, 1, 1 — and then nothing is left.
        assert totals[:5] == [1260, 1440, 1560, 1620, 1680]
        assert totals[-1] == totals[-2] == 1680  # 28 minutes: the whole balance
        assert wallet_service.call_hold(call)["cents"] <= 1000

    async def test_a_finished_call_stops_holding_credit(self, db, org, owner):
        await put_on_payg(db, org, balance_cents=1000)
        call = await make_call(db, org, owner, status="in_progress")
        await wallet_service.reserve_for_call(db, call.id, max_seconds=1800)
        call.status = "completed"
        call.ended_at = datetime.utcnow()
        await db.commit()
        assert await wallet_service.held_cents(db, org.id) == 0

    async def test_a_single_line_plan_gives_the_call_everything(self, db, org, owner):
        plan = await payg_plan(db)
        plan.entitlements = {
            **plan.entitlements,
            "limits": {**plan.entitlements["limits"], catalog.LIMIT_CONCURRENT_CALLS: 1},
        }
        await db.commit()
        await put_on_payg(db, org, balance_cents=1000)
        call = await make_call(db, org, owner, status="in_progress")
        assert await wallet_service.reserve_for_call(db, call.id, max_seconds=3600) == 28 * 60

    async def test_the_reservation_never_exceeds_the_agents_time_limit(self, db, org, owner):
        await put_on_payg(db, org, balance_cents=100_000)
        call = await make_call(db, org, owner, status="in_progress")
        assert await wallet_service.reserve_for_call(db, call.id, max_seconds=600) == 600

    async def test_a_subscribers_call_reserves_nothing(self, db, org, owner):
        await paid_subscription(db, org)
        call = await make_call(db, org, owner, status="in_progress")
        assert await wallet_service.reserve_for_call(db, call.id, max_seconds=1800) is None
        assert wallet_service.call_hold(call) == {}

    async def test_a_call_that_cannot_be_paid_for_is_closed_out(self, db, org, owner):
        await put_on_payg(db, org, balance_cents=10)
        call = await make_call(db, org, owner, status="ringing")

        assert await call_credit.reserve(db, call, Agent()) is False
        assert call.status == "missed" and call.ended_at is not None
        assert call.call_metadata["declined_reason"] == "insufficient_balance"

        outbound = await make_call(db, org, owner, status="initiated", direction="outbound")
        with pytest.raises(EntitlementError) as refused:
            await call_credit.reserve_or_refuse(db, outbound, Agent())
        assert refused.value.payload["reason"] == REASON_BALANCE
        assert outbound.status == "failed"

    async def test_reserved_time_plus_the_charge_never_overdraws(self, db, org, owner):
        """A call that runs exactly as long as it reserved costs what it reserved."""
        await put_on_payg(db, org, balance_cents=100)
        call = await make_call(db, org, owner, status="in_progress")
        seconds = await wallet_service.reserve_for_call(db, call.id, max_seconds=1800)
        call.status = "completed"
        call.ended_at = datetime.utcnow()
        call.duration_seconds = call.billable_duration_seconds = seconds
        await db.commit()

        await UsageTracker.record_call_usage(db, call.id, org.id)
        assert await balance(db, org) == 100 - 35 >= 0


# ==================== Stripe top-ups ====================


class TestStripeTopups:
    async def test_a_paid_topup_is_credited(self, db, org, owner, quiet_notices):
        intent = topup_intent(org, owner, amount=2500)
        result = await wallet_topups.credit_stripe_intent(db, intent, actor=owner)

        assert result.credited and result.balance_cents == 2500
        rows = await ledger(db, org, TXN_TOPUP)
        assert len(rows) == 1
        assert rows[0].reference_id == intent.id
        assert rows[0].details["receipt_url"].startswith("https://pay.stripe.com/")
        assert any("credit added" in n["subject"].lower() for n in quiet_notices)

    async def test_the_confirm_call_and_the_webhook_credit_once(self, db, org, owner, quiet_notices):
        intent = topup_intent(org, owner, amount=2500)
        await wallet_topups.credit_stripe_intent(db, intent, actor=owner)
        event = {"id": "evt_1", "type": "payment_intent.succeeded", "data": {"object": intent}}
        await wallet_topups.apply_stripe_event(db, event)
        await wallet_topups.apply_stripe_event(db, event)  # Stripe retries

        assert await balance(db, org) == 2500
        assert len(await ledger(db, org, TXN_TOPUP)) == 1
        assert len(quiet_notices) == 1

    async def test_the_webhook_alone_credits_a_browser_that_never_came_back(self, db, org, owner):
        intent = topup_intent(org, owner, amount=1000)
        await wallet_topups.apply_stripe_event(
            db, {"id": "evt_2", "type": "payment_intent.succeeded", "data": {"object": intent}}
        )
        assert await balance(db, org) == 1000

    async def test_an_unpaid_payment_credits_nothing(self, db, org, owner):
        for status in ("requires_action", "requires_payment_method", "processing", "canceled"):
            intent = topup_intent(org, owner, status=status)
            assert await wallet_topups.credit_stripe_intent(db, intent) is None
        assert await ledger(db, org) == []

    async def test_a_payment_that_is_not_a_topup_is_left_alone(self, db, org, owner):
        intent = topup_intent(org, owner)
        intent["metadata"] = {"organization_id": str(org.id), "plan_id": "x"}  # a subscription's
        await wallet_topups.apply_stripe_event(
            db, {"id": "evt_3", "type": "payment_intent.succeeded", "data": {"object": intent}}
        )
        assert await ledger(db, org) == []

    async def test_a_topup_for_an_unknown_workspace_credits_nothing(self, db, org, owner):
        intent = topup_intent(org, owner)
        intent["metadata"]["organization_id"] = str(uuid.uuid4())
        assert await wallet_topups.credit_stripe_intent(db, intent) is None

    async def test_a_first_topup_moves_a_trial_onto_the_plan(self, db, org, owner, quiet_notices):
        trial = await start_trial(db, org, owner)
        trial.current_period_minutes = 12

        intent = topup_intent(org, owner, amount=2500, activate=1)
        result = await wallet_topups.credit_stripe_intent(db, intent, actor=owner)

        assert result.activated_plan == "Pay As You Go"
        await db.refresh(trial)
        assert trial.source == SOURCE_WALLET and trial.status == STATUS_ACTIVE
        assert trial.plan_id == (await payg_plan(db)).id
        assert trial.trial_converted_at is not None and trial.trial_end <= datetime.utcnow()
        assert trial.current_period_minutes == 0  # the trial's usage is not carried over
        assert trial.stripe_subscription_id is None

        grant = (await db.execute(select(TrialGrant))).scalar_one()
        assert grant.converted is True
        events_ = (await db.execute(select(SubscriptionEvent.event_type))).scalars().all()
        assert "trial_converted" in events_

        ent = await resolve_entitlements(db, org.id, fresh=True)
        assert ent.is_prepaid and ent.is_live and not ent.is_trial
        assert await runtime_allows(db, org.id, catalog.INBOUND_CALLS) == (True, None)
        assert any("You're now on Pay As You Go" in n["subject"] for n in quiet_notices)

    async def test_a_topup_without_activate_leaves_the_plan_alone(self, db, org, owner):
        trial = await start_trial(db, org, owner)
        await wallet_topups.credit_stripe_intent(db, topup_intent(org, owner), actor=owner)
        await db.refresh(trial)
        assert trial.source == SOURCE_TRIAL and trial.status == STATUS_TRIALING
        assert await balance(db, org) == 2500

    async def test_a_subscriber_can_top_up_but_keeps_the_plan_they_paid_for(self, db, org, owner):
        subscription = await paid_subscription(db, org, "growth")
        result = await wallet_topups.credit_stripe_intent(
            db, topup_intent(org, owner, activate=1), actor=owner
        )
        await db.refresh(subscription)
        assert result.credited and result.activated_plan is None
        assert subscription.source == SOURCE_STRIPE
        assert subscription.plan_id == (await plan_by_slug(db, "growth")).id
        assert await balance(db, org) == 2500

    async def test_a_workspace_with_no_subscription_gets_one(self, db, org, owner):
        await wallet_topups.credit_stripe_intent(
            db, topup_intent(org, owner, amount=1000, activate=1), actor=owner
        )
        subscription = await prepaid.current_subscription(db, org.id)
        assert subscription.source == SOURCE_WALLET and subscription.status == STATUS_ACTIVE

    async def test_saving_the_card_switches_on_the_auto_recharge_that_was_asked_for(
        self, db, org, owner, monkeypatch
    ):
        async def no_stripe():
            return None

        async def card(_):
            return "visa", "4242"

        monkeypatch.setattr(wallet_topups, "_configure_stripe", no_stripe)
        monkeypatch.setattr(wallet_topups, "_card_details", card)
        wallet = await wallet_service.get_wallet(db, org.id, create=True)
        wallet.auto_recharge_threshold_cents = 500
        wallet.auto_recharge_amount_cents = 2500
        await db.commit()

        await wallet_topups.credit_stripe_intent(
            db, topup_intent(org, owner, save_card=1, enable_auto=1), actor=owner
        )
        await db.refresh(wallet)
        assert wallet.stripe_payment_method_id == "pm_card"
        assert (wallet.card_brand, wallet.card_last4) == ("visa", "4242")
        assert wallet.auto_recharge_enabled is True

    async def test_a_card_is_not_saved_unless_asked(self, db, org, owner):
        await wallet_topups.credit_stripe_intent(db, topup_intent(org, owner), actor=owner)
        wallet = await wallet_service.get_wallet(db, org.id)
        assert wallet.stripe_payment_method_id is None and not wallet.auto_recharge_enabled


class TestStripeRefunds:
    async def _topped_up(self, db, org, owner, amount=2500):
        intent = topup_intent(org, owner, amount=amount)
        await wallet_topups.credit_stripe_intent(db, intent, actor=owner)
        return intent

    async def test_a_refund_comes_back_out_of_the_wallet(self, db, org, owner, quiet_notices):
        intent = await self._topped_up(db, org, owner)
        event = {
            "id": "evt_r1",
            "type": "charge.refunded",
            "data": {
                "object": {"id": "ch_1", "payment_intent": intent.id, "amount": 2500, "amount_refunded": 2500}
            },
        }
        await wallet_topups.apply_stripe_event(db, event)
        await wallet_topups.apply_stripe_event(db, event)
        assert await balance(db, org) == 0
        assert len(await ledger(db, org, TXN_REFUND)) == 1
        assert any("refunded" in n["subject"] for n in quiet_notices)

    async def test_partial_refunds_take_back_only_what_is_new(self, db, org, owner):
        intent = await self._topped_up(db, org, owner)

        def refunded(total, event_id):
            return {
                "id": event_id,
                "type": "charge.refunded",
                "data": {
                    "object": {"id": "ch_1", "payment_intent": intent.id, "amount": 2500, "amount_refunded": total}
                },
            }

        await wallet_topups.apply_stripe_event(db, refunded(1000, "e1"))
        assert await balance(db, org) == 1500
        await wallet_topups.apply_stripe_event(db, refunded(2500, "e2"))  # cumulative
        assert await balance(db, org) == 0
        assert [r.amount_cents for r in await ledger(db, org, TXN_REFUND)] == [-1000, -1500]

    async def test_refunding_spent_credit_leaves_a_negative_balance_that_blocks_calls(
        self, db, org, owner
    ):
        await put_on_payg(db, org)
        intent = await self._topped_up(db, org, owner, amount=1000)
        await wallet_service.apply(db, org.id, amount_cents=-800, type=TXN_USAGE, idempotency_key="u")
        await db.commit()
        await wallet_topups.apply_stripe_event(
            db,
            {
                "id": "e",
                "type": "charge.refunded",
                "data": {"object": {"id": "ch_1", "payment_intent": intent.id, "amount": 1000, "amount_refunded": 1000}},
            },
        )
        assert await balance(db, org) == -800
        assert (await runtime_allows(db, org.id, catalog.INBOUND_CALLS))[0] is False

    async def test_a_refund_of_a_subscription_charge_is_not_the_wallets(self, db, org, owner):
        await self._topped_up(db, org, owner)
        await wallet_topups.apply_stripe_event(
            db,
            {
                "id": "e",
                "type": "charge.refunded",
                "data": {"object": {"id": "ch_x", "payment_intent": "pi_other", "amount": 4900, "amount_refunded": 4900}},
            },
        )
        assert await balance(db, org) == 2500

    async def test_a_dispute_takes_the_credit_back_and_winning_it_restores_it(self, db, org, owner):
        intent = await self._topped_up(db, org, owner)
        wallet = await wallet_service.get_wallet(db, org.id)
        wallet.auto_recharge_enabled = True
        await db.commit()

        dispute = {"id": "dp_1", "payment_intent": intent.id, "amount": 2500, "status": "needs_response"}
        await wallet_topups.apply_stripe_event(
            db, {"id": "e1", "type": "charge.dispute.created", "data": {"object": dispute}}
        )
        await wallet_topups.apply_stripe_event(
            db, {"id": "e2", "type": "charge.dispute.funds_withdrawn", "data": {"object": dispute}}
        )
        assert await balance(db, org) == 0
        await db.refresh(wallet)
        assert wallet.auto_recharge_enabled is False  # never auto-charge a disputed card

        won = {"id": "e3", "type": "charge.dispute.closed", "data": {"object": {**dispute, "status": "won"}}}
        await wallet_topups.apply_stripe_event(db, won)
        await wallet_topups.apply_stripe_event(db, won)
        assert await balance(db, org) == 2500
        assert await wallet_service.ledger_mismatches(db) == []


# ==================== Polar top-ups ====================


class TestPolarTopups:
    async def test_a_paid_order_is_credited_net_of_tax(self, db, org, owner):
        order = polar_topup_order(org, owner, amount=2500)
        outcome = await polar_service.handle_webhook_event(
            db, "wh_1", {"type": "order.paid", "data": order}
        )
        assert await balance(db, org) == 2500  # not 3000: tax is not credit
        assert len(outcome.wallet_credits) == 1 and outcome.wallet_credits[0].credited
        assert org.id in outcome.invalidate
        row = (await ledger(db, org, TXN_TOPUP))[0]
        assert row.reference_type == wallet_topups.REF_POLAR_ORDER
        assert row.client_ref == order["metadata"]["topup_id"]

    async def test_a_repeated_delivery_credits_once(self, db, org, owner):
        order = polar_topup_order(org, owner)
        payload = {"type": "order.paid", "data": order}
        await polar_service.handle_webhook_event(db, "wh_1", payload)
        await polar_service.handle_webhook_event(db, "wh_1", payload)  # same delivery
        await polar_service.handle_webhook_event(db, "wh_2", payload)  # same order, new delivery
        assert await balance(db, org) == 2500
        assert len(await ledger(db, org, TXN_TOPUP)) == 1

    async def test_a_first_topup_moves_a_trial_onto_the_plan(self, db, org, owner):
        trial = await start_trial(db, org, owner)
        outcome = await polar_service.handle_webhook_event(
            db, "wh_1", {"type": "order.paid", "data": polar_topup_order(org, owner, activate=True)}
        )
        await db.refresh(trial)
        assert trial.source == SOURCE_WALLET and trial.status == STATUS_ACTIVE
        assert outcome.wallet_credits[0].activated_plan == "Pay As You Go"

    async def test_a_one_off_order_that_is_not_a_topup_is_ignored(self, db, org, owner):
        order = polar_topup_order(org, owner)
        order["metadata"] = {}
        outcome = await polar_service.handle_webhook_event(
            db, "wh_1", {"type": "order.paid", "data": order}
        )
        assert outcome.wallet_credits == [] and await ledger(db, org) == []

    async def test_a_refunded_order_comes_back_out(self, db, org, owner):
        order = polar_topup_order(org, owner, amount=2500)
        await polar_service.handle_webhook_event(db, "wh_1", {"type": "order.paid", "data": order})

        partial = {**order, "status": "partially_refunded", "refunded_amount": 1000}
        await polar_service.handle_webhook_event(db, "wh_2", {"type": "order.refunded", "data": partial})
        assert await balance(db, org) == 1500

        full = {**order, "status": "refunded", "refunded_amount": 2500}
        outcome = await polar_service.handle_webhook_event(
            db, "wh_3", {"type": "order.refunded", "data": full}
        )
        await polar_service.handle_webhook_event(db, "wh_4", {"type": "order.refunded", "data": full})
        assert await balance(db, org) == 0
        assert len(outcome.wallet_refunds) == 1
        assert await wallet_service.ledger_mismatches(db) == []

    async def test_the_checkout_pins_the_amount_and_says_whose_it_is(self, db, org, owner, monkeypatch):
        plan = await payg_plan(db)
        plan.polar_product_id = "prod_credit"
        await db.commit()
        sent = {}

        class Client:
            async def create_checkout(self, body):
                sent.update(body)
                return {"url": "https://polar.example/checkout", "id": "chk_9"}

        monkeypatch.setattr(polar_service, "get_polar_client", lambda: Client())
        result = await wallet_topups.start_polar_topup(
            db,
            organization_id=org.id,
            user=owner,
            amount_cents=5000,
            activate=True,
            return_path="/dashboard/settings/billing",
            cancel_path="/dashboard/settings/billing",
        )
        assert result == {"url": "https://polar.example/checkout", "checkout_id": "chk_9"}
        assert sent["products"] == ["prod_credit"]
        assert sent["prices"]["prod_credit"] == [
            {"amount_type": "fixed", "price_amount": 5000, "price_currency": "usd"}
        ]
        assert sent["external_customer_id"] == str(org.id)
        assert sent["metadata"]["kind"] == wallet_topups.TOPUP_KIND
        assert sent["metadata"]["activate"] == "1"
        assert "{CHECKOUT_ID}" in sent["success_url"] and "kind=topup" in sent["success_url"]
        assert await ledger(db, org) == []  # nothing is credited until Polar says paid

    async def test_the_return_page_sees_the_credit_land(self, db, org, owner, monkeypatch):
        order = polar_topup_order(org, owner)
        checkout = {"status": "succeeded", "metadata": order["metadata"]}

        class Client:
            async def get_checkout(self, checkout_id):
                return checkout

        monkeypatch.setattr(polar_service, "get_polar_client", lambda: Client())
        assert await wallet_topups.polar_topup_status(db, organization_id=org.id, checkout_id="c") == "pending"
        await polar_service.handle_webhook_event(db, "wh_1", {"type": "order.paid", "data": order})
        assert await wallet_topups.polar_topup_status(db, organization_id=org.id, checkout_id="c") == "active"

        other, _ = await make_org(db, "Other")
        assert await wallet_topups.polar_topup_status(db, organization_id=other.id, checkout_id="c") is None


# ==================== Auto-recharge ====================


class TestAutoRecharge:
    @pytest.fixture
    def stripe_on(self, monkeypatch):
        calls = []

        async def no_stripe():
            return None

        monkeypatch.setattr(wallet_topups, "auto_recharge_supported", lambda: True)
        monkeypatch.setattr(wallet_topups, "_configure_stripe", no_stripe)
        return calls

    async def _wallet(self, db, org, *, balance_cents=300):
        await put_on_payg(db, org, balance_cents=balance_cents)
        wallet = await wallet_service.get_wallet(db, org.id)
        wallet.auto_recharge_enabled = True
        wallet.auto_recharge_threshold_cents = 500
        wallet.auto_recharge_amount_cents = 2500
        wallet.stripe_payment_method_id = "pm_saved"
        wallet.stripe_customer_id = "cus_saved"
        await db.commit()
        return wallet

    async def test_a_low_balance_charges_the_saved_card_once(self, db, org, owner, stripe_on, monkeypatch):
        import stripe

        wallet = await self._wallet(db, org)

        def create(**params):
            stripe_on.append(params)
            return topup_intent(org, owner, amount=params["amount"], automatic=1)

        monkeypatch.setattr(stripe.PaymentIntent, "create", create)

        result = await wallet_topups.run_auto_recharge(db, org.id)
        assert result.credited and result.automatic
        assert await balance(db, org) == 300 + 2500
        params = stripe_on[0]
        assert params["off_session"] is True and params["confirm"] is True
        assert params["customer"] == "cus_saved" and params["payment_method"] == "pm_saved"
        assert params["amount"] == 2500

        # Back above the threshold: nothing more to do.
        assert await wallet_topups.run_auto_recharge(db, org.id) is None
        assert len(stripe_on) == 1

    async def test_a_second_trigger_right_after_stands_down(self, db, org, owner, stripe_on, monkeypatch):
        import stripe

        await self._wallet(db, org)

        def create(**params):
            stripe_on.append(params)
            return topup_intent(org, owner, status="processing")  # not settled yet

        monkeypatch.setattr(stripe.PaymentIntent, "create", create)
        await wallet_topups.run_auto_recharge(db, org.id)
        await wallet_topups.run_auto_recharge(db, org.id)
        assert len(stripe_on) == 1

    async def test_a_declined_card_is_reported_and_retried_a_day_later(
        self, db, org, owner, stripe_on, monkeypatch, quiet_notices
    ):
        import stripe

        wallet = await self._wallet(db, org)

        def decline(**params):
            stripe_on.append(params)
            raise stripe.error.CardError("Your card was declined.", "card", "card_declined")

        monkeypatch.setattr(stripe.PaymentIntent, "create", decline)
        now = datetime.utcnow()
        await wallet_topups.run_auto_recharge(db, org.id, now=now)
        await db.refresh(wallet)
        assert wallet.auto_recharge_failures == 1 and wallet.auto_recharge_enabled
        assert any("couldn't top up" in n["subject"] for n in quiet_notices)

        await wallet_topups.run_auto_recharge(db, org.id, now=now + timedelta(hours=1))
        assert len(stripe_on) == 1  # not hammered

        await wallet_topups.run_auto_recharge(db, org.id, now=now + timedelta(hours=25))
        await wallet_topups.run_auto_recharge(db, org.id, now=now + timedelta(hours=50))
        await db.refresh(wallet)
        assert len(stripe_on) == 3
        assert wallet.auto_recharge_failures == 3
        assert wallet.auto_recharge_enabled is False  # switched itself off
        assert await balance(db, org) == 300

    async def test_nothing_is_charged_without_a_saved_card_or_when_switched_off(
        self, db, org, owner, stripe_on, monkeypatch
    ):
        import stripe

        wallet = await self._wallet(db, org)
        monkeypatch.setattr(
            stripe.PaymentIntent, "create", lambda **p: stripe_on.append(p) or topup_intent(org, owner)
        )
        wallet.auto_recharge_enabled = False
        await db.commit()
        assert await wallet_topups.run_auto_recharge(db, org.id) is None
        wallet.auto_recharge_enabled = True
        wallet.stripe_payment_method_id = None
        await db.commit()
        assert await wallet_topups.run_auto_recharge(db, org.id) is None
        assert stripe_on == []

    async def test_it_is_not_offered_when_polar_takes_the_payments(self, monkeypatch):
        monkeypatch.setattr(providers, "active_provider", lambda: providers.POLAR)
        assert wallet_topups.auto_recharge_supported() is False


# ==================== Switching plans ====================


class TestSwitching:
    async def test_activating_twice_changes_nothing(self, db, org):
        first = await put_on_payg(db, org)
        second = await prepaid.activate(db, org.id)
        await db.commit()
        assert first.id == second.id
        count = (await db.execute(select(func.count(Subscription.id)))).scalar()
        assert count == 1

    async def test_a_provider_billed_workspace_is_not_switched_by_a_topup(self, db, org):
        subscription = await paid_subscription(db, org, "growth")
        assert await prepaid.activate(db, org.id) is None
        await db.refresh(subscription)
        assert subscription.source == SOURCE_STRIPE

    async def test_a_lapsed_trial_comes_back_on_the_plan(self, db, org, owner):
        trial = await start_trial(db, org, owner)
        trial.status = "expired"
        trial.expired_at = datetime.utcnow()
        await db.commit()
        get_entitlement_service().invalidate(org.id)
        assert not (await resolve_entitlements(db, org.id, fresh=True)).is_live

        await put_on_payg(db, org, balance_cents=1000)
        ent = await resolve_entitlements(db, org.id, fresh=True)
        assert ent.is_live and ent.is_prepaid
        assert (await prepaid.current_subscription(db, org.id)).id == trial.id

    async def test_change_plan_queues_the_move_for_the_end_of_the_paid_period(
        self, db, org, owner, monkeypatch
    ):
        subscription = await paid_subscription(db, org, "starter")
        told = []

        async def tell_provider(sub, cancel):
            told.append(cancel)

        monkeypatch.setattr(billing, "_set_provider_cancel_at_period_end", tell_provider)
        plan = await payg_plan(db)

        response = await billing.change_plan(
            billing.ChangePlanRequest(plan_id=plan.id), current_user=owner, org_id=org.id, db=db
        )
        await db.refresh(subscription)
        assert told == [True]
        assert subscription.scheduled_plan_id == plan.id and subscription.cancel_at_period_end
        assert subscription.source == SOURCE_STRIPE  # still the plan they paid for
        assert subscription.plan_id == (await plan_by_slug(db, "starter")).id
        assert response.scheduled_plan_name == "Pay As You Go"
        assert not (await resolve_entitlements(db, org.id, fresh=True)).is_prepaid

    async def test_choosing_the_current_plan_again_undoes_the_queued_move(
        self, db, org, owner, monkeypatch
    ):
        subscription = await paid_subscription(db, org, "starter")
        told = []

        async def tell_provider(sub, cancel):
            told.append(cancel)

        monkeypatch.setattr(billing, "_set_provider_cancel_at_period_end", tell_provider)
        await billing.change_plan(
            billing.ChangePlanRequest(plan_id=(await payg_plan(db)).id),
            current_user=owner, org_id=org.id, db=db,
        )
        await billing.change_plan(
            billing.ChangePlanRequest(plan_id=subscription.plan_id),
            current_user=owner, org_id=org.id, db=db,
        )
        await db.refresh(subscription)
        assert told == [True, False]
        assert subscription.scheduled_plan_id is None and not subscription.cancel_at_period_end
        assert subscription.canceled_at is None

    async def test_the_move_is_refused_when_the_workspace_does_not_fit(self, db, org, owner, monkeypatch):
        from app.models.agent import Agent as AgentModel

        await paid_subscription(db, org, "growth")
        for index in range(2):
            db.add(
                AgentModel(
                    user_id=owner.id, organization_id=org.id, name=f"Agent {index}",
                    system_prompt="x", is_active=True,
                )
            )
        await db.commit()
        with pytest.raises(HTTPException) as refused:
            await billing.change_plan(
                billing.ChangePlanRequest(plan_id=(await payg_plan(db)).id),
                current_user=owner, org_id=org.id, db=db,
            )
        assert refused.value.status_code == 409
        assert refused.value.detail["code"] == "downgrade_blocked"

    async def test_a_trial_is_told_to_top_up_rather_than_switched_for_free(self, db, org, owner):
        trial = await start_trial(db, org, owner)
        with pytest.raises(HTTPException) as refused:
            await billing.change_plan(
                billing.ChangePlanRequest(plan_id=(await payg_plan(db)).id),
                current_user=owner, org_id=org.id, db=db,
            )
        assert refused.value.status_code == 409
        assert refused.value.detail["code"] == "topup_required"
        await db.refresh(trial)
        assert trial.source == SOURCE_TRIAL

    async def test_a_prepaid_workspace_cannot_take_a_subscription_without_paying(self, db, org, owner):
        subscription = await put_on_payg(db, org, balance_cents=1000)
        with pytest.raises(HTTPException) as refused:
            await billing.change_plan(
                billing.ChangePlanRequest(plan_id=(await plan_by_slug(db, "agency")).id),
                current_user=owner, org_id=org.id, db=db,
            )
        assert refused.value.status_code == 409
        assert refused.value.detail["code"] == "checkout_required"
        await db.refresh(subscription)
        assert subscription.plan_id == (await payg_plan(db)).id

    async def test_the_prepaid_plan_cannot_be_bought_at_subscription_checkout(self, db):
        with pytest.raises(HTTPException) as refused:
            billing._refuse_prepaid_checkout(await payg_plan(db))
        assert refused.value.detail["code"] == "topup_required"
        billing._refuse_prepaid_checkout(await plan_by_slug(db, "starter"))  # no error

    async def test_the_subscription_ending_switches_to_the_wallet_with_no_gap(self, db, org, owner):
        """Stripe reports the subscription over: the same row becomes Pay As You Go."""
        from app.services.billing.stripe_service import apply_stripe_subscription

        subscription = await paid_subscription(db, org, "starter")
        subscription.scheduled_plan_id = (await payg_plan(db)).id
        subscription.cancel_at_period_end = True
        await wallet_service.apply(db, org.id, amount_cents=2000, type=TXN_TOPUP, idempotency_key="t")
        await db.commit()

        ended = int(datetime.utcnow().timestamp())
        await apply_stripe_subscription(
            db, subscription, {"id": subscription.stripe_subscription_id, "status": "canceled", "ended_at": ended}
        )
        await db.commit()
        get_entitlement_service().invalidate(org.id)

        assert subscription.source == SOURCE_WALLET and subscription.status == STATUS_ACTIVE
        assert subscription.stripe_subscription_id is None
        assert subscription.scheduled_plan_id is None and not subscription.cancel_at_period_end
        ent = await resolve_entitlements(db, org.id, fresh=True)
        assert ent.is_live and ent.is_prepaid
        assert await balance(db, org) == 2000  # credit added ahead of the switch is kept

    async def test_a_polar_subscription_ending_switches_too(self, db, org, owner):
        subscription = await paid_subscription(db, org, "starter", source=SOURCE_POLAR)
        subscription.scheduled_plan_id = (await payg_plan(db)).id
        subscription.cancel_at_period_end = True
        await db.commit()

        outcome = polar_service.WebhookOutcome()
        await polar_service.sync_subscription(
            db,
            {"id": subscription.polar_subscription_id, "status": "canceled",
             "ended_at": datetime.utcnow().isoformat() + "Z"},
            outcome,
        )
        await db.commit()
        assert subscription.source == SOURCE_WALLET and subscription.status == STATUS_ACTIVE
        assert subscription.polar_subscription_id is None
        assert outcome.prepaid_started == [org.id]

    async def test_the_reconciler_catches_a_switch_whose_webhook_was_missed(self, db, org, quiet_notices):
        subscription = await paid_subscription(db, org, "starter")
        subscription.status = STATUS_CANCELED
        subscription.current_period_end = datetime.utcnow() - timedelta(hours=1)
        subscription.scheduled_plan_id = (await payg_plan(db)).id
        await db.commit()

        await reconcile_subscriptions(db)
        await db.refresh(subscription)
        assert subscription.source == SOURCE_WALLET and subscription.status == STATUS_ACTIVE
        assert any("You're now on Pay As You Go" in n["subject"] for n in quiet_notices)

    async def test_a_queued_move_is_not_applied_as_a_plain_plan_swap(self, db, org):
        """While Stripe is still billing it, the row must not be put on a plan
        with nothing to bill."""
        subscription = await paid_subscription(db, org, "starter")
        subscription.scheduled_plan_id = (await payg_plan(db)).id
        subscription.current_period_end = datetime.utcnow() - timedelta(minutes=5)
        await db.commit()

        await reconcile_subscriptions(db)
        await db.refresh(subscription)
        assert subscription.source == SOURCE_STRIPE
        assert subscription.plan_id == (await plan_by_slug(db, "starter")).id
        assert subscription.scheduled_plan_id is not None

    async def test_an_ordinary_cancellation_still_expires(self, db, org):
        subscription = await paid_subscription(db, org, "starter")
        subscription.status = STATUS_CANCELED
        subscription.current_period_end = datetime.utcnow() - timedelta(hours=1)
        await db.commit()
        await reconcile_subscriptions(db)
        await db.refresh(subscription)
        assert subscription.status == "expired" and subscription.source == SOURCE_STRIPE


# ==================== Phone number rent ====================


async def voicecon_number(db, org, owner, number="+14155550123") -> PhoneNumber:
    row = PhoneNumber(
        user_id=owner.id,
        organization_id=org.id,
        phone_number=number,
        provider="twilio",
        provider_sid="PN123",
        provider_metadata={"credential_source": "platform"},
        status="active",
    )
    db.add(row)
    await db.commit()
    return row


class TestNumberFees:
    async def test_a_number_is_paid_for_from_the_wallet_once_a_period(self, db, org, owner):
        await put_on_payg(db, org, balance_cents=1000)
        number = await voicecon_number(db, org, owner)
        now = datetime.utcnow()

        assert await prepaid.settle_number_fees(db, org.id, [number], now=now) is True
        assert await balance(db, org) == 800
        assert prepaid.number_paid_through(number) == now + prepaid.NUMBER_FEE_PERIOD

        # Paid up: the next sweeps charge nothing.
        assert await prepaid.settle_number_fees(db, org.id, [number], now=now + timedelta(days=5)) is True
        assert await balance(db, org) == 800

        # A period later, the next payment is taken.
        later = now + prepaid.NUMBER_FEE_PERIOD + timedelta(minutes=1)
        assert await prepaid.settle_number_fees(db, org.id, [number], now=later) is True
        assert await balance(db, org) == 600
        assert len(await ledger(db, org, TXN_NUMBER_FEE)) == 2

    async def test_a_wallet_that_cannot_pay_leaves_the_number_uncovered(self, db, org, owner):
        await put_on_payg(db, org, balance_cents=100)
        number = await voicecon_number(db, org, owner)
        assert await prepaid.settle_number_fees(db, org.id, [number]) is False
        assert await balance(db, org) == 100
        assert prepaid.number_paid_through(number) is None

        await wallet_service.apply(db, org.id, amount_cents=1000, type=TXN_TOPUP, idempotency_key="t")
        await db.commit()
        assert await prepaid.settle_number_fees(db, org.id, [number]) is True
        assert await balance(db, org) == 900

    async def test_a_subscriptions_numbers_are_covered_by_its_fee(self, db, org, owner):
        await paid_subscription(db, org)
        number = await voicecon_number(db, org, owner)
        assert await prepaid.settle_number_fees(db, org.id, [number]) is True
        assert await ledger(db, org) == []

    async def test_with_no_fee_a_number_is_covered_while_there_is_credit(self, db, org, owner):
        plan = await payg_plan(db)
        plan.entitlements = {
            **plan.entitlements,
            "billing": {**plan.entitlements["billing"], "number_monthly_fee": 0},
        }
        await db.commit()
        await put_on_payg(db, org, balance_cents=500)
        number = await voicecon_number(db, org, owner)
        assert await prepaid.settle_number_fees(db, org.id, [number]) is True
        await wallet_service.apply(db, org.id, amount_cents=-500, type=TXN_USAGE, idempotency_key="u")
        await db.commit()
        assert await prepaid.settle_number_fees(db, org.id, [number]) is False
        assert await ledger(db, org, TXN_NUMBER_FEE) == []

    async def test_the_number_sweep_holds_an_unpaid_number_and_restores_it(self, db, org, owner, monkeypatch):
        from app.services.telephony import number_reclaim

        async def no_notice(*args, **kwargs):
            return None

        monkeypatch.setattr(number_reclaim, "_notify", no_notice)
        await put_on_payg(db, org, balance_cents=100)
        number = await voicecon_number(db, org, owner)

        report = await number_reclaim.reclaim_numbers(db)
        await db.refresh(number)
        assert report.suspended == 1 and number.status == "suspended"

        await wallet_service.apply(db, org.id, amount_cents=1000, type=TXN_TOPUP, idempotency_key="t")
        await db.commit()
        get_entitlement_service().invalidate(org.id)
        report = await number_reclaim.reclaim_numbers(db)
        await db.refresh(number)
        assert number.status == "active"
        assert await balance(db, org) == 1100 - 200


# ==================== Admin ====================


class TestAdjustments:
    async def test_staff_credit_is_a_ledger_row_with_a_reason(self, db, org, owner):
        movement = await wallet_topups.adjust(
            db, org.id, amount_cents=1500, reason="Goodwill for the outage", admin=owner
        )
        await db.commit()
        assert movement.balance_cents == 1500
        row = (await ledger(db, org))[0]
        assert row.type == "adjustment" and row.actor_type == "admin" and row.actor_id == owner.id
        assert row.details["reason"] == "Goodwill for the outage"

    async def test_a_reason_and_an_amount_are_required(self, db, org, owner):
        with pytest.raises(wallet_service.WalletError):
            await wallet_topups.adjust(db, org.id, amount_cents=1500, reason="  ", admin=owner)
        with pytest.raises(wallet_service.WalletError):
            await wallet_topups.adjust(db, org.id, amount_cents=0, reason="why", admin=owner)

    async def test_the_admin_billing_settings_are_validated(self):
        from app.api.v1.endpoints.admin.billing import _validated_billing

        current = dict(catalog.PAYG_BILLING)
        assert _validated_billing({"per_minute": 0.4}, current)["per_minute"] == 0.4
        for bad in (
            {"per_minute": 0},
            {"per_minute": -1},
            {"topup_min": 50, "topup_max": 20},
            {"topup_presets": [5]},          # below the minimum
            {"topup_presets": []},
            {"mode": "subscription"},        # a plan does not change kind
            {"per_minute": "abc"},
        ):
            with pytest.raises(HTTPException):
                _validated_billing(bad, current)


# ==================== Real row locks ====================


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.mark.skipif(
    not TEST_DATABASE_URL.startswith("postgresql"),
    reason="needs TEST_DATABASE_URL pointing at Postgres (row locks are a no-op on SQLite)",
)
class TestConcurrentDebits:
    """The same paths under real concurrency, each on its own connection."""

    @pytest_asyncio.fixture
    async def factory(self):
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine, expire_on_commit=False)
        await engine.dispose()
        get_entitlement_service().invalidate_all()

    async def _org_on_payg(self, factory, balance_cents):
        async with factory() as db:
            await seed_default_plans(db)
            org, owner = await make_org(db, f"Concurrent {uuid.uuid4().hex[:6]}")
            await put_on_payg(db, org, balance_cents=balance_cents)
            return org, owner

    async def test_many_debits_at_once_all_land_and_the_ledger_agrees(self, factory):
        org, _ = await self._org_on_payg(factory, 10_000)

        async def debit(index):
            async with factory() as db:
                await wallet_service.apply(
                    db, org.id, amount_cents=-35, type=TXN_USAGE,
                    idempotency_key=f"c:{org.id}:{index}", low_balance_cents=0,
                )
                await db.commit()

        await asyncio.gather(*(debit(i) for i in range(40)))
        async with factory() as db:
            assert await wallet_service.balance_cents(db, org.id) == 10_000 - 40 * 35
            rows = await ledger(db, org, TXN_USAGE)
            assert len(rows) == 40
            # Every row saw the balance the one before it left behind.
            assert sorted(r.balance_after_cents for r in rows) == [
                10_000 - 35 * n for n in range(40, 0, -1)
            ]
            mine = [m for m in await wallet_service.ledger_mismatches(db, limit=1000)
                    if m["organization_id"] == str(org.id)]
            assert mine == []

    async def test_the_same_payment_delivered_many_times_at_once_credits_once(self, factory):
        org, owner = await self._org_on_payg(factory, 0)
        intent = topup_intent(org, owner, amount=2500)

        async def deliver():
            async with factory() as db:
                try:
                    await wallet_topups.credit_stripe_intent(db, intent)
                except Exception:
                    await db.rollback()  # lost the race on the unique key

        await asyncio.gather(*(deliver() for _ in range(12)))
        async with factory() as db:
            assert await wallet_service.balance_cents(db, org.id) == 2500
            assert len(await ledger(db, org, TXN_TOPUP)) == 1

    async def test_the_same_call_reported_many_times_at_once_is_charged_once(self, factory):
        org, owner = await self._org_on_payg(factory, 1000)
        async with factory() as db:
            call = await make_call(db, org, owner, seconds=120)

        async def report():
            async with factory() as db:
                await UsageTracker.record_call_usage(db, call.id, org.id)

        await asyncio.gather(*(report() for _ in range(10)))
        async with factory() as db:
            assert await wallet_service.balance_cents(db, org.id) == 1000 - 70
            assert len(await ledger(db, org, TXN_USAGE)) == 1

    async def test_calls_arriving_together_cannot_reserve_more_than_the_balance(self, factory):
        org, owner = await self._org_on_payg(factory, 105)  # three minutes in all
        async with factory() as db:
            calls = [await make_call(db, org, owner, status="ringing") for _ in range(8)]

        async def reserve(call):
            async with factory() as db:
                try:
                    return await wallet_service.reserve_for_call(db, call.id, max_seconds=1800)
                except wallet_service.InsufficientBalance:
                    return 0

        granted = await asyncio.gather(*(reserve(c) for c in calls))
        async with factory() as db:
            held = await wallet_service.held_cents(db, org.id)
        assert held <= 105
        assert sum(granted) // 60 * 35 == held
        assert 0 in granted  # some were turned away
