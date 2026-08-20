"""
Monthly vs yearly: the interval charged, and the dates written on the row.

The onboarding pricing toggle is the only thing standing between "renews in a
month" and "renews in a year". These tests pin the whole path: the interval
sent to Stripe, the amount, and the period start/end persisted afterwards.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.billing import (
    CheckoutRequest,
    StartTrialRequest,
    apply_paid_conversion,
)
from app.models.subscription import (
    SOURCE_STRIPE,
    SOURCE_TRIAL,
    STATUS_ACTIVE,
    STATUS_TRIALING,
    Subscription,
    SubscriptionPlan,
)
from app.services.billing.stripe_service import StripeService


@pytest.fixture
def stripe_service():
    return StripeService(api_key="sk_test_123", webhook_secret="whsec_test_123")


@pytest.fixture
def plan():
    return SubscriptionPlan(
        id=uuid.uuid4(),
        slug="voice-ai",
        name="Voice AI",
        stripe_product_id="prod_test",
        stripe_price_id="price_monthly_test",
        price_monthly=Decimal("359.00"),
        price_yearly=Decimal("3231.00"),
        currency="usd",
    )


class _RecordingStripe:
    """Captures what would have been sent to Stripe.Price.create."""

    def __init__(self):
        self.created = None

    def list(self, **kwargs):
        return type("Prices", (), {"data": []})()

    def create(self, **kwargs):
        self.created = kwargs
        return type("Price", (), {"id": "price_new_test"})()


@pytest.mark.unit
@pytest.mark.billing
class TestPriceInterval:
    """What ``ensure_stripe_price`` actually asks Stripe to charge."""

    @pytest.mark.parametrize(
        "billing_period,expected_interval,expected_cents",
        [
            ("monthly", "month", 35900),
            ("yearly", "year", 323100),
        ],
    )
    async def test_interval_and_amount_follow_the_toggle(
        self,
        db_session,
        stripe_service,
        plan,
        monkeypatch,
        billing_period,
        expected_interval,
        expected_cents,
    ):
        recorder = _RecordingStripe()
        monkeypatch.setattr("stripe.Price.list", recorder.list)
        monkeypatch.setattr("stripe.Price.create", recorder.create)

        await stripe_service.ensure_stripe_price(
            db=db_session, plan=plan, billing_period=billing_period
        )

        assert recorder.created["recurring"] == {"interval": expected_interval}
        assert recorder.created["unit_amount"] == expected_cents

    async def test_yearly_without_a_yearly_price_is_refused(
        self, db_session, stripe_service, plan, monkeypatch
    ):
        """
        A plan with no yearly price must not fall back to the monthly amount.

        That fallback bills $359 for a *whole year* against a pricing page that
        promised $3,231 — the customer is undercharged by 11 months and the
        yearly price shown was a lie. Refusing is the only safe answer.
        """
        recorder = _RecordingStripe()
        monkeypatch.setattr("stripe.Price.list", recorder.list)
        monkeypatch.setattr("stripe.Price.create", recorder.create)
        plan.price_yearly = None

        with pytest.raises(Exception) as exc:
            await stripe_service.ensure_stripe_price(
                db=db_session, plan=plan, billing_period="yearly"
            )

        assert recorder.created is None, "nothing may be charged"
        assert "yearly" in str(exc.value).lower()


@pytest.mark.unit
@pytest.mark.billing
class TestBillingPeriodIsValidated:
    """
    An unrecognised interval must be refused, not quietly billed monthly.

    ``"year"``, ``"annual"`` or ``"Yearly"`` used to fall through the
    ``== "yearly"`` check to a *monthly* Stripe price, while the row stored the
    string verbatim — so the account read back "Yearly" and renewed in 30 days.
    """

    @pytest.mark.parametrize("value", ["monthly", "yearly"])
    def test_the_two_real_intervals_are_accepted(self, value):
        assert (
            CheckoutRequest(
                plan_id=uuid.uuid4(), payment_method_id="pm_test", billing_period=value
            ).billing_period
            == value
        )
        assert StartTrialRequest(billing_period=value).billing_period == value

    @pytest.mark.parametrize("value", ["year", "annual", "Yearly", "yearly ", "", "月"])
    def test_anything_else_is_refused(self, value):
        with pytest.raises(ValidationError):
            CheckoutRequest(
                plan_id=uuid.uuid4(), payment_method_id="pm_test", billing_period=value
            )
        with pytest.raises(ValidationError):
            StartTrialRequest(billing_period=value)

    def test_monthly_is_the_default(self):
        assert (
            CheckoutRequest(
                plan_id=uuid.uuid4(), payment_method_id="pm_test"
            ).billing_period
            == "monthly"
        )


@pytest.mark.unit
@pytest.mark.billing
class TestPeriodDatesOnConversion:
    """The start/end dates written when a trial converts to a paid plan."""

    def _trial(self, plan, now):
        return Subscription(
            organization_id=uuid.uuid4(),
            plan_id=plan.id,
            status=STATUS_TRIALING,
            source=SOURCE_TRIAL,
            billing_period="monthly",
            current_period_start=now - timedelta(days=3),
            current_period_end=now + timedelta(days=27),
            trial_start=now - timedelta(days=3),
            trial_end=now + timedelta(days=27),
        )

    @pytest.mark.parametrize(
        "billing_period,span",
        [("monthly", timedelta(days=30)), ("yearly", timedelta(days=365))],
    )
    def test_the_paid_period_replaces_the_trial_period(self, plan, billing_period, span):
        now = datetime(2026, 8, 20, 12, 0, 0)
        subscription = self._trial(plan, now)
        period_start, period_end = now, now + span

        converted = apply_paid_conversion(
            subscription,
            plan,
            stripe_subscription_id="sub_test",
            stripe_customer_id="cus_test",
            stripe_status=STATUS_ACTIVE,
            billing_period=billing_period,
            period_start=period_start,
            period_end=period_end,
            now=now,
        )

        assert converted is True
        assert subscription.billing_period == billing_period
        assert subscription.current_period_start == period_start
        assert subscription.current_period_end == period_end
        assert subscription.current_period_end - subscription.current_period_start == span
        assert subscription.source == SOURCE_STRIPE
        assert subscription.status == STATUS_ACTIVE
        # The trial must not run on past the moment it was paid for.
        assert subscription.trial_end == now
        assert subscription.trial_converted_at == now


@pytest.mark.unit
@pytest.mark.billing
class TestStripeTimestampsAreUtc:
    """
    Stripe sends epoch seconds; the columns hold naive UTC.

    ``datetime.fromtimestamp(x)`` reads that epoch in the *server's* local zone,
    so on any host not set to UTC every period start/end lands hours out of step
    with the ``datetime.utcnow()`` the rest of the billing code compares it to.
    """

    def test_conversion_ignores_the_host_timezone(self, monkeypatch):
        from app.services.billing.stripe_service import utc_from_timestamp

        # 2026-08-20 12:00:00 UTC
        epoch = int(datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc).timestamp())
        converted = utc_from_timestamp(epoch)

        assert converted == datetime(2026, 8, 20, 12, 0)
        assert converted.tzinfo is None, "columns are naive"

    def test_none_passes_through(self):
        from app.services.billing.stripe_service import utc_from_timestamp

        assert utc_from_timestamp(None) is None
