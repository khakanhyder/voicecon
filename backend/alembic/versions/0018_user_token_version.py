"""add users.token_version so sessions can be revoked

Revision ID: 0018_user_token_version
Revises: 0017_trial_length_30d
Create Date: 2026-08-20

A JWT cannot be withdrawn once signed, so until now nothing could end a session
early. ``POST /auth/logout`` returned a message and did nothing, and — the part
that actually mattered — changing or resetting a password left every token
already issued for the account valid for up to 30 days. Someone responding to a
compromise by resetting their password did not evict the attacker.

``token_version`` fixes that with one integer. Every token records the value the
account held when it was issued; the value is compared on each request and on
refresh, so incrementing it invalidates everything outstanding. Logout, password
change and password reset all increment it.

Deploying this does **not** sign anyone out. Existing tokens predate the claim
and are read as version 0, which is the default this migration backfills — so
they keep working until their owner does something that revokes them.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0018_user_token_version"
down_revision = "0017_trial_length_30d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default is required, not cosmetic: the table has rows, and the
    # column is NOT NULL. Without it the ALTER fails on any non-empty database.
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    # Dropping this re-enables the tokens it was invalidating: anything issued
    # before a logout or password reset becomes acceptable again, because the
    # claim no longer has anything to be checked against.
    op.drop_column("users", "token_version")
