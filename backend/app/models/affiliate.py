"""
Affiliate program: partners who refer customers and earn a commission.

The money rules live in ``app.services.affiliates``; these tables only record
what happened. Four facts drive everything:

* A **referral** ties one organization (the billing unit) to one affiliate,
  once. First touch wins: a later link or coupon never moves it.
* A **commission** is earned from one paid invoice (Stripe) or order (Polar),
  when that payment's billing period is one the affiliate earns on (monthly,
  yearly or both — set per affiliate, each with its own rate).
  ``external_ref`` makes it idempotent across webhook re-deliveries.
* Commissions wait out a hold period (``pending``) so a refund can still
  cancel them, then become ``approved`` — payable.
* A **payout** gathers an affiliate's approved commissions and sends them in
  one Stripe Connect transfer, or records that staff paid them another way.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# ---- Affiliate statuses ----
AFFILIATE_INVITED = "invited"      # created by staff, has not signed in yet
AFFILIATE_ACTIVE = "active"
AFFILIATE_SUSPENDED = "suspended"  # links and coupon stop working; no new commissions
#: Statuses whose links, coupon and commissions work.
AFFILIATE_EARNING_STATUSES = (AFFILIATE_INVITED, AFFILIATE_ACTIVE)

# ---- Commission statuses ----
COMMISSION_PENDING = "pending"    # inside the hold period
COMMISSION_APPROVED = "approved"  # payable, not yet in a payout
COMMISSION_PAID = "paid"          # part of a completed payout
COMMISSION_REVERSED = "reversed"  # the payment was refunded before payout
COMMISSION_REJECTED = "rejected"  # staff voided it

# ---- Commission kinds ----
KIND_COMMISSION = "commission"    # earned from a payment
KIND_CLAWBACK = "clawback"        # negative: a refund after the commission was paid
KIND_ADJUSTMENT = "adjustment"    # added by staff, positive or negative

# ---- Payout statuses ----
PAYOUT_PROCESSING = "processing"
PAYOUT_PAID = "paid"
PAYOUT_FAILED = "failed"

# ---- Discount settings ----
DISCOUNT_YEARLY_ONLY = "yearly"
DISCOUNT_ALL_PLANS = "all"
DISCOUNT_ONCE = "once"
DISCOUNT_FOREVER = "forever"
DISCOUNT_REPEATING = "repeating"

# ---- Which billing periods earn commission (per affiliate) ----
EARNS_YEARLY = "yearly"
EARNS_MONTHLY = "monthly"
EARNS_BOTH = "both"
EARNS_CHOICES = (EARNS_YEARLY, EARNS_MONTHLY, EARNS_BOTH)

# ---- Application statuses (requests from the public form) ----
APPLICATION_PENDING = "pending"    # waiting for staff
APPLICATION_APPROVED = "approved"  # staff created an affiliate from it
APPLICATION_REJECTED = "rejected"


class AffiliateProgram(Base):
    """Program-wide rules. One row (``id == 1``), created on first read."""

    __tablename__ = "affiliate_program"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    #: Off: links and coupons stop attributing, and no new commissions are made.
    #: Commissions already earned can still be paid out.
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    #: Starting rate for a new affiliate. Each affiliate keeps its own rate.
    default_commission_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("20.00"), nullable=False
    )
    #: Days a commission waits before it can be paid, so a refund can cancel it.
    hold_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    #: Smallest payout staff can send without overriding it.
    min_payout_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("50.00"), nullable=False
    )
    #: How long a referral link is remembered in the visitor's browser.
    cookie_days: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    #: A referred customer must make their first qualifying yearly payment
    #: within this many days of signing up. NULL: no limit.
    referral_window_days: Mapped[Optional[int]] = mapped_column(Integer, default=365, nullable=True)
    #: How many yearly payments per customer earn a commission: 1 is the first
    #: yearly payment only. NULL: every yearly renewal. Affiliates can override.
    max_commission_payments: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    #: The same for monthly payments (for affiliates who earn on monthly plans):
    #: 12 is the first year of monthly payments. NULL: every month.
    max_monthly_commission_payments: Mapped[Optional[int]] = mapped_column(Integer, default=12, nullable=True)
    #: Plan slugs that earn commission. Empty: every paid plan.
    eligible_plan_slugs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Affiliate(Base):
    """A partner account. Signs in to the separate affiliate portal."""

    __tablename__ = "affiliates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: The login. An existing customer can also be an affiliate; the portal is a
    #: separate sign-in with its own session scope either way.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=AFFILIATE_INVITED, nullable=False, index=True)

    #: Lower-case slug used in ``?ref=``.
    referral_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    #: Upper-case code typed at checkout. NULL: this affiliate has no coupon.
    coupon_code: Mapped[Optional[str]] = mapped_column(String(40), unique=True, nullable=True)

    #: Which payments earn: ``yearly`` | ``monthly`` | ``both``.
    commission_billing_periods: Mapped[str] = mapped_column(
        String(10), default=EARNS_YEARLY, server_default=EARNS_YEARLY, nullable=False
    )
    #: Rate on yearly payments.
    commission_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    #: Rate on monthly payments. NULL: same as ``commission_percent``.
    commission_percent_monthly: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    #: Override of the program's payment limits (both periods at once).
    custom_max_payments: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_commission_payments: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_monthly_commission_payments: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    #: Percent off for customers using the coupon. NULL or 0: no discount.
    discount_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    #: ``yearly`` (annual checkouts only) | ``all``.
    discount_applies_to: Mapped[str] = mapped_column(String(10), default=DISCOUNT_YEARLY_ONLY, nullable=False)
    #: ``once`` (first payment) | ``forever`` | ``repeating`` (for N months).
    discount_duration: Mapped[str] = mapped_column(String(10), default=DISCOUNT_ONCE, nullable=False)
    discount_duration_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    #: Provider-side discount objects, created lazily at checkout. ``*_key``
    #: fingerprints the terms they were made with, so changing the discount
    #: makes a new object instead of silently reusing the old terms.
    stripe_coupon_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_coupon_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    polar_discount_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    polar_discount_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Stripe Connect (Express) account that receives payouts.
    stripe_account_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    stripe_country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    stripe_details_submitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: Transfers capability is active: a payout can be sent.
    stripe_transfers_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stripe_payouts_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stripe_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    #: Staff-only notes.
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    invited_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = relationship("User", foreign_keys=[user_id], lazy="joined")

    def __repr__(self) -> str:
        return f"<Affiliate {self.referral_code} ({self.status})>"


class AffiliateApplication(Base):
    """A request to join the program, sent from the public form.

    It is only a request: nothing can be earned from it. Staff review it and
    create the affiliate with the normal form, which links the two.
    """

    __tablename__ = "affiliate_applications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Lower-cased. Not unique: someone rejected earlier may apply again.
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    #: Site, channel or profile where they would promote.
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    #: Their audience and how they plan to promote, in their own words.
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=APPLICATION_PENDING, nullable=False, index=True)

    #: The affiliate created from this request.
    affiliate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("affiliates.id", ondelete="SET NULL"), nullable=True
    )
    #: Staff-only: why it was rejected.
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<AffiliateApplication {self.email} ({self.status})>"


class AffiliateClick(Base):
    """One visit through a referral link. Only counted, never used for money."""

    __tablename__ = "affiliate_clicks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    affiliate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("affiliates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    landing_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    referrer: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class AffiliateReferral(Base):
    """An organization brought in by an affiliate. One per organization, forever."""

    __tablename__ = "affiliate_referrals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    affiliate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("affiliates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    #: The person who signed up (or applied the coupon).
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: ``link`` | ``coupon``
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    #: First commission-earning payment.
    converted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AffiliateCommission(Base):
    """Money owed to an affiliate, or (negative) taken back."""

    __tablename__ = "affiliate_commissions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    affiliate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("affiliates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    referral_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("affiliate_referrals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )
    #: ``stripe:<invoice id>`` / ``polar:<order id>`` for a commission;
    #: ``clawback:<commission id>:<n>`` for a clawback. Unique, so a
    #: re-delivered webhook cannot pay twice.
    external_ref: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default=KIND_COMMISSION, nullable=False)
    #: stripe | polar | manual
    provider: Mapped[str] = mapped_column(String(20), nullable=False)

    plan_slug: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    billing_period: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    #: subscription_create | subscription_cycle | subscription_update
    billing_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    #: What the customer paid, net of discount and before tax.
    base_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    #: What this row is worth now. Negative for a clawback.
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    #: Before any refund reduced it.
    original_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    #: Share of the payment refunded so far, 0..1. Refund events carry a running
    #: total, so applying one twice changes nothing.
    refunded_fraction: Mapped[Decimal] = mapped_column(Numeric(7, 6), default=Decimal("0"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="usd", nullable=False)

    status: Mapped[str] = mapped_column(String(20), default=COMMISSION_PENDING, nullable=False, index=True)
    #: End of the hold period.
    available_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    #: End of the service period paid for; a mid-year upgrade only earns while
    #: a commissioned year is running.
    service_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    payout_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("affiliate_payouts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    earned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reversed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


Index("idx_affiliate_commission_status_available", AffiliateCommission.status, AffiliateCommission.available_at)


class AffiliatePayout(Base):
    """One payment to an affiliate, covering a set of approved commissions."""

    __tablename__ = "affiliate_payouts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    affiliate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("affiliates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="usd", nullable=False)
    #: ``stripe`` (Connect transfer) | ``manual`` (paid outside the app)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=PAYOUT_PROCESSING, nullable=False, index=True)
    stripe_transfer_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    #: A manual payout's bank or PayPal reference.
    reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    #: Staff-facing reason, shown only in the admin console.
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    commission_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
