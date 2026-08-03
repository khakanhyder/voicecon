"""track which workspace each user is currently working inside

Revision ID: 0013_active_workspace
Revises: 0012_verification_codes
Create Date: 2026-08-03

A user can belong to several organizations (their own, plus any they were
invited to). Without a stored choice, request scoping fell back to whichever
membership the database returned first, so an invited teammate could land in
their personal workspace instead of the shared one — and had no way to switch.

``users.active_organization_id`` records the workspace they last switched to.
It is nullable and self-healing: app.core.workspace re-derives a default when it
is empty or points at a workspace they no longer belong to.

No foreign key: organizations.owner_id already references users, so an FK here
would close a cycle that forces ALTER-based create/drop. The value is validated
against organization_members on every request anyway, which also catches a
membership that was revoked without the workspace going away.

Backfill: every existing user is pointed at the workspace they own, falling back
to their earliest membership — the same deterministic default the resolver uses,
so behaviour before and after the migration matches.

Idempotent: skips the column when a dev DB already has it from
Base.metadata.create_all.

Note: the revision id is kept short (<=32 chars) to fit alembic_version.version_num.
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_active_workspace"
down_revision = "0012_verification_codes"
branch_labels = None
depends_on = None

TABLE = "users"
COLUMN = "active_organization_id"
INDEX_NAME = "ix_users_active_organization_id"


def _has_column() -> bool:
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return False
    return COLUMN in {c["name"] for c in inspector.get_columns(TABLE)}


def upgrade() -> None:
    if _has_column():
        return

    op.add_column(TABLE, sa.Column(COLUMN, sa.Uuid(as_uuid=True), nullable=True))
    op.create_index(INDEX_NAME, TABLE, [COLUMN])

    # Owned workspace first, else the earliest membership.
    op.execute(
        """
        UPDATE users AS u
        SET active_organization_id = m.organization_id
        FROM (
            SELECT DISTINCT ON (user_id)
                   user_id, organization_id
            FROM organization_members
            ORDER BY user_id,
                     (CASE WHEN role = 'owner' THEN 0 ELSE 1 END),
                     joined_at
        ) AS m
        WHERE m.user_id = u.id
          AND u.active_organization_id IS NULL
        """
    )


def downgrade() -> None:
    if not _has_column():
        return
    op.drop_index(INDEX_NAME, table_name=TABLE)
    op.drop_column(TABLE, COLUMN)
