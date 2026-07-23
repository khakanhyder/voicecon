"""add invitations and notifications tables

Revision ID: 0010_invites_notifs
Revises: 0009_add_user_bio
Create Date: 2026-07-24

Adds the team-invitation flow (pending invites addressed by email + token) and
in-app notifications (header bell). Idempotent: skips tables/indexes that a dev
DB already has from Base.metadata.create_all.

Note: the revision id is kept short (<=32 chars) to fit alembic_version.version_num.
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_invites_notifs"
down_revision = "0009_add_user_bio"
branch_labels = None
depends_on = None


def _tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table: str) -> set:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {ix["name"] for ix in insp.get_indexes(table)}


def upgrade() -> None:
    tables = _tables()

    if "invitations" not in tables:
        op.create_table(
            "invitations",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column(
                "organization_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=50), nullable=False, server_default="member"),
            sa.Column("token", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("invited_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("invited_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("responded_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_invitations_organization_id", "invitations", ["organization_id"])
        op.create_index("ix_invitations_email", "invitations", ["email"])
        op.create_index("ix_invitations_token", "invitations", ["token"], unique=True)
        op.create_index("ix_invitations_status", "invitations", ["status"])

    if "notifications" not in tables:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("type", sa.String(length=50), nullable=False, server_default="info"),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("data", sa.JSON(), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_actioned", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
        op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
        op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    tables = _tables()
    if "notifications" in tables:
        op.drop_table("notifications")
    if "invitations" in tables:
        op.drop_table("invitations")
