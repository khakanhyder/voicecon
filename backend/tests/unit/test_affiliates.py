"""
Affiliate program: attribution, coupons, annual-only commissions, refunds,
payouts, and the separate affiliate session scope.

Uses in-memory SQLite like the other billing unit tests; Stripe is mocked at
the SDK boundary, nothing touches the network.
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import (
    SCOPE_AFFILIATE,
    SCOPE_APP,
    create_access_token,
    get_password_hash,
)
from app.database import Base, get_db
from app.models.affiliate import (
    AFFILIATE_ACTIVE,
    AFFILIATE_SUSPENDED,
    COMMISSION_APPROVED,
    COMMISSION_PAID,
    COMMISSION_PENDING,
    COMMISSION_REVERSED,
    KIND_CLAWBACK,
    PAYOUT_FAILED,
    PAYOUT_PAID,
    Affiliate,
    AffiliateCommission,
    AffiliateReferral,
)
from app.models.subscription import (
    SOURCE_STRIPE,
    SOURCE_TRIAL,
    STATUS_ACTIVE,
    STATUS_TRIALING,
    Subscription,
    SubscriptionPlan,
)
from app.models.user import Organization, OrganizationMember, User
from app.services.affiliates import attribution, commissions, coupons, payouts
from app.services.affiliates.invites import invite_token
from app.services.affiliates.program import get_program, unique_coupon_code

pytestmark = [pytest.mark.unit, pytest.mark.billing]

NOW = datetime(2026, 10, 1, 12, 0, 0)


# ==================== Fixtures ====================


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncSession:
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session


async def make_user(db: AsyncSession, email: str, password: str = "x") -> User:
    user = User(email=email, hashed_password=get_password_hash(password), full_name=email.split("@")[0], is_active=True)
    db.add(user)
    await db.flush()
    return user


async def make_org(db: AsyncSession, owner: User) -> Organization:
    org = Organization(name=f"{owner.full_name} Co", slug=f"org-{uuid.uuid4().hex[:8]}", owner_id=owner.id)
    db.add(org)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=owner.id, role="owner"))
    await db.flush()
    return org


@pytest_asyncio.fixture
async def plan(db: AsyncSession) -> SubscriptionPlan:
    plan = SubscriptionPlan(
        slug="growth",
        name="Growth",
        stripe_product_id=f"prod_{uuid.uuid4().hex[:8]}",
        stripe_price_id=f"price_{uuid.uuid4().hex[:8]}",
        price_monthly=Decimal("149"),
        price_yearly=Decimal("1428"),
    )
    db.add(plan)
    await db.flush()
    return plan


@pytest_asyncio.fixture
async def affiliate(db: AsyncSession) -> Affiliate:
    user = await make_user(db, "partner@example.com", "Partner!2345")
    aff = Affiliate(
        user_id=user.id,
        name="Pat Partner",
        status=AFFILIATE_ACTIVE,
        referral_code="pat-partner",
        coupon_code="PAT20",
        commission_percent=Decimal("25"),
        discount_percent=Decimal("20"),
        discount_applies_to="yearly",
        discount_duration="once",
    )
    db.add(aff)
    await db.flush()
    await get_program(db)
    await db.commit()
    return aff


@pytest_asyncio.fixture
async def referred_org(db: AsyncSession, affiliate: Affiliate) -> Organization:
    customer = await make_user(db, "customer@example.com")
    org = await make_org(db, customer)
    await attribution.attribute_signup(db, code="pat-partner", organization_id=org.id, user_id=customer.id)
    await db.commit()
    return org


def payment(org: Organization, *, ref: str = None, period: str = "yearly", reason: str = "subscription_create",
            amount: str = "1428.00", paid_at: datetime = NOW, plan_slug: str = "growth", period_end=None):
    return commissions.Payment(
        provider="stripe",
        external_ref=ref or f"stripe:in_{uuid.uuid4().hex[:10]}",
        organization_id=org.id,
        plan_slug=plan_slug,
        billing_period=period,
        billing_reason=reason,
        base_amount=Decimal(amount),
        currency="usd",
        paid_at=paid_at,
        service_period_end=period_end or paid_at + timedelta(days=365),
    )


# ==================== Attribution ====================


async def test_signup_with_link_is_attributed(db, referred_org, affiliate):
    referral = await attribution.referral_for(db, referred_org.id)
    assert referral is not None
    assert referral.affiliate_id == affiliate.id
    assert referral.source == "link"


async def test_first_touch_wins(db, referred_org, affiliate):
    other_user = await make_user(db, "other-partner@example.com")
    other = Affiliate(user_id=other_user.id, name="Other", status=AFFILIATE_ACTIVE,
                      referral_code="other", commission_percent=Decimal("10"))
    db.add(other)
    await db.flush()
    await attribution.attribute(db, affiliate=other, organization_id=referred_org.id, user_id=None, source="coupon")
    referral = await attribution.referral_for(db, referred_org.id)
    assert referral.affiliate_id == affiliate.id


async def test_self_referral_and_existing_customer_are_refused(db, affiliate, plan):
    own_org = await make_org(db, await db.get(User, affiliate.user_id))
    await attribution.attribute_signup(db, code="pat-partner", organization_id=own_org.id, user_id=affiliate.user_id)
    assert await attribution.referral_for(db, own_org.id) is None

    payer = await make_user(db, "payer@example.com")
    paying_org = await make_org(db, payer)
    db.add(Subscription(organization_id=paying_org.id, plan_id=plan.id, status=STATUS_ACTIVE, source=SOURCE_STRIPE,
                        current_period_start=NOW, current_period_end=NOW + timedelta(days=30)))
    await db.flush()
    await attribution.attribute(db, affiliate=affiliate, organization_id=paying_org.id, user_id=payer.id, source="coupon")
    assert await attribution.referral_for(db, paying_org.id) is None


async def test_suspended_affiliate_or_disabled_program_does_not_attribute(db, affiliate):
    affiliate.status = AFFILIATE_SUSPENDED
    await db.flush()
    assert await attribution.usable_affiliate(db, "pat-partner") is None
    affiliate.status = AFFILIATE_ACTIVE
    (await get_program(db)).enabled = False
    await db.flush()
    assert await attribution.usable_affiliate(db, "PAT20") is None


# ==================== Coupons ====================


async def test_coupon_rules(db, affiliate, plan):
    user = await make_user(db, "new@example.com")
    org = await make_org(db, user)

    with pytest.raises(coupons.CouponError, match="annual"):
        await coupons.quote(db, "pat20", organization_id=org.id, user_id=user.id, billing_period="monthly")

    quote = await coupons.apply(db, " pat20 ", organization_id=org.id, user_id=user.id, billing_period="yearly")
    assert quote.code == "PAT20" and quote.percent_off == Decimal("20")
    assert quote.as_dict()["description"] == "20% off your first payment"
    referral = await attribution.referral_for(db, org.id)
    assert referral.source == "coupon" and referral.affiliate_id == affiliate.id

    with pytest.raises(coupons.CouponError, match="own"):
        await coupons.quote(db, "PAT20", organization_id=org.id, user_id=affiliate.user_id, billing_period="yearly")

    with pytest.raises(coupons.CouponError, match="isn't valid"):
        await coupons.quote(db, "NOPE", organization_id=org.id, user_id=user.id, billing_period="yearly")

    db.add(Subscription(organization_id=org.id, plan_id=plan.id, status=STATUS_ACTIVE, source=SOURCE_STRIPE,
                        current_period_start=NOW, current_period_end=NOW + timedelta(days=365)))
    await db.flush()
    with pytest.raises(coupons.CouponError, match="new customers"):
        await coupons.quote(db, "PAT20", organization_id=org.id, user_id=user.id, billing_period="yearly")


async def test_all_plans_coupon_works_on_monthly_and_trial_is_not_a_customer(db, affiliate, plan):
    affiliate.discount_applies_to = "all"
    user = await make_user(db, "trialist@example.com")
    org = await make_org(db, user)
    db.add(Subscription(organization_id=org.id, plan_id=plan.id, status=STATUS_TRIALING, source=SOURCE_TRIAL,
                        current_period_start=NOW, current_period_end=NOW + timedelta(days=14)))
    await db.flush()
    quote = await coupons.quote(db, "PAT20", organization_id=org.id, user_id=user.id, billing_period="monthly")
    assert quote.applies_to == "all"


async def test_suggested_code_comes_from_referral(db, referred_org):
    assert await coupons.suggested_code(db, referred_org.id) == "PAT20"


# ==================== Commissions ====================


async def test_annual_payment_earns_commission_on_net_amount(db, referred_org, affiliate):
    commission = await commissions.record_payment(db, payment(referred_org, amount="1142.40"))
    assert commission is not None
    assert commission.amount == Decimal("285.60")  # 25% of the discounted price
    assert commission.status == COMMISSION_PENDING
    assert commission.available_at == NOW + timedelta(days=30)
    referral = await attribution.referral_for(db, referred_org.id)
    assert referral.converted_at == NOW


async def test_annual_only_affiliate_does_not_earn_on_monthly(db, referred_org, affiliate):
    assert affiliate.commission_billing_periods == "yearly"  # the default
    assert await commissions.record_payment(db, payment(referred_org, period="monthly", amount="149")) is None


async def test_monthly_only_affiliate_earns_on_monthly_not_annual(db, referred_org, affiliate):
    affiliate.commission_billing_periods = "monthly"
    affiliate.commission_percent_monthly = Decimal("10")
    await db.flush()
    assert await commissions.record_payment(db, payment(referred_org)) is None
    monthly = await commissions.record_payment(db, payment(referred_org, period="monthly", amount="149"))
    assert monthly.amount == Decimal("14.90") and monthly.rate_percent == Decimal("10")


async def test_both_periods_use_their_own_rates(db, referred_org, affiliate):
    affiliate.commission_billing_periods = "both"
    affiliate.commission_percent_monthly = Decimal("10")
    await db.flush()
    yearly = await commissions.record_payment(db, payment(referred_org))
    monthly = await commissions.record_payment(db, payment(referred_org, period="monthly", amount="149"))
    assert yearly.amount == Decimal("357.00")  # 25% annual rate
    assert monthly.amount == Decimal("14.90")  # 10% monthly rate

    affiliate.commission_percent_monthly = None  # blank: same as the annual rate
    await db.flush()
    again = await commissions.record_payment(
        db, payment(referred_org, period="monthly", reason="subscription_cycle", amount="149")
    )
    assert again.amount == Decimal("37.25")


async def test_monthly_and_annual_limits_are_counted_separately(db, referred_org, affiliate):
    affiliate.commission_billing_periods = "both"
    affiliate.custom_max_payments = True
    affiliate.max_commission_payments = 1
    affiliate.max_monthly_commission_payments = 2
    await db.flush()
    month = lambda n: payment(referred_org, period="monthly", amount="149",
                              reason="subscription_create" if n == 0 else "subscription_cycle",
                              paid_at=NOW + timedelta(days=30 * n), period_end=NOW + timedelta(days=30 * (n + 1)))
    assert await commissions.record_payment(db, month(0)) is not None
    assert await commissions.record_payment(db, month(1)) is not None
    assert await commissions.record_payment(db, month(2)) is None  # monthly limit of 2 reached
    # The annual allowance is untouched by the monthly payments.
    assert await commissions.record_payment(db, payment(referred_org, paid_at=NOW + timedelta(days=90))) is not None


async def test_same_payment_twice_earns_once(db, referred_org):
    first = await commissions.record_payment(db, payment(referred_org, ref="stripe:in_same"))
    second = await commissions.record_payment(db, payment(referred_org, ref="stripe:in_same"))
    assert first.id == second.id
    count = len((await db.execute(select(AffiliateCommission))).scalars().all())
    assert count == 1


async def test_ineligible_plan_and_unreferred_org_do_not_earn(db, referred_org, affiliate):
    (await get_program(db)).eligible_plan_slugs = ["scale"]
    await db.flush()
    assert await commissions.record_payment(db, payment(referred_org)) is None

    stranger = await make_org(db, await make_user(db, "stranger@example.com"))
    assert await commissions.record_payment(db, payment(stranger)) is None


async def test_renewals_follow_the_payment_limit(db, referred_org, affiliate):
    assert await commissions.record_payment(db, payment(referred_org)) is not None
    renewal = payment(referred_org, reason="subscription_cycle", paid_at=NOW + timedelta(days=365))
    assert await commissions.record_payment(db, renewal) is None  # program default: first payment only

    affiliate.custom_max_payments = True
    affiliate.max_commission_payments = None  # every renewal
    await db.flush()
    assert await commissions.record_payment(db, renewal) is not None


async def test_referral_window(db, referred_org):
    late = payment(referred_org, paid_at=datetime.utcnow() + timedelta(days=400))
    assert await commissions.record_payment(db, late) is None


async def test_upgrade_proration_only_inside_a_commissioned_year(db, referred_org):
    upgrade = payment(referred_org, reason="subscription_update", amount="300", paid_at=NOW + timedelta(days=100))
    assert await commissions.record_payment(db, upgrade) is None
    await commissions.record_payment(db, payment(referred_org))
    upgrade.external_ref = "stripe:in_upgrade"
    assert (await commissions.record_payment(db, upgrade)).amount == Decimal("75.00")


async def test_suspended_affiliate_stops_earning(db, referred_org, affiliate):
    affiliate.status = AFFILIATE_SUSPENDED
    await db.flush()
    assert await commissions.record_payment(db, payment(referred_org)) is None


# ==================== Refunds and maturing ====================


async def test_refund_before_payout_shrinks_then_reverses(db, referred_org):
    c = await commissions.record_payment(db, payment(referred_org, ref="stripe:in_r"))
    await commissions.apply_refund(db, "stripe:in_r", Decimal("0.5"))
    assert c.amount == Decimal("178.50") and c.status == COMMISSION_PENDING
    await commissions.apply_refund(db, "stripe:in_r", Decimal("0.5"))  # re-delivered: no change
    assert c.amount == Decimal("178.50")
    await commissions.apply_refund(db, "stripe:in_r", Decimal("1"))
    assert c.amount == Decimal("0.00") and c.status == COMMISSION_REVERSED


async def test_refund_after_payout_adds_a_clawback(db, referred_org, affiliate):
    c = await commissions.record_payment(db, payment(referred_org, ref="stripe:in_p"))
    c.status = COMMISSION_PAID
    await db.flush()
    await commissions.apply_refund(db, "stripe:in_p", Decimal("1"))
    await commissions.apply_refund(db, "stripe:in_p", Decimal("1"))
    clawbacks = (
        await db.execute(select(AffiliateCommission).where(AffiliateCommission.kind == KIND_CLAWBACK))
    ).scalars().all()
    assert len(clawbacks) == 1
    assert clawbacks[0].amount == Decimal("-357.00")
    assert clawbacks[0].status == COMMISSION_APPROVED


async def test_mature_moves_commissions_past_their_hold(db, referred_org):
    c = await commissions.record_payment(db, payment(referred_org))
    assert await commissions.mature(db, now=NOW + timedelta(days=29)) == 0
    assert await commissions.mature(db, now=NOW + timedelta(days=31)) == 1
    await db.refresh(c)
    assert c.status == COMMISSION_APPROVED


# ==================== Payouts ====================


async def _approved(db, org, amount="1428.00"):
    c = await commissions.record_payment(db, payment(org, amount=amount))
    c.status = COMMISSION_APPROVED
    await db.commit()
    return c


async def test_manual_payout_pays_the_approved_balance(db, referred_org, affiliate):
    await _approved(db, referred_org)
    payout = await payouts.create_payout(db, affiliate.id, method="manual", actor_id=None, reference="WIRE-1")
    assert payout.status == PAYOUT_PAID and payout.amount == Decimal("357.00")
    rows = (await db.execute(select(AffiliateCommission))).scalars().all()
    assert all(r.status == COMMISSION_PAID and r.payout_id == payout.id for r in rows)
    with pytest.raises(payouts.PayoutError, match="nothing approved"):
        await payouts.create_payout(db, affiliate.id, method="manual", actor_id=None, reference="WIRE-2")


async def test_payout_minimum(db, referred_org, affiliate):
    await _approved(db, referred_org, amount="100")  # $25 commission, minimum is $50
    with pytest.raises(payouts.PayoutError, match="below the minimum"):
        await payouts.create_payout(db, affiliate.id, method="manual", actor_id=None, reference="x")
    payout = await payouts.create_payout(
        db, affiliate.id, method="manual", actor_id=None, reference="x", ignore_minimum=True
    )
    assert payout.amount == Decimal("25.00")


class _FakeStripe:
    """Just enough of the stripe module for payouts: a transfer that succeeds or fails."""

    class error:
        class StripeError(Exception):
            def __init__(self, message="", code=None):
                super().__init__(message)
                self.code = code
                self.user_message = message

    def __init__(self, fail_code=None):
        self.fail_code = fail_code
        self.transfers = []
        fake = self

        class Transfer:
            @staticmethod
            def create(**kwargs):
                if fake.fail_code:
                    raise fake.error.StripeError("Insufficient funds", code=fake.fail_code)
                fake.transfers.append(kwargs)
                return SimpleNamespace(id="tr_123")

        class Account:
            @staticmethod
            def retrieve(account_id=None):
                return {"details_submitted": True, "payouts_enabled": True,
                        "capabilities": {"transfers": "active"}, "country": "US"}

        self.Transfer = Transfer
        self.Account = Account


@pytest.fixture
def connected(monkeypatch, affiliate):
    affiliate.stripe_account_id = "acct_123"
    monkeypatch.setattr(payouts, "connect_ready", lambda: True)


async def test_stripe_payout_sends_one_idempotent_transfer(db, referred_org, affiliate, connected, monkeypatch):
    fake = _FakeStripe()
    monkeypatch.setattr(payouts, "_stripe", lambda: fake)
    await _approved(db, referred_org)
    payout = await payouts.create_payout(db, affiliate.id, method="stripe", actor_id=None)
    assert payout.status == PAYOUT_PAID and payout.stripe_transfer_id == "tr_123"
    assert fake.transfers[0]["amount"] == 35700
    assert fake.transfers[0]["destination"] == "acct_123"
    assert fake.transfers[0]["idempotency_key"] == f"affiliate-payout:{payout.id}"


async def test_failed_transfer_returns_commissions_to_the_pool(db, referred_org, affiliate, connected, monkeypatch):
    monkeypatch.setattr(payouts, "_stripe", lambda: _FakeStripe(fail_code="balance_insufficient"))
    c = await _approved(db, referred_org)
    payout = await payouts.create_payout(db, affiliate.id, method="stripe", actor_id=None)
    assert payout.status == PAYOUT_FAILED
    assert "balance is too low" in payout.failure_reason
    await db.refresh(c)
    assert c.status == COMMISSION_APPROVED and c.payout_id is None


# ==================== Webhooks ====================


async def test_stripe_invoice_paid_records_commission(db, referred_org, plan, monkeypatch):
    from app.services.billing.stripe_service import StripeService

    sub = Subscription(organization_id=referred_org.id, plan_id=plan.id, status=STATUS_ACTIVE, source=SOURCE_STRIPE,
                       billing_period="yearly", stripe_subscription_id="sub_1",
                       current_period_start=NOW, current_period_end=NOW + timedelta(days=365))
    db.add(sub)
    await db.commit()

    service = StripeService(api_key="", webhook_secret="", configure_sdk=False)

    async def no_sync(db, invoice_id):
        return None

    monkeypatch.setattr(service, "sync_invoice", no_sync)
    invoice = {
        "id": "in_web", "subscription": "sub_1", "billing_reason": "subscription_create", "status": "paid",
        "amount_paid": 114240, "total_excluding_tax": 114240, "currency": "usd",
        "status_transitions": {"paid_at": int(NOW.timestamp())},
        "lines": {"data": [{"period": {"start": int(NOW.timestamp()),
                                       "end": int((NOW + timedelta(days=365)).timestamp())}}]},
    }
    assert await service.handle_webhook_event(db, {"type": "invoice.paid", "data": {"object": invoice}})
    row = await db.scalar(select(AffiliateCommission).where(AffiliateCommission.external_ref == "stripe:in_web"))
    assert row is not None and row.amount == Decimal("285.60")

    refund = {"invoice": "in_web", "amount": 114240, "amount_refunded": 114240}
    assert await service.handle_webhook_event(db, {"type": "charge.refunded", "data": {"object": refund}})
    await db.refresh(row)
    assert row.status == COMMISSION_REVERSED


async def test_polar_order_paid_records_commission(db, referred_org, plan):
    from app.services.billing import polar_service

    plan.polar_product_id_yearly = "prod_polar_yearly"
    db.add(Subscription(organization_id=referred_org.id, plan_id=plan.id, status=STATUS_ACTIVE, source="polar",
                        billing_period="yearly", polar_subscription_id="psub_1",
                        current_period_start=NOW, current_period_end=NOW + timedelta(days=365)))
    await db.commit()
    order = {
        "id": "order_1", "subscription_id": "psub_1", "product_id": "prod_polar_yearly",
        "billing_reason": "subscription_create", "net_amount": 114240, "tax_amount": 0, "total_amount": 114240,
        "currency": "usd", "created_at": NOW.isoformat(), "subscription": {},
    }
    await polar_service.handle_webhook_event(db, "wh_1", {"type": "order.paid", "data": order})
    row = await db.scalar(select(AffiliateCommission).where(AffiliateCommission.external_ref == "polar:order_1"))
    assert row is not None and row.amount == Decimal("285.60") and row.billing_period == "yearly"


# ==================== Session scope ====================


@pytest_asyncio.fixture
async def http(engine):
    from app.main import app

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


def _bearer(user: User, scope: str) -> dict:
    token = create_access_token(subject=str(user.id), token_version=user.token_version, scope=scope)
    return {"Authorization": f"Bearer {token}"}


async def test_affiliate_session_is_its_own_front_door(http, db, affiliate):
    user = await db.get(User, affiliate.user_id)
    app_headers = _bearer(user, SCOPE_APP)
    aff_headers = _bearer(user, SCOPE_AFFILIATE)

    assert (await http.get("/api/v1/affiliate/me", headers=aff_headers)).status_code == 200
    assert (await http.get("/api/v1/affiliate/me", headers=app_headers)).status_code == 403
    assert (await http.get("/api/v1/users/me", headers=aff_headers)).status_code == 403
    assert (await http.get("/api/v1/admin/overview", headers=aff_headers)).status_code == 403


async def test_affiliate_login_refuses_non_affiliates(http, db, affiliate):
    await make_user(db, "plain@example.com", "Plain!2345")
    await db.commit()
    ok = await http.post("/api/v1/auth/affiliate/login", json={"email": "partner@example.com", "password": "Partner!2345"})
    assert ok.status_code == 200
    refused = await http.post("/api/v1/auth/affiliate/login", json={"email": "plain@example.com", "password": "Plain!2345"})
    assert refused.status_code == 401


async def test_click_endpoint(http, affiliate):
    res = await http.post("/api/v1/affiliate-public/click", json={"code": "pat-partner", "landing_path": "/"})
    assert res.json() == {"valid": True, "cookie_days": 60, "kind": "referral"}
    res = await http.post("/api/v1/affiliate-public/click", json={"code": "nobody"})
    assert res.json()["valid"] is False


async def test_generated_coupon_codes_are_valid_and_free(db, affiliate):
    assert await unique_coupon_code(db, "jane-doe") == "JANEDOE"
    short = await unique_coupon_code(db, "a-b")
    assert len(short) >= 3 and short.startswith("AB")
    # PAT20 is taken, and so is anything equal to an existing referral code.
    taken = await unique_coupon_code(db, "pat20")
    assert taken != "PAT20"


async def test_invite_link_sets_password_and_works_once(http, db, affiliate):
    user = await db.get(User, affiliate.user_id)
    user.hashed_password = None
    await db.commit()
    await db.refresh(affiliate, ["user"])
    token = invite_token(affiliate)

    info = await http.get("/api/v1/auth/affiliate/invite", params={"token": token})
    assert info.json()["needs_password"] is True
    missing = await http.post("/api/v1/auth/affiliate/accept-invite", json={"token": token})
    assert missing.status_code == 400
    accepted = await http.post(
        "/api/v1/auth/affiliate/accept-invite", json={"token": token, "password": "Brand-New!Pass9"}
    )
    assert accepted.status_code == 200
    headers = {"Authorization": f"Bearer {accepted.json()['access_token']}"}
    assert (await http.get("/api/v1/affiliate/me", headers=headers)).status_code == 200

    again = await http.post(
        "/api/v1/auth/affiliate/accept-invite", json={"token": token, "password": "Other-New!Pass9"}
    )
    assert again.status_code == 400


async def test_payout_includes_monthly_and_annual_commissions(db, referred_org, affiliate):
    affiliate.commission_billing_periods = "both"
    affiliate.commission_percent_monthly = Decimal("10")
    await db.flush()
    for p in (payment(referred_org), payment(referred_org, period="monthly", amount="149")):
        c = await commissions.record_payment(db, p)
        c.status = COMMISSION_APPROVED
    await db.commit()
    payout = await payouts.create_payout(db, affiliate.id, method="manual", actor_id=None, reference="WIRE-3")
    assert payout.amount == Decimal("371.90")  # 357.00 annual + 14.90 monthly
    assert payout.commission_count == 2
