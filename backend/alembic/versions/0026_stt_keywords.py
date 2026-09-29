"""add per-agent STT keyword/keyterm biasing list

Revision ID: 0026_stt_keywords
Revises: 0025_standalone_chatbots
Create Date: 2026-09-29

Deepgram has no way to know a caller's name, a product name, or any other
out-of-vocabulary word matters more than usual — Pakistani names like "Asad
Ali" arrived transcribed as "a sad alley" with no way for the agent owner to
correct it (M11 in the 29 Sep QA report). `stt_keywords` lets an agent supply
a short list of terms Deepgram should bias toward (passed as `keyterm` on
nova-3 or `keywords` on nova-2/nova/enhanced/base).

Idempotent: skips the column a dev DB already has from Base.metadata.create_all.
"""
from alembic import op
import sqlalchemy as sa

revision = "0026_stt_keywords"
down_revision = "0025_standalone_chatbots"
branch_labels = None
depends_on = None

TABLE = "agents"


def _columns() -> set:
    insp = sa.inspect(op.get_bind())
    if TABLE not in insp.get_table_names():
        return set()
    return {col["name"] for col in insp.get_columns(TABLE)}


def upgrade() -> None:
    columns = _columns()
    if not columns:
        # agents does not exist yet; create_all will build it with the new
        # column already present.
        return

    if "stt_keywords" not in columns:
        op.add_column(
            TABLE,
            sa.Column("stt_keywords", sa.JSON(), nullable=True),
        )
        op.execute(f"UPDATE {TABLE} SET stt_keywords = '[]' WHERE stt_keywords IS NULL")


def downgrade() -> None:
    columns = _columns()
    if "stt_keywords" in columns:
        op.drop_column(TABLE, "stt_keywords")
