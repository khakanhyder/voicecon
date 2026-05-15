"""
Integration tests for billing API endpoints.
"""

import pytest
from decimal import Decimal
from datetime import datetime


@pytest.mark.integration
@pytest.mark.billing
class TestBillingAPI:
    """Test billing API endpoints."""

    async def test_list_subscription_plans(self, auth_client, db_session, assert_response_success):
        """Test listing subscription plans."""
        # Create test plans
        from app.models.subscription import SubscriptionPlan

        plans_data = [
            {
                "name": "Starter",
                "stripe_product_id": "prod_starter",
                "stripe_price_id": "price_starter",
                "price_monthly": Decimal("29.00"),
                "included_minutes": 1000,
                "included_calls": 100,
                "max_agents": 1,
                "max_phone_numbers": 1,
                "max_knowledge_bases": 1,
                "is_public": True,
                "is_active": True,
            },
            {
                "name": "Professional",
                "stripe_product_id": "prod_pro",
                "stripe_price_id": "price_pro",
                "price_monthly": Decimal("99.00"),
                "included_minutes": 5000,
                "included_calls": 500,
                "max_agents": 5,
                "max_phone_numbers": 5,
                "max_knowledge_bases": 10,
                "is_public": True,
                "is_active": True,
            },
        ]

        for plan_data in plans_data:
            plan = SubscriptionPlan(**plan_data)
            db_session.add(plan)

        await db_session.commit()

        # Test API
        response = auth_client.get("/api/v1/billing/plans")
        data = assert_response_success(response)

        assert len(data) == 2
        assert data[0]["name"] == "Starter"
        assert data[0]["price_monthly"] == 29.0
        assert data[1]["name"] == "Professional"
        assert data[1]["price_monthly"] == 99.0

    async def test_get_current_subscription(
        self, auth_client, db_session, test_organization, assert_response_success
    ):
        """Test getting current subscription."""
        from app.models.subscription import SubscriptionPlan, Subscription

        # Create plan
        plan = SubscriptionPlan(
            name="Professional",
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
            price_monthly=Decimal("99.00"),
            included_minutes=5000,
            included_calls=500,
            max_agents=5,
            max_phone_numbers=5,
            max_knowledge_bases=10,
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
            current_period_minutes=2500,
            current_period_calls=250,
        )
        db_session.add(subscription)
        await db_session.commit()

        # Test API
        response = auth_client.get("/api/v1/billing/subscription")
        data = assert_response_success(response)

        assert data["plan_name"] == "Professional"
        assert data["status"] == "active"
        assert data["current_period_minutes"] == 2500
        assert data["current_period_calls"] == 250

    async def test_get_current_subscription_none(
        self, auth_client, assert_response_success
    ):
        """Test getting subscription when none exists."""
        response = auth_client.get("/api/v1/billing/subscription")
        data = assert_response_success(response)

        assert data is None

    async def test_get_current_usage(
        self, auth_client, db_session, test_organization, assert_response_success
    ):
        """Test getting current usage."""
        from app.models.subscription import SubscriptionPlan, Subscription

        # Create plan and subscription
        plan = SubscriptionPlan(
            name="Professional",
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
            price_monthly=Decimal("99.00"),
            included_minutes=5000,
            included_calls=500,
            max_agents=5,
            max_phone_numbers=5,
            max_knowledge_bases=10,
            overage_rate_per_minute=Decimal("0.012"),
            overage_rate_per_call=Decimal("0.04"),
        )
        db_session.add(plan)
        await db_session.flush()

        subscription = Subscription(
            organization_id=test_organization.id,
            plan_id=plan.id,
            stripe_subscription_id="sub_test",
            stripe_customer_id="cus_test",
            status="active",
            billing_period="monthly",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow(),
            current_period_minutes=3245,
            current_period_calls=289,
        )
        db_session.add(subscription)
        await db_session.commit()

        # Test API
        response = auth_client.get("/api/v1/billing/usage")
        data = assert_response_success(response)

        assert data["minutes_used"] == 3245
        assert data["minutes_included"] == 5000
        assert data["minutes_overage"] == 0
        assert data["calls_used"] == 289
        assert data["calls_included"] == 500
        assert data["calls_overage"] == 0
        assert data["estimated_overage_cost"] == 0.0

    async def test_get_usage_with_overage(
        self, auth_client, db_session, test_organization, assert_response_success
    ):
        """Test getting usage with overage charges."""
        from app.models.subscription import SubscriptionPlan, Subscription

        # Create plan and subscription with overage
        plan = SubscriptionPlan(
            name="Starter",
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
            price_monthly=Decimal("29.00"),
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
            current_period_calls=125,  # 25 over
        )
        db_session.add(subscription)
        await db_session.commit()

        # Test API
        response = auth_client.get("/api/v1/billing/usage")
        data = assert_response_success(response)

        assert data["minutes_overage"] == 250
        assert data["calls_overage"] == 25
        # 250 * 0.015 + 25 * 0.05 = 3.75 + 1.25 = 5.00
        assert data["estimated_overage_cost"] == 5.0

    async def test_check_usage_limits(
        self, auth_client, db_session, test_organization, assert_response_success
    ):
        """Test checking usage limits."""
        from app.models.subscription import SubscriptionPlan, Subscription

        # Create plan and subscription
        plan = SubscriptionPlan(
            name="Starter",
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
            price_monthly=Decimal("29.00"),
            included_minutes=1000,
            included_calls=100,
            max_agents=1,
            max_phone_numbers=1,
            max_knowledge_bases=1,
        )
        db_session.add(plan)
        await db_session.flush()

        subscription = Subscription(
            organization_id=test_organization.id,
            plan_id=plan.id,
            stripe_subscription_id="sub_test",
            stripe_customer_id="cus_test",
            status="active",
            billing_period="monthly",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow(),
            current_period_minutes=950,  # Within limit
            current_period_calls=98,  # Within limit
        )
        db_session.add(subscription)
        await db_session.commit()

        # Test API
        response = auth_client.get("/api/v1/billing/usage/limits")
        data = assert_response_success(response)

        assert data["has_active_subscription"] is True
        assert data["within_limits"] is True
        assert data["minutes_limit_reached"] is False
        assert data["calls_limit_reached"] is False

    async def test_list_invoices(
        self, auth_client, db_session, test_organization, assert_response_success
    ):
        """Test listing invoices."""
        from app.models.subscription import SubscriptionPlan, Subscription, Invoice

        # Create plan and subscription
        plan = SubscriptionPlan(
            name="Professional",
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
            price_monthly=Decimal("99.00"),
            included_minutes=5000,
            included_calls=500,
            max_agents=5,
            max_phone_numbers=5,
            max_knowledge_bases=10,
        )
        db_session.add(plan)
        await db_session.flush()

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
        await db_session.flush()

        # Create invoices
        invoices_data = [
            {
                "subscription_id": subscription.id,
                "organization_id": test_organization.id,
                "stripe_invoice_id": "in_test_1",
                "stripe_customer_id": "cus_test",
                "invoice_number": "INV-2024-001",
                "status": "paid",
                "amount_due": Decimal("99.00"),
                "amount_paid": Decimal("99.00"),
                "amount_remaining": Decimal("0.00"),
                "subtotal": Decimal("99.00"),
                "total": Decimal("99.00"),
                "period_start": datetime.utcnow(),
                "period_end": datetime.utcnow(),
                "paid_at": datetime.utcnow(),
            },
            {
                "subscription_id": subscription.id,
                "organization_id": test_organization.id,
                "stripe_invoice_id": "in_test_2",
                "stripe_customer_id": "cus_test",
                "invoice_number": "INV-2024-002",
                "status": "open",
                "amount_due": Decimal("99.00"),
                "amount_paid": Decimal("0.00"),
                "amount_remaining": Decimal("99.00"),
                "subtotal": Decimal("99.00"),
                "total": Decimal("99.00"),
                "period_start": datetime.utcnow(),
                "period_end": datetime.utcnow(),
            },
        ]

        for invoice_data in invoices_data:
            invoice = Invoice(**invoice_data)
            db_session.add(invoice)

        await db_session.commit()

        # Test API
        response = auth_client.get("/api/v1/billing/invoices")
        data = assert_response_success(response)

        assert len(data) == 2
        assert data[0]["invoice_number"] == "INV-2024-002"  # Most recent first
        assert data[0]["status"] == "open"
        assert data[1]["invoice_number"] == "INV-2024-001"
        assert data[1]["status"] == "paid"

    async def test_list_invoices_with_limit(
        self, auth_client, db_session, test_organization, assert_response_success
    ):
        """Test listing invoices with limit parameter."""
        from app.models.subscription import SubscriptionPlan, Subscription, Invoice

        # Create plan and subscription
        plan = SubscriptionPlan(
            name="Professional",
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
            price_monthly=Decimal("99.00"),
            included_minutes=5000,
            included_calls=500,
            max_agents=5,
            max_phone_numbers=5,
            max_knowledge_bases=10,
        )
        db_session.add(plan)
        await db_session.flush()

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
        await db_session.flush()

        # Create 5 invoices
        for i in range(5):
            invoice = Invoice(
                subscription_id=subscription.id,
                organization_id=test_organization.id,
                stripe_invoice_id=f"in_test_{i}",
                stripe_customer_id="cus_test",
                invoice_number=f"INV-2024-{i:03d}",
                status="paid",
                amount_due=Decimal("99.00"),
                amount_paid=Decimal("99.00"),
                amount_remaining=Decimal("0.00"),
                subtotal=Decimal("99.00"),
                total=Decimal("99.00"),
                period_start=datetime.utcnow(),
                period_end=datetime.utcnow(),
            )
            db_session.add(invoice)

        await db_session.commit()

        # Test API with limit=2
        response = auth_client.get("/api/v1/billing/invoices?limit=2")
        data = assert_response_success(response)

        assert len(data) == 2
