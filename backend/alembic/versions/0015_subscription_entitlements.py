"""subscription entitlements, trial lifecycle and billing audit tables

Revision ID: 0015_subscription_ent
Revises: 0014_api_key_prefix_idx
Create Date: 2026-08-05

Turns the subscription tables from "a record of what Stripe told us" into
something the product can actually enforce:

* ``subscription_plans`` gains a stable ``slug`` to branch on, a ``tier`` for
  up/downgrade comparisons, a machine-readable ``entitlements`` document, and
  trial settings. ``features`` stays as marketing copy.
* ``subscriptions`` gains the trial/grace lifecycle columns, a ``source`` so a
  card-free trial is distinguishable from a Stripe subscription, and per-period
  SMS/email counters. ``stripe_subscription_id`` becomes nullable, because a
  trial genuinely has no Stripe object — the old NOT NULL forced the trial code
  to fabricate ``local_trial_<uuid>`` ids that then leaked into Stripe paths.
* Four new tables: the subscription event ledger, webhook idempotency, trial
  grants (so a workspace cannot be deleted and re-trialled forever), and
  per-org entitlement overrides for comps.

A partial unique index enforces "at most one live subscription per
organization", which until now was a SELECT-then-INSERT race.

Idempotent throughout: a dev database may have been built by
``Base.metadata.create_all``, so every step checks before acting.

Note: the revision id is kept <=32 chars to fit alembic_version.version_num.
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_subscription_ent"
down_revision = "0014_api_key_prefix_idx"
branch_labels = None
depends_on = None


LIVE_STATUSES = ("trialing", "active", "past_due", "grace")
ONE_LIVE_SUB_INDEX = "uq_one_live_subscription_per_org"


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table: str) -> bool:
    return table in _inspector().get_table_names()


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    return column in {c["name"] for c in _inspector().get_columns(table)}


def _has_index(table: str, index: str) -> bool:
    if not _has_table(table):
        return False
    return index in {ix["name"] for ix in _inspector().get_indexes(table)}


def _add_column(table: str, column: sa.Column) -> None:
    if not _has_column(table, column.name):
        op.add_column(table, column)


def _create_index(name: str, table: str, columns) -> None:
    if not _has_index(table, name):
        op.create_index(name, table, columns)


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ---- subscription_plans ----
    _add_column("subscription_plans", sa.Column("slug", sa.String(50), nullable=True))
    _add_column(
        "subscription_plans",
        sa.Column("tier", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column(
        "subscription_plans", sa.Column("stripe_price_id_yearly", sa.String(255), nullable=True)
    )
    _add_column("subscription_plans", sa.Column("entitlements", sa.JSON(), nullable=True))
    _add_column(
        "subscription_plans",
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="7"),
    )
    _add_column(
        "subscription_plans",
        sa.Column("is_trialable", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    _create_index("ix_subscription_plans_slug", "subscription_plans", ["slug"])

    # Derive a slug for rows seeded before this migration, so the catalogue can
    # match them by slug instead of by display name.
    op.execute(
        """
        UPDATE subscription_plans
           SET slug = CASE
                        WHEN lower(name) LIKE '%voice%'  THEN 'voice-ai'
                        WHEN lower(name) LIKE '%chatbot%' THEN 'sales-chatbot'
                        ELSE lower(replace(name, ' ', '-'))
                      END
         WHERE slug IS NULL
        """
    )
    op.execute(
        "UPDATE subscription_plans SET tier = 2 WHERE slug = 'voice-ai' AND tier = 0"
    )
    op.execute(
        "UPDATE subscription_plans SET tier = 1 WHERE slug = 'sales-chatbot' AND tier = 0"
    )

    # ---- subscriptions ----
    _add_column(
        "subscriptions",
        sa.Column("source", sa.String(20), nullable=False, server_default="stripe"),
    )
    _add_column("subscriptions", sa.Column("grace_period_end", sa.DateTime(), nullable=True))
    _add_column("subscriptions", sa.Column("expired_at", sa.DateTime(), nullable=True))
    _add_column("subscriptions", sa.Column("trial_converted_at", sa.DateTime(), nullable=True))
    _add_column(
        "subscriptions",
        sa.Column(
            "cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    _add_column("subscriptions", sa.Column("scheduled_plan_id", sa.Uuid(), nullable=True))
    _add_column(
        "subscriptions",
        sa.Column("current_period_sms", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column(
        "subscriptions",
        sa.Column("current_period_emails", sa.Integer(), nullable=False, server_default="0"),
    )

    # A card-free trial has no Stripe object. Relax the NOT NULLs and clear the
    # placeholder ids the old trial endpoint had to invent.
    with op.batch_alter_table("subscriptions") as batch:
        batch.alter_column(
            "stripe_subscription_id", existing_type=sa.String(255), nullable=True
        )
        batch.alter_column(
            "stripe_customer_id", existing_type=sa.String(255), nullable=True
        )

    op.execute(
        """
        UPDATE subscriptions
           SET source = 'trial',
               stripe_subscription_id = NULL,
               stripe_customer_id = NULL
         WHERE stripe_subscription_id LIKE 'local_trial_%'
        """
    )
    op.execute("UPDATE subscriptions SET stripe_customer_id = NULL WHERE stripe_customer_id = ''")

    _create_index(
        "idx_subscription_trial_sweep", "subscriptions", ["status", "trial_end"]
    )
    _create_index(
        "idx_subscription_period_sweep", "subscriptions", ["status", "current_period_end"]
    )
    _create_index(
        "idx_subscription_grace_sweep", "subscriptions", ["status", "grace_period_end"]
    )

    # One live subscription per organization. Postgres does partial unique
    # indexes; elsewhere the application-level check in the trial/checkout
    # endpoints remains the only guard.
    if is_postgres and not _has_index("subscriptions", ONE_LIVE_SUB_INDEX):
        statuses = ", ".join(f"'{s}'" for s in LIVE_STATUSES)
        op.execute(
            f"""
            CREATE UNIQUE INDEX {ONE_LIVE_SUB_INDEX}
                ON subscriptions (organization_id)
             WHERE status IN ({statuses})
            """
        )

    # ---- subscription_events ----
    if not _has_table("subscription_events"):
        op.create_table(
            "subscription_events",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "organization_id",
                sa.Uuid(),
                sa.ForeignKey("organizations.id"),
                nullable=False,
            ),
            sa.Column(
                "subscription_id",
                sa.Uuid(),
                sa.ForeignKey("subscriptions.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("event_type", sa.String(50), nullable=False),
            sa.Column("from_status", sa.String(50), nullable=True),
            sa.Column("to_status", sa.String(50), nullable=True),
            sa.Column("from_plan_id", sa.Uuid(), nullable=True),
            sa.Column("to_plan_id", sa.Uuid(), nullable=True),
            sa.Column("actor_type", sa.String(20), nullable=False, server_default="system"),
            sa.Column("actor_id", sa.Uuid(), nullable=True),
            sa.Column("stripe_event_id", sa.String(255), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
            ),
        )
        op.create_index(
            "idx_subscription_event_org",
            "subscription_events",
            ["organization_id", "created_at"],
        )
        op.create_index(
            "idx_subscription_event_type",
            "subscription_events",
            ["subscription_id", "event_type"],
        )

    # ---- processed_stripe_events ----
    if not _has_table("processed_stripe_events"):
        op.create_table(
            "processed_stripe_events",
            sa.Column("stripe_event_id", sa.String(255), primary_key=True),
            sa.Column("event_type", sa.String(100), nullable=False),
            sa.Column(
                "processed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
            ),
        )

    # ---- trial_grants ----
    if not _has_table("trial_grants"):
        op.create_table(
            "trial_grants",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "organization_id",
                sa.Uuid(),
                sa.ForeignKey("organizations.id"),
                nullable=False,
            ),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("email_domain", sa.String(255), nullable=False),
            sa.Column("signup_ip", sa.String(64), nullable=True),
            sa.Column(
                "granted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
            ),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("converted", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index("ix_trial_grants_user_id", "trial_grants", ["user_id"])
        op.create_index("ix_trial_grants_email_domain", "trial_grants", ["email_domain"])

    # ---- organization_entitlements ----
    if not _has_table("organization_entitlements"):
        op.create_table(
            "organization_entitlements",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "organization_id",
                sa.Uuid(),
                sa.ForeignKey("organizations.id"),
                nullable=False,
                unique=True,
            ),
            sa.Column("overrides", sa.JSON(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
            ),
            sa.Column(
                "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
            ),
        )

    # Backfill trial grants for trials that already exist, so an in-flight
    # trial user is not handed a second one the moment this ships.
    op.execute(
        """
        INSERT INTO trial_grants (id, organization_id, user_id, email_domain,
                                  granted_at, expires_at, converted)
        SELECT s.id, s.organization_id, m.user_id,
               lower(split_part(u.email, '@', 2)),
               COALESCE(s.trial_start, s.created_at),
               COALESCE(s.trial_end, s.current_period_end),
               false
          FROM subscriptions s
          JOIN organization_members m ON m.organization_id = s.organization_id
                                     AND m.role = 'owner'
          JOIN users u ON u.id = m.user_id
         WHERE s.source = 'trial'
           AND NOT EXISTS (SELECT 1 FROM trial_grants g WHERE g.id = s.id)
        """
        if is_postgres
        else "SELECT 1"
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    for table in (
        "organization_entitlements",
        "trial_grants",
        "processed_stripe_events",
        "subscription_events",
    ):
        if _has_table(table):
            op.drop_table(table)

    if is_postgres and _has_index("subscriptions", ONE_LIVE_SUB_INDEX):
        op.execute(f"DROP INDEX {ONE_LIVE_SUB_INDEX}")

    for name in (
        "idx_subscription_grace_sweep",
        "idx_subscription_period_sweep",
        "idx_subscription_trial_sweep",
    ):
        if _has_index("subscriptions", name):
            op.drop_index(name, table_name="subscriptions")

    for column in (
        "current_period_emails",
        "current_period_sms",
        "scheduled_plan_id",
        "cancel_at_period_end",
        "trial_converted_at",
        "expired_at",
        "grace_period_end",
        "source",
    ):
        if _has_column("subscriptions", column):
            op.drop_column("subscriptions", column)

    if _has_index("subscription_plans", "ix_subscription_plans_slug"):
        op.drop_index("ix_subscription_plans_slug", table_name="subscription_plans")

    for column in (
        "is_trialable",
        "trial_days",
        "entitlements",
        "stripe_price_id_yearly",
        "tier",
        "slug",
    ):
        if _has_column("subscription_plans", column):
            op.drop_column("subscription_plans", column)
