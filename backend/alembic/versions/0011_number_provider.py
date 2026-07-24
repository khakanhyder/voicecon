"""track which carrier connection a phone number was bought on

Revision ID: 0011_number_provider
Revises: 0010_invites_notifs
Create Date: 2026-07-24

Phone numbers can now be purchased from any connected carrier (Twilio, Telnyx)
rather than only the server's Twilio account. Two columns record which carrier
account a number came from so releases and webhook updates go back to the right
place:

- integration_connection_id: the carrier integration used at purchase time
- provider_metadata: carrier-specific bookkeeping (e.g. Telnyx order id and
  TeXML application id)

Idempotent: skips columns a dev DB already has from Base.metadata.create_all.

Note: the revision id is kept short (<=32 chars) to fit alembic_version.version_num.
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_number_provider"
down_revision = "0010_invites_notifs"
branch_labels = None
depends_on = None

TABLE = "phone_numbers"


def _columns() -> set:
    insp = sa.inspect(op.get_bind())
    if TABLE not in insp.get_table_names():
        return set()
    return {col["name"] for col in insp.get_columns(TABLE)}


def upgrade() -> None:
    columns = _columns()
    if not columns:
        # phone_numbers does not exist yet; create_all will build it with the
        # new columns already present.
        return

    if "integration_connection_id" not in columns:
        op.add_column(
            TABLE,
            sa.Column(
                "integration_connection_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("integration_connections.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    if "provider_metadata" not in columns:
        op.add_column(
            TABLE,
            sa.Column("provider_metadata", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    columns = _columns()

    if "provider_metadata" in columns:
        op.drop_column(TABLE, "provider_metadata")

    if "integration_connection_id" in columns:
        op.drop_column(TABLE, "integration_connection_id")
