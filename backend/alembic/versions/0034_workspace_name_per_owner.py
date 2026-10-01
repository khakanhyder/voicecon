"""workspaces: one active workspace per name per owner

Revision ID: 0034_workspace_name_per_owner
Revises: 0033_affiliate_applications
Create Date: 2026-10-01

The API refuses a second active workspace with the same name for the same
owner (case-insensitive). This adds the index that makes that true under
concurrent requests too. Another owner may still use the same name.

Guarded: a database that already holds such duplicates would fail the
CREATE UNIQUE INDEX and take the whole deploy with it. In that case the index is
skipped, the duplicates are logged for someone to rename, and the API check
still applies to every new or renamed workspace. Rerunning after the duplicates
are fixed (``alembic downgrade -1 && alembic upgrade head``) creates it.
"""
import logging

from alembic import op
import sqlalchemy as sa


revision = "0034_workspace_name_per_owner"
down_revision = "0033_affiliate_applications"
branch_labels = None
depends_on = None

INDEX = "uq_organizations_owner_name_active"
logger = logging.getLogger("alembic.runtime.migration")


def _has_index() -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(ix["name"] == INDEX for ix in inspector.get_indexes("organizations"))


def upgrade() -> None:
    if _has_index():
        return

    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            "SELECT owner_id, lower(trim(name)) AS n, count(*) AS c "
            "FROM organizations WHERE is_active "
            "GROUP BY owner_id, lower(trim(name)) HAVING count(*) > 1"
        )
    ).fetchall()
    if duplicates:
        logger.warning(
            "Skipping %s: %d owner/name pairs already have duplicate active "
            "workspaces (first: owner %s, name %r). Rename them, then rerun.",
            INDEX, len(duplicates), duplicates[0][0], duplicates[0][1],
        )
        return

    op.execute(
        sa.text(
            f"CREATE UNIQUE INDEX {INDEX} ON organizations "
            "(owner_id, lower(trim(name))) WHERE is_active"
        )
    )


def downgrade() -> None:
    if _has_index():
        op.drop_index(INDEX, table_name="organizations")
