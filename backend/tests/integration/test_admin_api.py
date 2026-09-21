"""
Platform admin API (/api/v1/admin).

Covers the properties that matter most, rather than every field:

* Access: only ``is_platform_admin`` users get in; workspace owners and API
  keys are refused.
* Settings: a saved secret is encrypted at rest, never echoed back, applied to
  the live ``settings`` object, and reset to the environment on delete.
* Every write leaves an audit row, and no audit row contains a secret.
* Billing actions (extend trial, override, plan edit) change what the
  entitlement resolver returns, and a plan edit survives the startup backfill.

Same harness as ``test_settings_api``: in-loop httpx client, per-request DB
sessions, and ``get_current_user`` loading the acting user from that session.
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core import runtime_settings
from app.core.config import settings
from app.core.dependencies import get_current_user, get_optional_api_key
from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models.platform import AdminAuditLog, PlatformSetting
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.user import Organization, OrganizationMember, User
from app.services.billing.entitlements import get_entitlement_service

_ACTING: dict = {"id": None}

SECRET = "sk-test-admin-dashboard-secret-value-1234"


async def _make_user(db, email, *, admin=False) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash("password123"),
        full_name=email.split("@")[0],
        is_active=True,
        is_verified=True,
        is_platform_admin=admin,
    )
    db.add(user)
    await db.flush()
    org = Organization(name=f"{email} org", slug=f"org-{uuid.uuid4().hex[:8]}", owner_id=user.id, is_active=True)
    db.add(org)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    await db.commit()
    await db.refresh(user)
    return user


async def _org_of(db, user) -> Organization:
    return (await db.execute(select(Organization).where(Organization.owner_id == user.id))).scalar_one()


@pytest_asyncio.fixture
async def admin(db_session) -> User:
    return await _make_user(db_session, "admin@example.com", admin=True)


@pytest_asyncio.fixture
async def customer(db_session) -> User:
    return await _make_user(db_session, "customer@example.com")


@pytest_asyncio.fixture
async def plan(db_session) -> SubscriptionPlan:
    plan = SubscriptionPlan(
        slug="voice-ai",
        name="Voice AI",
        tier=2,
        stripe_product_id="local_voice-ai",
        stripe_price_id="local_voice-ai_monthly",
        price_monthly=Decimal("359"),
        currency="usd",
        included_minutes=0,
        included_calls=0,
        max_agents=5,
        max_phone_numbers=5,
        max_knowledge_bases=5,
        overage_rate_per_minute=Decimal("0"),
        overage_rate_per_call=Decimal("0"),
        features={"highlights": ["One"]},
        entitlements={"features": {"workflows": True, "workflow_scheduling": False}, "limits": {"agents": 5}},
        trial_days=30,
        is_trialable=True,
        is_active=True,
        is_public=True,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


@pytest_asyncio.fixture
async def client(db_engine):
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    async def _current_user(db=Depends(get_db)):
        return (await db.execute(select(User).where(User.id == _ACTING["id"]))).scalar_one()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _current_user
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    # Settings saved by a test are applied to the process-wide object.
    runtime_settings.reset_for_tests()
    get_entitlement_service().invalidate_all()


def as_user(client, user):
    _ACTING["id"] = user.id
    return client


# ---------- Access ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestAccess:
    async def test_workspace_owner_is_refused(self, client, customer):
        res = await as_user(client, customer).get("/api/v1/admin/overview")
        assert res.status_code == 403

    async def test_api_key_is_refused_even_for_an_admin(self, client, admin):
        app.dependency_overrides[get_optional_api_key] = lambda: object()
        try:
            res = await as_user(client, admin).get("/api/v1/admin/me")
        finally:
            app.dependency_overrides.pop(get_optional_api_key, None)
        assert res.status_code == 403

    async def test_admin_gets_in(self, client, admin, customer):
        res = await as_user(client, admin).get("/api/v1/admin/overview")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["kpis"]["users_total"] >= 2
        assert len(body["calls_daily"]) == 14

    async def test_me_reports_admin_flag(self, client, admin):
        res = await as_user(client, admin).get("/api/v1/users/me")
        assert res.json()["is_platform_admin"] is True


# ---------- Settings ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestSettings:
    async def test_secret_is_encrypted_masked_and_applied(self, client, admin, db_session):
        res = await as_user(client, admin).put("/api/v1/admin/settings/OPENAI_API_KEY", json={"value": SECRET})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["source"] == "database"
        assert body["value"] is None
        assert body["hint"] == "••••" + SECRET[-4:]
        assert SECRET not in res.text

        # Applied to the live settings object the rest of the app reads.
        assert settings.OPENAI_API_KEY == SECRET

        row = await db_session.get(PlatformSetting, "OPENAI_API_KEY")
        await db_session.refresh(row)
        assert row.is_secret and row.value is None
        assert row.value_encrypted and SECRET not in row.value_encrypted

        listing = await client.get("/api/v1/admin/settings")
        assert listing.status_code == 200
        assert SECRET not in listing.text

    async def test_reset_restores_environment_value(self, client, admin):
        baseline = runtime_settings.baseline_value("OPENAI_API_KEY")
        await as_user(client, admin).put("/api/v1/admin/settings/OPENAI_API_KEY", json={"value": SECRET})
        res = await client.delete("/api/v1/admin/settings/OPENAI_API_KEY")
        assert res.status_code == 200
        assert settings.OPENAI_API_KEY == baseline

    async def test_typed_values_are_validated_and_coerced(self, client, admin):
        as_user(client, admin)
        bad = await client.put("/api/v1/admin/settings/SMTP_PORT", json={"value": "not-a-number"})
        assert bad.status_code == 422
        ok = await client.put("/api/v1/admin/settings/SMTP_PORT", json={"value": "2525"})
        assert ok.status_code == 200
        assert settings.SMTP_PORT == 2525
        flag = await client.put("/api/v1/admin/settings/REQUIRE_EMAIL_VERIFICATION", json={"value": False})
        assert flag.status_code == 200
        assert settings.REQUIRE_EMAIL_VERIFICATION is False

    async def test_bootstrap_secrets_cannot_be_managed(self, client, admin):
        res = await as_user(client, admin).put("/api/v1/admin/settings/SECRET_KEY", json={"value": "x" * 40})
        assert res.status_code == 404
        assert settings.SECRET_KEY != "x" * 40

    async def test_audit_trail_never_contains_the_secret(self, client, admin, db_session):
        await as_user(client, admin).put("/api/v1/admin/settings/STRIPE_SECRET_KEY", json={"value": SECRET})
        rows = (await db_session.execute(select(AdminAuditLog))).scalars().all()
        assert any(r.action == "setting.update" and r.target_id == "STRIPE_SECRET_KEY" for r in rows)
        for r in rows:
            assert SECRET not in (r.summary or "")
            assert SECRET not in str(r.details or {})

    async def test_customer_cannot_write_settings(self, client, customer):
        res = await as_user(client, customer).put("/api/v1/admin/settings/OPENAI_API_KEY", json={"value": SECRET})
        assert res.status_code == 403
        assert settings.OPENAI_API_KEY != SECRET


# ---------- Organizations & users ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestOrganizations:
    async def test_list_and_detail(self, client, admin, customer):
        as_user(client, admin)
        res = await client.get("/api/v1/admin/organizations", params={"search": "customer"})
        assert res.status_code == 200, res.text
        items = res.json()["items"]
        assert len(items) == 1 and items[0]["owner"]["email"] == "customer@example.com"
        detail = await client.get(f"/api/v1/admin/organizations/{items[0]['id']}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["members"][0]["role"] == "owner"

    async def test_suspend_blocks_the_workspace(self, client, admin, customer, db_session):
        org = await _org_of(db_session, customer)
        res = await as_user(client, admin).post(f"/api/v1/admin/organizations/{org.id}/suspend", json={"reason": "abuse"})
        assert res.status_code == 200
        await db_session.refresh(org)
        assert org.is_active is False
        # The customer can no longer act in it.
        blocked = await as_user(client, customer).get("/api/v1/agents")
        assert blocked.status_code in (403, 404)

    async def test_extend_expired_trial_revives_it(self, client, admin, customer, plan, db_session):
        org = await _org_of(db_session, customer)
        past = datetime.utcnow() - timedelta(days=20)
        sub = Subscription(
            organization_id=org.id, plan_id=plan.id, status="expired", source="trial",
            billing_period="monthly", current_period_start=past - timedelta(days=30),
            current_period_end=past, trial_start=past - timedelta(days=30), trial_end=past,
            expired_at=past,
        )
        db_session.add(sub)
        await db_session.commit()

        res = await as_user(client, admin).post(
            f"/api/v1/admin/organizations/{org.id}/extend-trial", json={"days": 14, "reason": "sales"}
        )
        assert res.status_code == 200, res.text
        await db_session.refresh(sub)
        assert sub.status == "trialing"
        assert sub.trial_end > datetime.utcnow() + timedelta(days=13)

    async def test_override_changes_entitlements(self, client, admin, customer, plan, db_session):
        org = await _org_of(db_session, customer)
        now = datetime.utcnow()
        db_session.add(Subscription(
            organization_id=org.id, plan_id=plan.id, status="trialing", source="trial",
            billing_period="monthly", current_period_start=now, current_period_end=now + timedelta(days=30),
            trial_start=now, trial_end=now + timedelta(days=30),
        ))
        await db_session.commit()

        res = await as_user(client, admin).put(
            f"/api/v1/admin/organizations/{org.id}/override",
            json={"features": {"white_label": True}, "reason": "enterprise pilot"},
        )
        assert res.status_code == 200, res.text
        detail = (await client.get(f"/api/v1/admin/organizations/{org.id}")).json()
        assert "white_label" in detail["entitlements"]["features"]

    async def test_grant_plan_creates_manual_subscription(self, client, admin, customer, plan, db_session):
        org = await _org_of(db_session, customer)
        res = await as_user(client, admin).post(
            f"/api/v1/admin/organizations/{org.id}/grant-plan", json={"plan_id": str(plan.id)}
        )
        assert res.status_code == 200, res.text
        sub = (await db_session.execute(select(Subscription).where(Subscription.organization_id == org.id))).scalar_one()
        assert sub.source == "manual" and sub.status == "active"


@pytest.mark.integration
@pytest.mark.asyncio
class TestUsers:
    async def test_cannot_demote_or_disable_self(self, client, admin):
        as_user(client, admin)
        res = await client.patch(f"/api/v1/admin/users/{admin.id}", json={"is_platform_admin": False})
        assert res.status_code == 409
        res = await client.patch(f"/api/v1/admin/users/{admin.id}", json={"is_active": False})
        assert res.status_code == 409

    async def test_disable_user_signs_them_out(self, client, admin, customer, db_session):
        before = customer.token_version
        res = await as_user(client, admin).patch(f"/api/v1/admin/users/{customer.id}", json={"is_active": False})
        assert res.status_code == 200, res.text
        await db_session.refresh(customer)
        assert customer.is_active is False
        assert customer.token_version == before + 1

    async def test_grant_admin(self, client, admin, customer, db_session):
        res = await as_user(client, admin).patch(f"/api/v1/admin/users/{customer.id}", json={"is_platform_admin": True})
        assert res.status_code == 200
        await db_session.refresh(customer)
        assert customer.is_platform_admin is True


# ---------- Plans ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestPlans:
    async def test_plan_edit_survives_startup_backfill(self, client, admin, plan, db_session):
        res = await as_user(client, admin).patch(
            f"/api/v1/admin/plans/{plan.id}",
            json={"trial_days": 14, "limits": {"agents": 12}, "features": {"workflow_scheduling": True}},
        )
        assert res.status_code == 200, res.text
        assert res.json()["admin_managed"] is True

        from app.services.billing.seed_plans import backfill_plan_entitlements

        # The backfill runs in a fresh session at startup; drop this session's
        # pre-edit copy of the plan so it reads what the endpoint committed.
        db_session.expire_all()
        await backfill_plan_entitlements(db_session)
        await db_session.refresh(plan)
        assert plan.trial_days == 14
        assert plan.entitlements["limits"]["agents"] == 12
        assert plan.entitlements["features"]["workflow_scheduling"] is True
        assert plan.max_agents == 12

    async def test_unknown_feature_rejected(self, client, admin, plan):
        res = await as_user(client, admin).patch(f"/api/v1/admin/plans/{plan.id}", json={"features": {"nope": True}})
        assert res.status_code == 422
