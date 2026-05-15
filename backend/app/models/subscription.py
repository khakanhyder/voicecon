"""
Subscription and billing models for Stripe integration.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import String, Integer, Numeric, ForeignKey, Text, DateTime, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SubscriptionPlan(Base):
    """Subscription plan definitions."""
    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    stripe_product_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    stripe_price_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Pricing
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price_yearly: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="usd")

    # Usage limits
    included_minutes: Mapped[int] = mapped_column(Integer, default=0)  # Minutes per month
    included_calls: Mapped[int] = mapped_column(Integer, default=0)  # Calls per month
    max_agents: Mapped[int] = mapped_column(Integer, default=1)
    max_phone_numbers: Mapped[int] = mapped_column(Integer, default=1)
    max_knowledge_bases: Mapped[int] = mapped_column(Integer, default=0)

    # Metered billing rates (per unit overage)
    overage_rate_per_minute: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.015"))
    overage_rate_per_call: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.05"))

    # Features
    features: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)  # JSON feature flags

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)  # Show in pricing page
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # Display order

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="plan", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<SubscriptionPlan {self.name} (${self.price_monthly}/mo)>"


class Subscription(Base):
    """Customer subscriptions."""
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False
    )

    # Stripe data
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Subscription details
    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # active, past_due, canceled, incomplete, trialing
    billing_period: Mapped[str] = mapped_column(
        String(20), default="monthly"
    )  # monthly, yearly

    # Dates
    current_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    trial_start: Mapped[Optional[datetime]] = mapped_column(DateTime)
    trial_end: Mapped[Optional[datetime]] = mapped_column(DateTime)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Usage tracking
    current_period_minutes: Mapped[int] = mapped_column(Integer, default=0)
    current_period_calls: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    stripe_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan", back_populates="subscriptions")
    usage_records: Mapped[list["UsageRecord"]] = relationship(
        "UsageRecord", back_populates="subscription", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="subscription", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Subscription {self.stripe_subscription_id} ({self.status})>"


class UsageRecord(Base):
    """Track metered usage for billing."""
    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )

    # Usage details
    usage_type: Mapped[str] = mapped_column(String(50), nullable=False)  # minutes, calls, sms
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Reference
    resource_type: Mapped[Optional[str]] = mapped_column(String(50))  # call, agent, etc.
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))

    # Stripe data
    stripe_usage_record_id: Mapped[Optional[str]] = mapped_column(String(255))
    reported_to_stripe: Mapped[bool] = mapped_column(Boolean, default=False)

    # Billing period
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Metadata
    stripe_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="usage_records")

    def __repr__(self):
        return f"<UsageRecord {self.usage_type}: {self.quantity} @ ${self.unit_price}>"


class Invoice(Base):
    """Invoice records from Stripe."""
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )

    # Stripe data
    stripe_invoice_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Invoice details
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # draft, open, paid, void, uncollectible

    # Amounts (in cents)
    amount_due: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    amount_remaining: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    currency: Mapped[str] = mapped_column(String(3), default="usd")

    # URLs
    invoice_pdf: Mapped[Optional[str]] = mapped_column(String(500))
    hosted_invoice_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Dates
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Payment details
    payment_intent_id: Mapped[Optional[str]] = mapped_column(String(255))
    charge_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Line items
    line_items: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Attempt tracking
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    attempted: Mapped[bool] = mapped_column(Boolean, default=False)
    next_payment_attempt: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Metadata
    stripe_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="invoices")
    payment_failures: Mapped[list["PaymentFailure"]] = relationship(
        "PaymentFailure", back_populates="invoice", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Invoice {self.invoice_number} ({self.status}): ${self.total}>"


class PaymentFailure(Base):
    """Track failed payment attempts."""
    __tablename__ = "payment_failures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )

    # Failure details
    failure_code: Mapped[Optional[str]] = mapped_column(String(100))
    failure_message: Mapped[str] = mapped_column(Text, nullable=False)

    # Stripe data
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(255))
    stripe_charge_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Resolution
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Notifications
    customer_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    admin_notified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payment_failures")

    def __repr__(self):
        return f"<PaymentFailure {self.failure_code}: {self.failure_message[:50]}>"


# Indexes for performance
Index("idx_subscription_org", Subscription.organization_id)
Index("idx_subscription_status", Subscription.status)
Index("idx_subscription_stripe", Subscription.stripe_subscription_id)
Index("idx_usage_subscription", UsageRecord.subscription_id)
Index("idx_usage_org", UsageRecord.organization_id)
Index("idx_usage_period", UsageRecord.period_start, UsageRecord.period_end)
Index("idx_invoice_subscription", Invoice.subscription_id)
Index("idx_invoice_org", Invoice.organization_id)
Index("idx_invoice_status", Invoice.status)
Index("idx_invoice_stripe", Invoice.stripe_invoice_id)
Index("idx_payment_failure_invoice", PaymentFailure.invoice_id)
Index("idx_payment_failure_resolved", PaymentFailure.resolved)
