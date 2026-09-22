"""polar billing: Polar ids on plans, subscriptions and invoices

Revision ID: 0021_polar_billing
Revises: 0020_platform_admin
Create Date: 2026-09-22

Adds Polar (Merchant of Record) as a second payment provider beside Stripe:

* ``subscription_plans.polar_product_id`` / ``polar_product_id_yearly``
* ``subscriptions.polar_subscription_id`` / ``polar_customer_id``
* ``invoices.provider`` + ``invoices.polar_order_id``; the Stripe invoice and
  customer ids become nullable, since a Polar order has neither.

Guarded like 0020 so it is safe on a database ``create_all`` already built.
"""
from alembic import op
import sqlalchemy as sa


revision = "0021_polar_billing"
down_revision = "0020_platform_admin"
branch_labels = None
depends_on = None


def _columns(table: str) -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _add(table: str, column: sa.Column, unique_name: str = None) -> None:
    if column.name in _columns(table):
        return
    op.add_column(table, column)
    if unique_name:
        op.create_unique_constraint(unique_name, table, [column.name])


def upgrade() -> None:
    _add("subscription_plans", sa.Column("polar_product_id", sa.String(255), nullable=True), "uq_plans_polar_product_id")
    _add("subscription_plans", sa.Column("polar_product_id_yearly", sa.String(255), nullable=True), "uq_plans_polar_product_id_yearly")
    _add("subscriptions", sa.Column("polar_subscription_id", sa.String(255), nullable=True), "uq_subscriptions_polar_subscription_id")
    _add("subscriptions", sa.Column("polar_customer_id", sa.String(255), nullable=True))
    _add("invoices", sa.Column("provider", sa.String(20), nullable=False, server_default="stripe"))
    _add("invoices", sa.Column("polar_order_id", sa.String(255), nullable=True), "uq_invoices_polar_order_id")
    op.alter_column("invoices", "stripe_invoice_id", existing_type=sa.String(255), nullable=True)
    op.alter_column("invoices", "stripe_customer_id", existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    # Polar orders have no Stripe ids, so they must go before NOT NULL returns.
    op.execute("DELETE FROM invoices WHERE stripe_invoice_id IS NULL")
    op.alter_column("invoices", "stripe_customer_id", existing_type=sa.String(255), nullable=False)
    op.alter_column("invoices", "stripe_invoice_id", existing_type=sa.String(255), nullable=False)
    for table, column, unique in (
        ("invoices", "polar_order_id", "uq_invoices_polar_order_id"),
        ("invoices", "provider", None),
        ("subscriptions", "polar_customer_id", None),
        ("subscriptions", "polar_subscription_id", "uq_subscriptions_polar_subscription_id"),
        ("subscription_plans", "polar_product_id_yearly", "uq_plans_polar_product_id_yearly"),
        ("subscription_plans", "polar_product_id", "uq_plans_polar_product_id"),
    ):
        if column in _columns(table):
            if unique:
                op.drop_constraint(unique, table, type_="unique")
            op.drop_column(table, column)
