"""pay as you go: the prepaid wallet and its ledger

Revision ID: 0036_payg_wallet
Revises: 0035_account_deactivation
Create Date: 2026-10-02

Adds the two tables behind the Pay As You Go plan:

* ``wallets`` — one row per organization: the current balance, the
  auto-recharge settings and the card saved for it.
* ``wallet_transactions`` — the append-only ledger of every credit and debit.
  ``idempotency_key`` is unique, which is what stops a repeated webhook or a
  repeated carrier callback from crediting or charging twice.

The Pay As You Go plan row itself is created by the startup seeder
(``seed_plans``), like every other plan, so there is nothing to insert here.

Guarded so it is safe on a database ``create_all`` already built, and safe to
rerun after a partial failure.

Downgrading drops both tables. Workspaces on Pay As You Go are expired first:
the code being downgraded to knows nothing about a balance, and would read
their subscription as an active plan with unmetered minutes.
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "0036_payg_wallet"
down_revision = "0035_account_deactivation"
branch_labels = None
depends_on = None

#: Matches models.subscription.SOURCE_WALLET and the seeded plan's slug.
#: Hard-coded: a migration must keep working when the code around it changes.
WALLET_SOURCE = "wallet"
PAYG_SLUG = "payg"


def _tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table: str) -> set:
    return {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes(table)}


def _index(name: str, table: str, columns: list) -> None:
    if name not in _indexes(table):
        op.create_index(name, table, columns)


def upgrade() -> None:
    tables = _tables()

    if "wallets" not in tables:
        op.create_table(
            "wallets",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column(
                "organization_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("organizations.id"),
                nullable=False,
            ),
            sa.Column("balance_cents", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
            sa.Column(
                "auto_recharge_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column("auto_recharge_threshold_cents", sa.Integer(), nullable=True),
            sa.Column("auto_recharge_amount_cents", sa.Integer(), nullable=True),
            sa.Column("auto_recharge_attempted_at", sa.DateTime(), nullable=True),
            sa.Column("auto_recharge_failures", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("stripe_customer_id", sa.String(255), nullable=True),
            sa.Column("stripe_payment_method_id", sa.String(255), nullable=True),
            sa.Column("card_brand", sa.String(30), nullable=True),
            sa.Column("card_last4", sa.String(4), nullable=True),
            sa.Column("notice_level", sa.String(10), nullable=False, server_default="none"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("organization_id", name="uq_wallets_organization_id"),
        )

    if "wallet_transactions" not in tables:
        op.create_table(
            "wallet_transactions",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column(
                "wallet_id", sa.Uuid(as_uuid=True), sa.ForeignKey("wallets.id"), nullable=False
            ),
            sa.Column(
                "organization_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("organizations.id"),
                nullable=False,
            ),
            sa.Column("type", sa.String(20), nullable=False),
            sa.Column("amount_cents", sa.BigInteger(), nullable=False),
            sa.Column("balance_after_cents", sa.BigInteger(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
            sa.Column("description", sa.String(255), nullable=True),
            sa.Column("reference_type", sa.String(40), nullable=True),
            sa.Column("reference_id", sa.String(255), nullable=True),
            sa.Column("client_ref", sa.String(64), nullable=True),
            sa.Column("idempotency_key", sa.String(255), nullable=True),
            sa.Column("actor_type", sa.String(20), nullable=False, server_default="system"),
            sa.Column("actor_id", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("idempotency_key", name="uq_wallet_txn_idempotency_key"),
        )

    _index("idx_wallet_txn_org_created", "wallet_transactions", ["organization_id", "created_at"])
    _index("idx_wallet_txn_wallet", "wallet_transactions", ["wallet_id"])
    _index("idx_wallet_txn_reference", "wallet_transactions", ["reference_type", "reference_id"])
    _index("ix_wallet_transactions_client_ref", "wallet_transactions", ["client_ref"])


def downgrade() -> None:
    bind = op.get_bind()
    now = datetime.utcnow()

    # A wallet subscription has no meaning without the wallet. Left "active" it
    # would run on the plan's unmetered minutes for free.
    bind.execute(
        sa.text(
            "UPDATE subscriptions SET status = 'expired', expired_at = :now, ended_at = :now "
            "WHERE source = :source AND status IN ('trialing', 'active', 'past_due', 'grace')"
        ),
        {"now": now, "source": WALLET_SOURCE},
    )
    # A plan change that was waiting to become Pay As You Go has nowhere to go.
    bind.execute(
        sa.text(
            "UPDATE subscriptions SET scheduled_plan_id = NULL WHERE scheduled_plan_id IN "
            "(SELECT id FROM subscription_plans WHERE slug = :slug)"
        ),
        {"slug": PAYG_SLUG},
    )
    # Off sale; the row stays because subscriptions still point at it.
    bind.execute(
        sa.text(
            "UPDATE subscription_plans SET is_active = false, is_public = false WHERE slug = :slug"
        ),
        {"slug": PAYG_SLUG},
    )

    tables = _tables()
    if "wallet_transactions" in tables:
        op.drop_table("wallet_transactions")
    if "wallets" in tables:
        op.drop_table("wallets")
