"""accounts: deactivation with a recovery window before permanent deletion

Revision ID: 0035_account_deactivation
Revises: 0034_workspace_name_per_owner
Create Date: 2026-10-01

Deactivating an account used to set ``users.deleted_at`` straight away, which is
also what a permanently deleted (tombstoned) account has — so the two could not
be told apart, and a deactivated account was hidden from the admin console that
was supposed to restore it.

This separates them:

- ``users.deactivated_at`` / ``users.deletion_scheduled_at`` — the customer
  closed their account; it is recoverable until the scheduled date.
- ``users.deleted_at`` — now only ever means permanently deleted.
- ``organizations.owner_deactivated_at`` — the workspace was switched off with
  its owner's account, so reactivating the account knows what to bring back.

Accounts deactivated under the old behaviour are moved into the new state and
given a full retention period from the day this runs, rather than being deleted
on the first sweep after deploy.

Every step is guarded, so rerunning after a partial failure is safe.
"""
from datetime import datetime, timedelta

from alembic import op
import sqlalchemy as sa


revision = "0035_account_deactivation"
down_revision = "0034_workspace_name_per_owner"
branch_labels = None
depends_on = None

INDEX = "ix_users_deletion_scheduled_at"
#: Matches config.ACCOUNT_DELETION_RETENTION_DAYS. Hard-coded: a migration must
#: not change behaviour when a setting is edited later.
LEGACY_RETENTION_DAYS = 30
#: What a permanently deleted account's email is replaced with.
TOMBSTONE = "deleted-%@deleted.invalid"


def _columns(table: str) -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _has_index() -> bool:
    return any(ix["name"] == INDEX for ix in sa.inspect(op.get_bind()).get_indexes("users"))


def upgrade() -> None:
    users = _columns("users")
    if "deactivated_at" not in users:
        op.add_column("users", sa.Column("deactivated_at", sa.DateTime(), nullable=True))
    if "deletion_scheduled_at" not in users:
        op.add_column("users", sa.Column("deletion_scheduled_at", sa.DateTime(), nullable=True))
    if not _has_index():
        op.create_index(INDEX, "users", ["deletion_scheduled_at"])
    if "owner_deactivated_at" not in _columns("organizations"):
        op.add_column("organizations", sa.Column("owner_deactivated_at", sa.DateTime(), nullable=True))

    bind = op.get_bind()
    legacy = bind.execute(
        sa.text(
            "SELECT id, deleted_at FROM users "
            "WHERE deleted_at IS NOT NULL AND deactivated_at IS NULL "
            "AND email NOT LIKE :tombstone"
        ),
        {"tombstone": TOMBSTONE},
    ).fetchall()
    scheduled = datetime.utcnow() + timedelta(days=LEGACY_RETENTION_DAYS)
    for user_id, deactivated_at in legacy:
        bind.execute(
            sa.text(
                "UPDATE users SET deactivated_at = :at, deletion_scheduled_at = :scheduled, "
                "deleted_at = NULL WHERE id = :id"
            ),
            {"at": deactivated_at, "scheduled": scheduled, "id": user_id},
        )
        # The old code stamped the workspace with the same instant as the user,
        # which is the only record of which workspaces went down with the
        # account (as opposed to ones the owner had deleted earlier).
        bind.execute(
            sa.text(
                "UPDATE organizations SET owner_deactivated_at = :at "
                "WHERE owner_id = :id AND is_active = false AND updated_at = :at"
            ),
            {"at": deactivated_at, "id": user_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    users = _columns("users")
    if "deactivated_at" in users:
        # Back to the old meaning, so a deactivated account stays unable to sign in.
        bind.execute(
            sa.text(
                "UPDATE users SET deleted_at = deactivated_at "
                "WHERE deactivated_at IS NOT NULL AND deleted_at IS NULL"
            )
        )
    if _has_index():
        op.drop_index(INDEX, table_name="users")
    if "deletion_scheduled_at" in users:
        op.drop_column("users", "deletion_scheduled_at")
    if "deactivated_at" in users:
        op.drop_column("users", "deactivated_at")
    if "owner_deactivated_at" in _columns("organizations"):
        op.drop_column("organizations", "owner_deactivated_at")
