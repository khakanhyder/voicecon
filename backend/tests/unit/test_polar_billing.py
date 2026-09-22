"""
Polar as a payment provider: webhook signatures, the subscription sync, and the
admin guard that keeps checkout working when the provider is switched.

Runs against an in-memory SQLite database, like ``test_subscription_lifecycle``.
"""

import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database import Base
from app.models.subscription import (
    SOURCE_POLAR,
    SOURCE_TRIAL,
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_PAST_DUE,
    STATUS_TRIALING,
    Invoice,
    Subscription,
    SubscriptionEvent,
    SubscriptionPlan,
    TrialGrant,
)
from app.models.user import Organization, OrganizationMember, User
from app.services.billing import catalog, polar_service, providers
from app.services.billing.reconciler import reset_expired_period_counters

pytestmark = [pytest.mark.unit, pytest.mark.billing]

SECRET = "whsec_" + base64.b64encode(b"polar-test-signing-key-0123456789").decode()


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
async def owner(db: AsyncSession) -> User:
    user = User(email=f"owner-{uuid.uuid4().hex[:8]}@acme.test", hashed_password="x", full_name="Owner", is_active=True)
    db.add(user)
    await db.commit()
    return user


@pytest_asyncio.fixture
async def org(db: AsyncSession, owner: User) -> Organization:
    organization = Organization(name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}", owner_id=owner.id)
    db.add(organization)
    await db.flush()
    db.add(OrganizationMember(organization_id=organization.id, user_id=owner.id, role="owner"))
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


async def make_trial(db, org, plan) -> Subscription:
    now = datetime.utcnow()
    sub = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        status=STATUS_TRIALING,
        source=SOURCE_TRIAL,
        billing_period="monthly",
        current_period_start=now,
        current_period_end=now + timedelta(days=7),
        trial_start=now,
        trial_end=now + timedelta(days=7),
        current_period_minutes=42,
    )
    db.add(sub)
    await db.flush()
    db.add(TrialGrant(organization_id=org.id, user_id=org.owner_id, email_domain="acme.test", expires_at=now + timedelta(days=7)))
    await db.commit()
    return sub


def polar_sub(org, *, product="polar-voice-ai-monthly", status="active", sub_id="psub_1", **extra) -> dict:
    now = datetime.utcnow()
    data = {
        "id": sub_id,
        "status": status,
        "product_id": product,
        "customer_id": "pcus_1",
        "current_period_start": now.isoformat() + "Z",
        "current_period_end": (now + timedelta(days=30)).isoformat() + "Z",
        "cancel_at_period_end": False,
        "canceled_at": None,
        "ended_at": None,
        "metadata": {"organization_id": str(org.id), "user_id": str(org.owner_id)},
        "customer": {"id": "pcus_1", "external_id": str(org.id), "email": "billing@acme.test"},
    }
    data.update(extra)
    return data


async def deliver(db, event_type: str, data: dict, event_id: str = None):
    return await polar_service.handle_webhook_event(
        db, event_id or uuid.uuid4().hex, {"type": event_type, "data": data}
    )


async def events_for(db, sub_id) -> list:
    result = await db.execute(select(SubscriptionEvent.event_type).where(SubscriptionEvent.subscription_id == sub_id))
    return [r[0] for r in result]


# ==================== Signatures ====================


def _sign(key: bytes, msg_id: str, ts: str, body: bytes) -> str:
    return base64.b64encode(hmac.new(key, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()


class TestWebhookSignature:
    body = json.dumps({"type": "subscription.active", "data": {}}).encode()

    def headers(self, signature: str, ts: str = None) -> dict:
        return {"webhook-id": "msg_1", "webhook-timestamp": ts or str(int(time.time())), "webhook-signature": signature}

    def test_standard_webhooks_signature_is_accepted(self, monkeypatch):
        monkeypatch.setattr(settings, "POLAR_WEBHOOK_SECRET", SECRET)
        key = base64.b64decode(SECRET[len("whsec_"):])
        ts = str(int(time.time()))
        payload = polar_service.verify_webhook(self.body, self.headers(f"v1,{_sign(key, 'msg_1', ts, self.body)}", ts))
        assert payload["type"] == "subscription.active"

    def test_legacy_polar_signature_is_accepted(self, monkeypatch):
        monkeypatch.setattr(settings, "POLAR_WEBHOOK_SECRET", SECRET)
        ts = str(int(time.time()))
        sig = _sign(SECRET.encode(), "msg_1", ts, self.body)
        assert polar_service.verify_webhook(self.body, self.headers(f"v1,{sig}", ts))

    def test_one_valid_signature_among_several_is_enough(self, monkeypatch):
        monkeypatch.setattr(settings, "POLAR_WEBHOOK_SECRET", SECRET)
        key = base64.b64decode(SECRET[len("whsec_"):])
        ts = str(int(time.time()))
        header = f"v1,bogus v1,{_sign(key, 'msg_1', ts, self.body)}"
        assert polar_service.verify_webhook(self.body, self.headers(header, ts))

    def test_wrong_signature_is_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "POLAR_WEBHOOK_SECRET", SECRET)
        with pytest.raises(polar_service.WebhookVerificationError):
            polar_service.verify_webhook(self.body, self.headers("v1,AAAA"))

    def test_tampered_body_is_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "POLAR_WEBHOOK_SECRET", SECRET)
        key = base64.b64decode(SECRET[len("whsec_"):])
        ts = str(int(time.time()))
        sig = _sign(key, "msg_1", ts, self.body)
        with pytest.raises(polar_service.WebhookVerificationError):
            polar_service.verify_webhook(self.body + b" ", self.headers(f"v1,{sig}", ts))

    def test_replayed_old_delivery_is_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "POLAR_WEBHOOK_SECRET", SECRET)
        key = base64.b64decode(SECRET[len("whsec_"):])
        ts = str(int(time.time()) - 3600)
        with pytest.raises(polar_service.WebhookVerificationError):
            polar_service.verify_webhook(self.body, self.headers(f"v1,{_sign(key, 'msg_1', ts, self.body)}", ts))

    def test_no_secret_configured_rejects_everything(self, monkeypatch):
        monkeypatch.setattr(settings, "POLAR_WEBHOOK_SECRET", None)
        with pytest.raises(polar_service.WebhookVerificationError):
            polar_service.verify_webhook(self.body, self.headers("v1,x"))


# ==================== Linking and conversion ====================


class TestSubscriptionLinking:
    async def test_active_subscription_converts_the_trial_in_place(self, db, org, plan):
        trial = await make_trial(db, org, plan)
        outcome = await deliver(db, "subscription.active", polar_sub(org))

        await db.refresh(trial)
        assert trial.source == SOURCE_POLAR
        assert trial.status == STATUS_ACTIVE
        assert trial.polar_subscription_id == "psub_1"
        assert trial.polar_customer_id == "pcus_1"
        assert trial.trial_converted_at is not None
        assert trial.trial_end <= datetime.utcnow()
        assert trial.current_period_minutes == 0
        grant = (await db.execute(select(TrialGrant))).scalar_one()
        assert grant.converted is True
        assert "trial_converted" in await events_for(db, trial.id)
        assert org.id in outcome.invalidate
        assert outcome.confirmations and outcome.confirmations[0][1] == plan.name

    async def test_first_subscription_without_a_trial_is_created(self, db, org, plan):
        await deliver(db, "subscription.active", polar_sub(org, product="polar-voice-ai-yearly"))
        sub = (await db.execute(select(Subscription))).scalar_one()
        assert sub.source == SOURCE_POLAR
        assert sub.plan_id == plan.id
        assert sub.billing_period == "yearly"

    async def test_redelivery_is_applied_once(self, db, org, plan):
        await make_trial(db, org, plan)
        await deliver(db, "subscription.active", polar_sub(org), event_id="evt_same")
        await deliver(db, "subscription.active", polar_sub(org), event_id="evt_same")
        rows = (await db.execute(select(SubscriptionEvent.event_type))).scalars().all()
        assert rows.count("trial_converted") == 1

    async def test_incomplete_subscription_is_not_linked(self, db, org, plan):
        trial = await make_trial(db, org, plan)
        await deliver(db, "subscription.created", polar_sub(org, status="incomplete"))
        await db.refresh(trial)
        assert trial.source == SOURCE_TRIAL

    async def test_unmapped_product_falls_back_to_the_checkout_plan(self, db, org, plan):
        data = polar_sub(org, product="polar-unknown")
        data["metadata"]["plan_id"] = str(plan.id)
        data["metadata"]["billing_period"] = "monthly"
        await deliver(db, "subscription.active", data)
        sub = (await db.execute(select(Subscription))).scalar_one()
        assert sub.plan_id == plan.id

    async def test_unmapped_product_with_no_plan_is_left_alone(self, db, org, plan):
        await deliver(db, "subscription.active", polar_sub(org, product="polar-unknown"))
        assert (await db.execute(select(Subscription))).scalar_one_or_none() is None

    async def test_second_paid_subscription_does_not_overwrite_the_first(self, db, org, plan):
        await deliver(db, "subscription.active", polar_sub(org, sub_id="psub_1"))
        await deliver(db, "subscription.active", polar_sub(org, sub_id="psub_2"))
        subs = (await db.execute(select(Subscription))).scalars().all()
        assert [s.polar_subscription_id for s in subs] == ["psub_1"]


# ==================== Lifecycle after linking ====================


class TestLinkedLifecycle:
    async def _linked(self, db, org, plan) -> Subscription:
        await make_trial(db, org, plan)
        await deliver(db, "subscription.active", polar_sub(org))
        return (await db.execute(select(Subscription))).scalar_one()

    async def test_renewal_order_rolls_usage_and_records_the_invoice(self, db, org, plan):
        sub = await self._linked(db, org, plan)
        sub.current_period_minutes = 500
        await db.commit()
        nxt = datetime.utcnow() + timedelta(days=30)
        order = {
            "id": "pord_2",
            "subscription_id": "psub_1",
            "billing_reason": "subscription_cycle",
            "subtotal_amount": 35900,
            "tax_amount": 0,
            "total_amount": 35900,
            "currency": "usd",
            "invoice_number": "INV-2",
            "subscription": {"current_period_start": datetime.utcnow().isoformat(), "current_period_end": nxt.isoformat()},
        }
        await deliver(db, "order.paid", order)
        await db.refresh(sub)
        assert sub.current_period_minutes == 0
        invoice = (await db.execute(select(Invoice))).scalar_one()
        assert invoice.provider == "polar"
        assert invoice.polar_order_id == "pord_2"
        assert float(invoice.total) == 359.0
        assert invoice.stripe_invoice_id is None
        assert "renewed" in await events_for(db, sub.id)

    async def test_order_paid_before_subscription_active_links_it(self, db, org, plan, monkeypatch):
        await make_trial(db, org, plan)

        class FakeClient:
            async def get_subscription(self, _id):
                return polar_sub(org)

        monkeypatch.setattr(polar_service, "get_polar_client", lambda: FakeClient())
        await deliver(db, "order.paid", {"id": "pord_1", "subscription_id": "psub_1", "billing_reason": "subscription_create", "total_amount": 35900})
        sub = (await db.execute(select(Subscription))).scalar_one()
        assert sub.source == SOURCE_POLAR and sub.status == STATUS_ACTIVE
        assert (await db.execute(select(Invoice))).scalar_one().polar_order_id == "pord_1"

    async def test_failed_payment_then_recovery(self, db, org, plan):
        sub = await self._linked(db, org, plan)
        await deliver(db, "subscription.past_due", polar_sub(org, status="past_due"))
        await db.refresh(sub)
        assert sub.status == STATUS_PAST_DUE
        assert sub.grace_period_end is not None
        await deliver(db, "subscription.active", polar_sub(org, status="active"))
        await db.refresh(sub)
        assert sub.status == STATUS_ACTIVE and sub.grace_period_end is None

    async def test_cancel_at_period_end_keeps_access(self, db, org, plan):
        sub = await self._linked(db, org, plan)
        await deliver(db, "subscription.canceled", polar_sub(org, cancel_at_period_end=True, canceled_at=datetime.utcnow().isoformat()))
        await db.refresh(sub)
        assert sub.status == STATUS_ACTIVE
        assert sub.cancel_at_period_end is True
        assert sub.canceled_at is not None
        await deliver(db, "subscription.uncanceled", polar_sub(org))
        await db.refresh(sub)
        assert sub.cancel_at_period_end is False and sub.canceled_at is None

    async def test_revoked_subscription_ends_access_now(self, db, org, plan):
        sub = await self._linked(db, org, plan)
        ended = datetime.utcnow()
        await deliver(db, "subscription.revoked", polar_sub(org, status="canceled", ended_at=ended.isoformat()))
        await db.refresh(sub)
        assert sub.status == STATUS_CANCELED
        assert sub.current_period_end <= ended + timedelta(seconds=1)

    async def test_product_change_moves_the_plan(self, db, org, plan, small_plan):
        sub = await self._linked(db, org, plan)
        sub.scheduled_plan_id = small_plan.id
        await db.commit()
        await deliver(db, "subscription.updated", polar_sub(org, product="polar-sales-chatbot-monthly"))
        await db.refresh(sub)
        assert sub.plan_id == small_plan.id
        assert sub.scheduled_plan_id is None
        assert "plan_changed" in await events_for(db, sub.id)

    async def test_reconciler_leaves_polar_counters_to_the_webhook(self, db, org, plan):
        sub = await self._linked(db, org, plan)
        sub.current_period_end = datetime.utcnow() - timedelta(hours=1)
        sub.current_period_minutes = 77
        await db.commit()
        await reset_expired_period_counters(db)
        await db.refresh(sub)
        assert sub.current_period_minutes == 77


# ==================== Provider switch ====================


class TestProviderSwitch:
    def _clear(self, monkeypatch):
        for key in ("STRIPE_SECRET_KEY", "STRIPE_API_KEY", "STRIPE_PUBLISHABLE_KEY", "STRIPE_WEBHOOK_SECRET", "POLAR_ACCESS_TOKEN", "POLAR_WEBHOOK_SECRET"):
            monkeypatch.setattr(settings, key, None)

    def test_readiness_lists_what_is_missing(self, monkeypatch):
        self._clear(monkeypatch)
        assert providers.missing_for("polar") == ["Polar access token", "Polar webhook signing secret"]
        monkeypatch.setattr(settings, "POLAR_ACCESS_TOKEN", "polar_oat_abc")
        monkeypatch.setattr(settings, "POLAR_WEBHOOK_SECRET", SECRET)
        assert providers.is_ready("polar")
        assert not providers.is_ready("stripe")

    def test_unknown_provider_value_falls_back_to_stripe(self, monkeypatch):
        monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "paypal")
        assert providers.active_provider() == "stripe"

    async def test_switching_to_an_unconfigured_provider_is_refused(self, monkeypatch, db):
        from app.api.v1.endpoints.admin import settings as admin_settings

        async def no_refresh(_db):
            return None

        monkeypatch.setattr(admin_settings.rs, "refresh_quietly", no_refresh)
        self._clear(monkeypatch)
        with pytest.raises(HTTPException) as exc:
            await admin_settings._guard_payment_provider(db, "PAYMENT_PROVIDER", "polar")
        assert exc.value.status_code == 409
        assert "Polar access token" in exc.value.detail

        monkeypatch.setattr(settings, "POLAR_ACCESS_TOKEN", "polar_oat_abc")
        monkeypatch.setattr(settings, "POLAR_WEBHOOK_SECRET", SECRET)
        await admin_settings._guard_payment_provider(db, "PAYMENT_PROVIDER", "polar")

    async def test_removing_a_key_the_active_provider_needs_is_refused(self, monkeypatch, db):
        from app.api.v1.endpoints.admin import settings as admin_settings

        async def no_refresh(_db):
            return None

        monkeypatch.setattr(admin_settings.rs, "refresh_quietly", no_refresh)
        monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "polar")
        with pytest.raises(HTTPException) as exc:
            await admin_settings._guard_payment_provider(db, "POLAR_ACCESS_TOKEN", None)
        assert exc.value.status_code == 409
        # The inactive provider's keys can be removed freely.
        await admin_settings._guard_payment_provider(db, "STRIPE_SECRET_KEY", None)


# ==================== Through the HTTP route ====================


class TestWebhookRoute:
    async def test_signed_delivery_is_applied_and_a_bad_one_refused(self, db, org, plan, monkeypatch):
        import httpx

        from app.database import get_db
        from app.main import app

        monkeypatch.setattr(settings, "POLAR_WEBHOOK_SECRET", SECRET)

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        try:
            await make_trial(db, org, plan)
            body = json.dumps({"type": "subscription.active", "data": polar_sub(org)}).encode()
            ts = str(int(time.time()))
            key = base64.b64decode(SECRET[len("whsec_"):])
            headers = {
                "content-type": "application/json",
                "webhook-id": "msg_route",
                "webhook-timestamp": ts,
                "webhook-signature": f"v1,{_sign(key, 'msg_route', ts, body)}",
            }
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                bad = await client.post("/api/v1/billing/webhooks/polar", content=body, headers={**headers, "webhook-signature": "v1,AAAA"})
                good = await client.post("/api/v1/billing/webhooks/polar", content=body, headers=headers)
            assert bad.status_code == 400
            assert good.status_code == 200, good.text
            sub = (await db.execute(select(Subscription))).scalar_one()
            assert sub.source == SOURCE_POLAR and sub.status == STATUS_ACTIVE
        finally:
            app.dependency_overrides.pop(get_db, None)
