"""one-time email codes for sign-up verification and password reset

Revision ID: 0012_verification_codes
Revises: 0011_number_provider
Create Date: 2026-08-01

Sign-up now proves the email address before the account is created, and
forgotten passwords are reset with a code sent to the address. Both need a place
to keep the outstanding code, keyed by email rather than user id because
verification happens before the user exists.

Idempotent: skips the table when a dev DB already has it from
Base.metadata.create_all.

Note: the revision id is kept short (<=32 chars) to fit alembic_version.version_num.
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_verification_codes"
down_revision = "0011_number_provider"
branch_labels = None
depends_on = None

TABLE = "verification_codes"


def _has_table() -> bool:
    return TABLE in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table():
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(f"ix_{TABLE}_email", TABLE, ["email"])
    op.create_index(f"ix_{TABLE}_email_purpose", TABLE, ["email", "purpose"])


def downgrade() -> None:
    if not _has_table():
        return

    op.drop_index(f"ix_{TABLE}_email_purpose", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_email", table_name=TABLE)
    op.drop_table(TABLE)
