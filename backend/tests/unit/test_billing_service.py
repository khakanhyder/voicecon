"""
Unit tests for billing service.
"""

import pytest
from decimal import Decimal
from datetime import datetime
import uuid

from app.services.billing.stripe_service import StripeService
from app.services.billing.usage_tracker import UsageTracker
from app.models.subscription import SubscriptionPlan, Subscription, UsageRecord
from app.models.call import Call


@pytest.mark.unit
@pytest.mark.billing
class TestStripeService:
    """Test Stripe service functionality."""

    @pytest.fixture
    def stripe_service(self):
        """Create Stripe service instance."""
        return StripeService(
            api_key="sk_test_123",
            webhook_secret="whsec_test_123"
        )

    async def test_create_subscription_plan(self, db_session, stripe_service, monkeypatch):
        """Test creating a subscription plan."""
        # Mock Stripe API calls
        mock_product = type('obj', (object,), {'id': 'prod_test_123'})()
        mock_price = type('obj', (object,), {'id': 'price_test_123'})()

        monkeypatch.setattr('stripe.Product.create', lambda **kwargs: mock_product)
        monkeypatch.setattr('stripe.Price.create', lambda **kwargs: mock_price)

        # Create plan
        plan = await stripe_service.create_subscription_plan(
            db=db_session,
            name="Professional",
            description="For growing businesses",
            price_monthly=Decimal("99.00"),
            included_minutes=5000,
            included_calls=500,
            max_agents=5,
            max_phone_numbers=5,
            max_knowledge_bases=10,
        )

        assert plan.name == "Professional"
        assert plan.price_monthly == Decimal("99.00")
        assert plan.included_minutes == 5000
        assert plan.stripe_product_id == "prod_test_123"
        assert plan.stripe_price_id == "price_test_123"

    async def test_create_customer(self, stripe_service, monkeypatch):
        """Test creating a Stripe customer."""
        mock_customer = type('obj', (object,), {'id': 'cus_test_123'})()
        monkeypatch.setattr('stripe.Customer.create', lambda **kwargs: mock_customer)

        customer_id = await stripe_service.create_customer(
            email="test@example.com",
            name="Test User",
            organization_id=uuid.uuid4()
        )

        assert customer_id == "cus_test_123"

    async def test_get_current_usage(self, db_session, stripe_service, test_organization):
        """Test getting current usage for a subscription."""
        # Create plan
        plan = SubscriptionPlan(
            name="Test Plan",
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
            price_monthly=Decimal("99.00"),
            included_minutes=1000,
            included_calls=100,
            max_agents=1,
            max_phone_numbers=1,
            max_knowledge_bases=1,
        )
        db_session.add(plan)
        await db_session.flush()

        # Create subscription
        subscription = Subscription(
            organization_id=test_organization.id,
            plan_id=plan.id,
            stripe_subscription_id="sub_test",
            stripe_customer_id="cus_test",
            status="active",
            billing_period="monthly",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow(),
            current_period_minutes=750,
            current_period_calls=60,
        )
        db_session.add(subscription)
        await db_session.commit()

        # Get usage
        usage = await stripe_service.get_current_usage(
            db=db_session,
            subscription_id=subscription.id
        )

        assert usage["minutes_used"] == 750
        assert usage["minutes_included"] == 1000
        assert usage["minutes_overage"] == 0
        assert usage["calls_used"] == 60
        assert usage["calls_included"] == 100
        assert usage["calls_overage"] == 0

    async def test_get_current_usage_with_overage(
        self, db_session, stripe_service, test_organization
    ):
        """Test getting usage when limits are exceeded."""
        # Create plan
        plan = SubscriptionPlan(
            name="Test Plan",
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
            price_monthly=Decimal("99.00"),
            included_minutes=1000,
            included_calls=100,
            max_agents=1,
            max_phone_numbers=1,
            max_knowledge_bases=1,
        )
        db_session.add(plan)
        await db_session.flush()

        # Create subscription with overage
        subscription = Subscription(
            organization_id=test_organization.id,
            plan_id=plan.id,
            stripe_subscription_id="sub_test",
            stripe_customer_id="cus_test",
            status="active",
            billing_period="monthly",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow(),
            current_period_minutes=1250,  # 250 over
            current_period_calls=120,  # 20 over
        )
        db_session.add(subscription)
        await db_session.commit()

        # Get usage
        usage = await stripe_service.get_current_usage(
            db=db_session,
            subscription_id=subscription.id
        )

        assert usage["minutes_overage"] == 250
        assert usage["calls_overage"] == 20


@pytest.mark.unit
@pytest.mark.billing
class TestUsageTracker:
    """Test usage tracking functionality."""

    async def test_record_call_usage(
        self, db_session, test_organization, test_agent
    ):
        """Test recording call usage."""
        # Create plan
        plan = SubscriptionPlan(
            name="Test Plan",
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
            price_monthly=Decimal("99.00"),
            included_minutes=1000,
            included_calls=100,
            max_agents=1,
            max_phone_numbers=1,
            max_knowledge_bases=1,
            overage_rate_per_minute=Decimal("0.015"),
            overage_rate_per_call=Decimal("0.05"),
        )
        db_session.add(plan)
        await db_session.flush()

        # Create subscription
        subscription = Subscription(
            organization_id=test_organization.id,
            plan_id=plan.id,
            stripe_subscription_id="sub_test",
            stripe_customer_id="cus_test",
            status="active",
            billing_period="monthly",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow(),
            current_period_minutes=0,
            current_period_calls=0,
        )
        db_session.add(subscription)
        await db_session.flush()

        # Create call
        call = Call(
            organization_id=test_organization.id,
            agent_id=test_agent.id,
            from_number="+15551234567",
            to_number="+15559876543",
            direction="inbound",
            status="completed",
            duration=180,  # 3 minutes = 180 seconds
        )
        db_session.add(call)
        await db_session.commit()

        # Record usage
        usage_record = await UsageTracker.record_call_usage(
            db=db_session,
            call_id=call.id,
            organization_id=test_organization.id
        )

        assert usage_record is not None
        assert usage_record.usage_type == "calls"
        assert usage_record.quantity == 1

        # Verify subscription was updated
        await db_session.refresh(subscription)
        assert subscription.current_period_minutes == 3  # ceil(180/60)
        assert subscription.current_period_calls == 1

    async def test_record_call_usage_with_overage(
        self, db_session, test_organization, test_agent
    ):
        """Test recording usage that exceeds limits."""
        # Create plan with low limits
        plan = SubscriptionPlan(
            name="Test Plan",
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
            price_monthly=Decimal("29.00"),
            included_minutes=10,
            included_calls=5,
            max_agents=1,
            max_phone_numbers=1,
            max_knowledge_bases=1,
            overage_rate_per_minute=Decimal("0.015"),
            overage_rate_per_call=Decimal("0.05"),
        )
        db_session.add(plan)
        await db_session.flush()

        # Create subscription already at limits
        subscription = Subscription(
            organization_id=test_organization.id,
            plan_id=plan.id,
            stripe_subscription_id="sub_test",
            stripe_customer_id="cus_test",
            status="active",
            billing_period="monthly",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow(),
            current_period_minutes=10,  # At limit
            current_period_calls=5,  # At limit
        )
        db_session.add(subscription)
        await db_session.flush()

        # Create call that will cause overage
        call = Call(
            organization_id=test_organization.id,
            agent_id=test_agent.id,
            from_number="+15551234567",
            to_number="+15559876543",
            direction="inbound",
            status="completed",
            duration=120,  # 2 minutes
        )
        db_session.add(call)
        await db_session.commit()

        # Record usage
        await UsageTracker.record_call_usage(
            db=db_session,
            call_id=call.id,
            organization_id=test_organization.id
        )

        # Verify subscription was updated
        await db_session.refresh(subscription)
        assert subscription.current_period_minutes == 12  # 10 + 2
        assert subscription.current_period_calls == 6  # 5 + 1

        # Verify usage record has overage charge
        from sqlalchemy import select
        result = await db_session.execute(
            select(UsageRecord).where(
                UsageRecord.subscription_id == subscription.id,
                UsageRecord.usage_type == "minutes"
            )
        )
        minutes_record = result.scalar_one()

        # Should charge for 2 minutes overage
        assert minutes_record.total_amount == Decimal("0.015") * 2

    async def test_check_usage_limit(self, db_session, test_organization):
        """Test checking usage limits."""
        # No subscription
        status = await UsageTracker.check_usage_limit(
            db=db_session,
            organization_id=test_organization.id,
            usage_type="minutes"
        )

        assert status["has_subscription"] is False
        assert status["within_limit"] is False

    async def test_record_sms_usage(self, db_session, test_organization):
        """Test recording SMS usage."""
        # Create plan
        plan = SubscriptionPlan(
            name="Test Plan",
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
            price_monthly=Decimal("99.00"),
            included_minutes=1000,
            included_calls=100,
            max_agents=1,
            max_phone_numbers=1,
            max_knowledge_bases=1,
        )
        db_session.add(plan)
        await db_session.flush()

        # Create subscription
        subscription = Subscription(
            organization_id=test_organization.id,
            plan_id=plan.id,
            stripe_subscription_id="sub_test",
            stripe_customer_id="cus_test",
            status="active",
            billing_period="monthly",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow(),
        )
        db_session.add(subscription)
        await db_session.commit()

        # Record SMS usage
        usage_record = await UsageTracker.record_sms_usage(
            db=db_session,
            organization_id=test_organization.id,
            sms_count=5
        )

        assert usage_record is not None
        assert usage_record.usage_type == "sms"
        assert usage_record.quantity == 5
        assert usage_record.unit_price == 0.0075
        assert usage_record.total_amount == Decimal("0.0375")  # 5 * 0.0075
