"""add api_key_encrypted to integration_connections

Revision ID: 0003_add_api_key_encrypted
Revises: 0002_add_tools_table
Create Date: 2026-07-13

The integration manager stores API-key credentials in
integration_connections.api_key_encrypted, but the column was never created,
so every API-key connection attempt failed. This adds it.
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_add_api_key_encrypted'
down_revision = '0002_add_tools_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'integration_connections',
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('integration_connections', 'api_key_encrypted')
