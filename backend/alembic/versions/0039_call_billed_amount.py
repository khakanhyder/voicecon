"""calls.billed_amount: what the customer was charged for a call

Revision ID: 0039_call_billed_amount
Revises: 0040_blog_slug_redirects
Create Date: 2026-10-14

The ``cost_*`` columns hold what the providers charge Voicecon for a call. The
call screens showed ``cost_total`` to every customer, as if it were the price.
``billed_amount`` is the price: the Pay As You Go wallet debit for the call, at
the plan's per-minute rate. Backfilled from the wallet ledger, which is the
record of what was actually charged.

Guarded so it is safe on a database ``create_all`` already built.
"""
from alembic import op
import sqlalchemy as sa


revision = "0039_call_billed_amount"
down_revision = "0040_blog_slug_redirects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("calls")}
    if "billed_amount" not in cols:
        op.add_column("calls", sa.Column("billed_amount", sa.Numeric(10, 4), nullable=True))

    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "wallet_transactions" in tables:
        op.execute(
            """
            UPDATE calls
               SET billed_amount = charged.amount
              FROM (
                    SELECT reference_id, SUM(-amount_cents) / 100.0 AS amount
                      FROM wallet_transactions
                     WHERE type = 'usage' AND reference_type = 'call'
                     GROUP BY reference_id
                   ) AS charged
             WHERE charged.reference_id = calls.id::text
               AND calls.billed_amount IS NULL
            """
        )


def downgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("calls")}
    if "billed_amount" in cols:
        op.drop_column("calls", "billed_amount")
