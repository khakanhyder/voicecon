"""integration changes: audit of updates and deletes made in connected apps

Revision ID: 0022_integration_changes
Revises: 0021_polar_billing
Create Date: 2026-09-24

Agents and workflows can now reschedule and cancel appointments (and, later,
update or delete records in other apps). Each such change is recorded in
``integration_changes`` with the call or workflow that made it and a snapshot
of the record from just before.

Guarded like 0020 so it is safe on a database ``create_all`` already built.
"""
from alembic import op
import sqlalchemy as sa


revision = "0022_integration_changes"
down_revision = "0021_polar_billing"
branch_labels = None
depends_on = None


def _tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "integration_changes" in _tables():
        return
    op.create_table(
        "integration_changes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("connector_slug", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("record_id", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("tool_id", sa.Uuid(), nullable=True),
        sa.Column("call_id", sa.String(length=255), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_integration_changes_organization_id", "integration_changes", ["organization_id"])
    op.create_index("ix_integration_changes_connection_id", "integration_changes", ["connection_id"])
    op.create_index("ix_integration_changes_call_id", "integration_changes", ["call_id"])
    op.create_index("ix_integration_changes_created_at", "integration_changes", ["created_at"])


def downgrade() -> None:
    if "integration_changes" in _tables():
        op.drop_table("integration_changes")
