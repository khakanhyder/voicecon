"""
Subscription and billing models for Stripe integration.

The tables here are the *source of truth* for what an organization has bought.
What it is allowed to do right now is a derived question, answered by
``app.services.billing.entitlements`` — which applies trial expiry at read time
rather than trusting :attr:`Subscription.status`, since that string is only as
fresh as the last reconciler run.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import String, Integer, Numeric, ForeignKey, Text, DateTime, Boolean, Index, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# ---- Subscription statuses ----
# Persisted on ``Subscription.status``. Anything derived (expiring soon, over
# quota, in grace) is computed by the entitlement resolver and never stored.
STATUS_TRIALING = "trialing"      # trial running, now < trial_end
STATUS_ACTIVE = "active"          # paid and current
STATUS_PAST_DUE = "past_due"      # payment failed, inside Stripe's dunning window
STATUS_GRACE = "grace"            # lapsed, inside the grace period, read-only soon
STATUS_EXPIRED = "expired"        # trial ended or subscription lapsed for good
STATUS_CANCELED = "canceled"      # user cancelled; may still be inside a paid period
STATUS_INCOMPLETE = "incomplete"  # Stripe checkout started but never confirmed

#: Statuses that occupy the organization's single "live" subscription slot. An
#: org may hold exactly one of these at a time (enforced by a partial unique
#: index in migration 0015).
LIVE_STATUSES = (STATUS_TRIALING, STATUS_ACTIVE, STATUS_PAST_DUE, STATUS_GRACE)

#: Statuses that still permit *runtime* — placing calls, answering calls,
#: running agents and workflows. ``grace`` is deliberately included: a card that
#: failed once should not take someone's phone line down the same afternoon.
RUNTIME_STATUSES = (STATUS_TRIALING, STATUS_ACTIVE, STATUS_PAST_DUE, STATUS_GRACE)

# ---- Subscription sources ----
SOURCE_STRIPE = "stripe"  # a real Stripe subscription
SOURCE_TRIAL = "trial"    # our own card-free trial; no Stripe object exists
SOURCE_MANUAL = "manual"  # created by staff (enterprise deal, comp)


class SubscriptionPlan(Base):
    """Subscription plan definitions."""
    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    #: Stable identifier code branches on. Never branch on ``name`` (renamed for
    #: marketing) or ``id`` (differs between environments).
    slug: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    #: Rank for up/downgrade comparisons. Higher is the bigger plan.
    tier: Mapped[int] = mapped_column(Integer, default=0)
    stripe_product_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    stripe_price_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    #: Yearly price is a separate Stripe object. Backfilled at checkout time by
    #: ``StripeService.ensure_stripe_price`` when a customer first picks yearly.
    stripe_price_id_yearly: Mapped[Optional[str]] = mapped_column(String(255), unique=True)

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
    #: Marketing copy — the bullet list the pricing page renders. Human-facing.
    features: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    #: The machine-readable contract the backend enforces: ``{"features": {...},
    #: "limits": {...}, "overage": {...}}``. See ``app.services.billing.catalog``.
    #: Kept separate from ``features`` on purpose — one column serving both
    #: marketing and enforcement guarantees the two drift apart.
    entitlements: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Trial
    #: Kept in step with ``catalog.DEFAULT_TRIAL_DAYS`` by the startup backfill;
    #: the literal here only covers rows inserted without going through it.
    trial_days: Mapped[int] = mapped_column(Integer, default=30)
    is_trialable: Mapped[bool] = mapped_column(Boolean, default=True)

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
        "Subscription",
        back_populates="plan",
        cascade="all, delete-orphan",
        foreign_keys="Subscription.plan_id",
    )

    def __repr__(self):
        return f"<SubscriptionPlan {self.name} (${self.price_monthly}/mo)>"


class Subscription(Base):
    """Customer subscriptions."""
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False
    )

    # Stripe data. Both are NULL for a card-free trial, which has no Stripe
    # object at all — earlier code faked a ``local_trial_<uuid>`` id to satisfy
    # a NOT NULL constraint, and that fake id then leaked into Stripe-shaped
    # code paths.
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Subscription details
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # see LIVE_STATUSES
    billing_period: Mapped[str] = mapped_column(
        String(20), default="monthly"
    )  # monthly, yearly
    #: Where this subscription came from: stripe | trial | manual.
    source: Mapped[str] = mapped_column(String(20), default=SOURCE_STRIPE, nullable=False)

    # Dates
    current_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    trial_start: Mapped[Optional[datetime]] = mapped_column(DateTime)
    trial_end: Mapped[Optional[datetime]] = mapped_column(DateTime)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    #: End of the cushion granted after a trial or payment lapses. Runtime keeps
    #: working until this passes, so a Friday expiry is not a weekend outage.
    grace_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime)
    #: When the reconciler moved this to ``expired``.
    expired_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    #: When a free trial turned into a paying subscription. The conversion metric.
    trial_converted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Lifecycle flags
    #: Cancel at the end of the paid period rather than immediately — the
    #: default, because the customer paid for that period.
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Plan taking effect next period. Set by a downgrade, which must not take
    #: away capacity the customer has already paid for.
    scheduled_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subscription_plans.id")
    )

    # Usage tracking
    current_period_minutes: Mapped[int] = mapped_column(Integer, default=0)
    current_period_calls: Mapped[int] = mapped_column(Integer, default=0)
    current_period_sms: Mapped[int] = mapped_column(Integer, default=0)
    current_period_emails: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    stripe_metadata: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships. ``foreign_keys`` is explicit because the table now has two
    # FKs to subscription_plans (the current plan and a scheduled downgrade).
    plan: Mapped["SubscriptionPlan"] = relationship(
        "SubscriptionPlan", back_populates="subscriptions", foreign_keys=[plan_id]
    )
    scheduled_plan: Mapped[Optional["SubscriptionPlan"]] = relationship(
        "SubscriptionPlan", foreign_keys=[scheduled_plan_id]
    )
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
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )

    # Usage details
    usage_type: Mapped[str] = mapped_column(String(50), nullable=False)  # minutes, calls, sms
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Reference
    resource_type: Mapped[Optional[str]] = mapped_column(String(50))  # call, agent, etc.
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))

    # Stripe data
    stripe_usage_record_id: Mapped[Optional[str]] = mapped_column(String(255))
    reported_to_stripe: Mapped[bool] = mapped_column(Boolean, default=False)

    # Billing period
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Metadata
    stripe_metadata: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

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
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False
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
    line_items: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Attempt tracking
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    attempted: Mapped[bool] = mapped_column(Boolean, default=False)
    next_payment_attempt: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Metadata
    stripe_metadata: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

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
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("invoices.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False
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


class SubscriptionEvent(Base):
    """Append-only log of everything that ever happened to a subscription.

    Current state is a materialised convenience; *this* is the ledger. It
    answers "why is this account in this state?" — the most common billing
    support question — and doubles as the send-once guard for lifecycle emails.

    Rows are never updated or deleted.
    """
    __tablename__ = "subscription_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    subscription_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL")
    )

    #: trial_started | trial_expiring | trial_expired | trial_converted
    #: | grace_started | grace_ended | activated | renewed | payment_failed
    #: | past_due | canceled | reactivated | plan_changed | plan_change_scheduled
    #: | notice_sent
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)

    from_status: Mapped[Optional[str]] = mapped_column(String(50))
    to_status: Mapped[Optional[str]] = mapped_column(String(50))
    from_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    to_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))

    #: user | system | stripe | admin
    actor_type: Mapped[str] = mapped_column(String(20), default="system", nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))

    stripe_event_id: Mapped[Optional[str]] = mapped_column(String(255))
    payload: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<SubscriptionEvent {self.event_type} org={self.organization_id}>"


class ProcessedStripeEvent(Base):
    """Webhook idempotency ledger.

    Stripe retries deliveries, so without this a re-delivered ``invoice.paid``
    applies its effect twice. The insert happens in the same transaction as the
    effect: a duplicate-key violation is the signal to skip, not an error.
    """
    __tablename__ = "processed_stripe_events"

    stripe_event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<ProcessedStripeEvent {self.stripe_event_id}>"


class TrialGrant(Base):
    """One row per free trial ever handed out.

    Without this, "delete the workspace and sign up again" is an unlimited free
    product. Recorded against both the user and their email domain so the same
    company cannot cycle through trials on new addresses.
    """
    __tablename__ = "trial_grants"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    #: Lower-cased domain part of the signup email. Indexed, not unique — a
    #: genuine second team at a large company must not be silently refused.
    email_domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    signup_ip: Mapped[Optional[str]] = mapped_column(String(64))

    granted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    converted: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self):
        return f"<TrialGrant user={self.user_id} domain={self.email_domain}>"


class OrganizationEntitlementOverride(Base):
    """Per-organization overrides merged over the plan's entitlements.

    Lets sales comp an account, extend a trial, or unlock one feature for an
    enterprise deal without hand-editing subscription rows or inventing a
    one-off plan.
    """
    __tablename__ = "organization_entitlements"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), unique=True, nullable=False
    )
    #: Same shape as ``SubscriptionPlan.entitlements``; only the keys present
    #: are overridden, everything else inherits from the plan.
    overrides: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<OrganizationEntitlementOverride org={self.organization_id}>"


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

# The reconciler scans by (status, deadline); without these it table-scans
# every subscription every 15 minutes.
Index("idx_subscription_trial_sweep", Subscription.status, Subscription.trial_end)
Index("idx_subscription_period_sweep", Subscription.status, Subscription.current_period_end)
Index("idx_subscription_grace_sweep", Subscription.status, Subscription.grace_period_end)
Index("idx_subscription_event_org", SubscriptionEvent.organization_id, SubscriptionEvent.created_at)
Index("idx_subscription_event_type", SubscriptionEvent.subscription_id, SubscriptionEvent.event_type)
