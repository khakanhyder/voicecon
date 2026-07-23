"""add call summary column

Revision ID: 0007_add_call_summary
Revises: 0006_add_chat_widget
Create Date: 2026-07-22

Adds `summary` (Text) to the `calls` table: an AI-generated recap of the
conversation, surfaced on the call-detail page and the analytics caller view.
"""
from alembic import op
import sqlalchemy as sa

revision = '0007_add_call_summary'
down_revision = '0006_add_chat_widget'
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return table in insp.get_table_names() and column in {
        c['name'] for c in insp.get_columns(table)
    }


def upgrade() -> None:
    # Idempotent: dev builds this column via Base.metadata.create_all.
    if not _has_column('calls', 'summary'):
        op.add_column('calls', sa.Column('summary', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('calls', 'summary')
