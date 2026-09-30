"""affiliates: choose monthly, yearly or both billing periods, each with its own rate

Revision ID: 0031_affiliate_billing_periods
Revises: 0030_affiliate_program
Create Date: 2026-09-30

Commission used to be annual-only by a fixed rule. It is now a per-affiliate
choice. Existing affiliates keep earning on yearly payments only
(``server_default``), so nothing changes for them until staff edit them.

Guarded so it is safe on a database ``create_all`` already built.
"""
from alembic import op
import sqlalchemy as sa


revision = "0031_affiliate_billing_periods"
down_revision = "0030_affiliate_program"
branch_labels = None
depends_on = None


def _columns(table: str) -> set:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    affiliates = _columns("affiliates")
    if "commission_billing_periods" not in affiliates:
        op.add_column(
            "affiliates",
            sa.Column("commission_billing_periods", sa.String(10), nullable=False, server_default="yearly"),
        )
    if "commission_percent_monthly" not in affiliates:
        op.add_column("affiliates", sa.Column("commission_percent_monthly", sa.Numeric(5, 2), nullable=True))
    if "max_monthly_commission_payments" not in affiliates:
        op.add_column("affiliates", sa.Column("max_monthly_commission_payments", sa.Integer(), nullable=True))

    if "max_monthly_commission_payments" not in _columns("affiliate_program"):
        op.add_column("affiliate_program", sa.Column("max_monthly_commission_payments", sa.Integer(), nullable=True))
        op.execute("UPDATE affiliate_program SET max_monthly_commission_payments = 12")


def downgrade() -> None:
    for column in ("commission_billing_periods", "commission_percent_monthly", "max_monthly_commission_payments"):
        if column in _columns("affiliates"):
            op.drop_column("affiliates", column)
    if "max_monthly_commission_payments" in _columns("affiliate_program"):
        op.drop_column("affiliate_program", "max_monthly_commission_payments")
