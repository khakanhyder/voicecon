"""platform admin: staff flag, operator settings, admin audit log

Revision ID: 0020_platform_admin
Revises: 0019_template_trigger_type
Create Date: 2026-09-21

Adds what the platform admin dashboard stands on:

* ``users.is_platform_admin`` — Voicecon staff, separate from workspace roles.
* ``subscription_plans.admin_managed`` — stops the startup backfill in
  ``seed_plans`` from re-syncing a plan an admin has edited.
* ``platform_settings`` — provider keys and tunables set from the dashboard,
  overriding the environment variable of the same name.
* ``admin_audit_logs`` — who changed what, and when.

Every step is guarded so the migration is safe to re-run on a database where
``create_all`` (dev, ``DEBUG=true``) has already built some of it.
"""
from alembic import op
import sqlalchemy as sa


revision = "0020_platform_admin"
down_revision = "0019_template_trigger_type"
branch_labels = None
depends_on = None


def _columns(table: str) -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "is_platform_admin" not in _columns("users"):
        op.add_column(
            "users",
            sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if "admin_managed" not in _columns("subscription_plans"):
        op.add_column(
            "subscription_plans",
            sa.Column("admin_managed", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    tables = _tables()

    if "platform_settings" not in tables:
        op.create_table(
            "platform_settings",
            sa.Column("key", sa.String(length=100), primary_key=True),
            sa.Column("value", sa.Text(), nullable=True),
            sa.Column("value_encrypted", sa.Text(), nullable=True),
            sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("hint", sa.String(length=16), nullable=True),
            sa.Column("updated_by", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if "admin_audit_logs" not in tables:
        op.create_table(
            "admin_audit_logs",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("actor_id", sa.Uuid(), nullable=True),
            sa.Column("actor_email", sa.String(length=255), nullable=True),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("target_type", sa.String(length=50), nullable=True),
            sa.Column("target_id", sa.String(length=100), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_admin_audit_logs_actor_id", "admin_audit_logs", ["actor_id"])
        op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])
        op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"])
        op.create_index("idx_admin_audit_target", "admin_audit_logs", ["target_type", "target_id"])


def downgrade() -> None:
    tables = _tables()
    if "admin_audit_logs" in tables:
        op.drop_table("admin_audit_logs")
    if "platform_settings" in tables:
        op.drop_table("platform_settings")
    if "admin_managed" in _columns("subscription_plans"):
        op.drop_column("subscription_plans", "admin_managed")
    if "is_platform_admin" in _columns("users"):
        op.drop_column("users", "is_platform_admin")
