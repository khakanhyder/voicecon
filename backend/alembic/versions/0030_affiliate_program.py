"""affiliate program: affiliates, referrals, commissions, payouts

Revision ID: 0030_affiliate_program
Revises: 0029_remove_salesforce
Create Date: 2026-09-30

Partners referred by link or coupon earn a commission on referred customers'
yearly payments, paid out through Stripe Connect. See app/models/affiliate.py.

Guarded like 0020 so it is safe on a database ``create_all`` already built.
"""
from alembic import op
import sqlalchemy as sa


revision = "0030_affiliate_program"
down_revision = "0029_remove_salesforce"
branch_labels = None
depends_on = None


def _tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _timestamps() -> list:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def upgrade() -> None:
    tables = _tables()

    if "affiliate_program" not in tables:
        op.create_table(
            "affiliate_program",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("default_commission_percent", sa.Numeric(5, 2), nullable=False, server_default="20.00"),
            sa.Column("hold_days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("min_payout_amount", sa.Numeric(10, 2), nullable=False, server_default="50.00"),
            sa.Column("cookie_days", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("referral_window_days", sa.Integer(), nullable=True),
            sa.Column("max_commission_payments", sa.Integer(), nullable=True),
            sa.Column("eligible_plan_slugs", sa.JSON(), nullable=False),
            sa.Column("updated_by", sa.Uuid(), nullable=True),
            *_timestamps(),
        )

    if "affiliates" not in tables:
        op.create_table(
            "affiliates",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("company", sa.String(255), nullable=True),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("referral_code", sa.String(40), nullable=False),
            sa.Column("coupon_code", sa.String(40), nullable=True),
            sa.Column("commission_percent", sa.Numeric(5, 2), nullable=False),
            sa.Column("custom_max_payments", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("max_commission_payments", sa.Integer(), nullable=True),
            sa.Column("discount_percent", sa.Numeric(5, 2), nullable=True),
            sa.Column("discount_applies_to", sa.String(10), nullable=False, server_default="yearly"),
            sa.Column("discount_duration", sa.String(10), nullable=False, server_default="once"),
            sa.Column("discount_duration_months", sa.Integer(), nullable=True),
            sa.Column("stripe_coupon_id", sa.String(255), nullable=True),
            sa.Column("stripe_coupon_key", sa.String(100), nullable=True),
            sa.Column("polar_discount_id", sa.String(255), nullable=True),
            sa.Column("polar_discount_key", sa.String(100), nullable=True),
            sa.Column("stripe_account_id", sa.String(255), nullable=True),
            sa.Column("stripe_country", sa.String(2), nullable=True),
            sa.Column("stripe_details_submitted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("stripe_transfers_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("stripe_payouts_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("stripe_checked_at", sa.DateTime(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("invited_at", sa.DateTime(), nullable=True),
            sa.Column("activated_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            *_timestamps(),
            sa.UniqueConstraint("user_id", name="uq_affiliates_user_id"),
            sa.UniqueConstraint("referral_code", name="uq_affiliates_referral_code"),
            sa.UniqueConstraint("coupon_code", name="uq_affiliates_coupon_code"),
            sa.UniqueConstraint("stripe_account_id", name="uq_affiliates_stripe_account_id"),
        )
        op.create_index("ix_affiliates_status", "affiliates", ["status"])

    if "affiliate_clicks" not in tables:
        op.create_table(
            "affiliate_clicks",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("affiliate_id", sa.Uuid(), sa.ForeignKey("affiliates.id", ondelete="CASCADE"), nullable=False),
            sa.Column("landing_path", sa.String(500), nullable=True),
            sa.Column("referrer", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_affiliate_clicks_affiliate_id", "affiliate_clicks", ["affiliate_id"])
        op.create_index("ix_affiliate_clicks_created_at", "affiliate_clicks", ["created_at"])

    if "affiliate_referrals" not in tables:
        op.create_table(
            "affiliate_referrals",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("affiliate_id", sa.Uuid(), sa.ForeignKey("affiliates.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("source", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("converted_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("organization_id", name="uq_affiliate_referrals_organization_id"),
        )
        op.create_index("ix_affiliate_referrals_affiliate_id", "affiliate_referrals", ["affiliate_id"])
        op.create_index("ix_affiliate_referrals_created_at", "affiliate_referrals", ["created_at"])

    if "affiliate_payouts" not in tables:
        op.create_table(
            "affiliate_payouts",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("affiliate_id", sa.Uuid(), sa.ForeignKey("affiliates.id", ondelete="CASCADE"), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("method", sa.String(20), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("stripe_transfer_id", sa.String(255), nullable=True),
            sa.Column("reference", sa.String(255), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("commission_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("stripe_transfer_id", name="uq_affiliate_payouts_stripe_transfer_id"),
        )
        op.create_index("ix_affiliate_payouts_affiliate_id", "affiliate_payouts", ["affiliate_id"])
        op.create_index("ix_affiliate_payouts_status", "affiliate_payouts", ["status"])

    if "affiliate_commissions" not in tables:
        op.create_table(
            "affiliate_commissions",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("affiliate_id", sa.Uuid(), sa.ForeignKey("affiliates.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "referral_id", sa.Uuid(), sa.ForeignKey("affiliate_referrals.id", ondelete="SET NULL"), nullable=True
            ),
            sa.Column("organization_id", sa.Uuid(), nullable=True),
            sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
            sa.Column("external_ref", sa.String(255), nullable=True),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("provider", sa.String(20), nullable=False),
            sa.Column("plan_slug", sa.String(50), nullable=True),
            sa.Column("billing_period", sa.String(20), nullable=True),
            sa.Column("billing_reason", sa.String(50), nullable=True),
            sa.Column("base_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("rate_percent", sa.Numeric(5, 2), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("original_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("refunded_fraction", sa.Numeric(7, 6), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("available_at", sa.DateTime(), nullable=False),
            sa.Column("service_period_end", sa.DateTime(), nullable=True),
            sa.Column(
                "payout_id", sa.Uuid(), sa.ForeignKey("affiliate_payouts.id", ondelete="SET NULL"), nullable=True
            ),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("earned_at", sa.DateTime(), nullable=False),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("reversed_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            *_timestamps(),
            sa.UniqueConstraint("external_ref", name="uq_affiliate_commissions_external_ref"),
        )
        for column in ("affiliate_id", "referral_id", "organization_id", "status", "payout_id"):
            op.create_index(f"ix_affiliate_commissions_{column}", "affiliate_commissions", [column])
        op.create_index(
            "idx_affiliate_commission_status_available", "affiliate_commissions", ["status", "available_at"]
        )


def downgrade() -> None:
    tables = _tables()
    for table in (
        "affiliate_commissions",
        "affiliate_payouts",
        "affiliate_referrals",
        "affiliate_clicks",
        "affiliates",
        "affiliate_program",
    ):
        if table in tables:
            op.drop_table(table)
