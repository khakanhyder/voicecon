"""chat inbox for the mobile app: human replies, unread, push devices

Revision ID: 0038_chat_mobile_inbox
Revises: 0037_blog
Create Date: 2026-10-07

* ``chat_sessions.mode`` (ai | human), ``unread_count``,
  ``last_message_preview`` / ``last_message_role`` — the inbox list and
  team-member takeover. Existing conversations get their preview backfilled.
* ``chat_messages.sender_user_id`` — who wrote a ``human`` reply.
* ``device_tokens`` — phones registered for push notifications.

Guarded so it is safe on a database ``create_all`` already built, and safe to
rerun after a partial failure.
"""
from alembic import op
import sqlalchemy as sa


revision = "0038_chat_mobile_inbox"
down_revision = "0037_blog"
branch_labels = None
depends_on = None


def _tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set:
    return {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    cols = _columns("chat_sessions")
    if "mode" not in cols:
        op.add_column("chat_sessions", sa.Column("mode", sa.String(10), nullable=False, server_default="ai"))
    if "unread_count" not in cols:
        op.add_column("chat_sessions", sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"))
    if "last_message_preview" not in cols:
        op.add_column("chat_sessions", sa.Column("last_message_preview", sa.String(300), nullable=True))
    if "last_message_role" not in cols:
        op.add_column("chat_sessions", sa.Column("last_message_role", sa.String(20), nullable=True))

    if "sender_user_id" not in _columns("chat_messages"):
        op.add_column("chat_messages", sa.Column("sender_user_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            "fk_chat_messages_sender_user_id", "chat_messages", "users",
            ["sender_user_id"], ["id"], ondelete="SET NULL",
        )

    if "device_tokens" not in _tables():
        op.create_table(
            "device_tokens",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token", sa.String(512), nullable=False),
            sa.Column("platform", sa.String(20), nullable=False),
            sa.Column("device_name", sa.String(255), nullable=True),
            sa.Column("app_version", sa.String(50), nullable=True),
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        )
    indexes = _indexes("device_tokens")
    if "ix_device_tokens_token" not in indexes:
        op.create_index("ix_device_tokens_token", "device_tokens", ["token"], unique=True)
    if "ix_device_tokens_user_id" not in indexes:
        op.create_index("ix_device_tokens_user_id", "device_tokens", ["user_id"])

    # Conversations from before this migration: show their newest message in
    # the inbox list instead of a blank line.
    op.execute(
        """
        UPDATE chat_sessions SET
          last_message_preview = (
            SELECT substr(m.content, 1, 300) FROM chat_messages m
            WHERE m.session_id = chat_sessions.id
            ORDER BY m.created_at DESC LIMIT 1),
          last_message_role = (
            SELECT m.role FROM chat_messages m
            WHERE m.session_id = chat_sessions.id
            ORDER BY m.created_at DESC LIMIT 1)
        WHERE last_message_preview IS NULL
        """
    )


def downgrade() -> None:
    if "device_tokens" in _tables():
        op.drop_table("device_tokens")
    if "sender_user_id" in _columns("chat_messages"):
        op.drop_constraint("fk_chat_messages_sender_user_id", "chat_messages", type_="foreignkey")
        op.drop_column("chat_messages", "sender_user_id")
    cols = _columns("chat_sessions")
    for name in ("last_message_role", "last_message_preview", "unread_count", "mode"):
        if name in cols:
            op.drop_column("chat_sessions", name)
