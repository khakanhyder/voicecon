"""add bio column to users

Revision ID: 0009_add_user_bio
Revises: 0008_add_oauth_fields
Create Date: 2026-07-23

Adds a free-text ``bio`` column to the users table, backing the Profile
settings page. Idempotent so it runs cleanly on both a fresh DB and a dev DB
where Base.metadata.create_all already applied the model change.
"""
from alembic import op
import sqlalchemy as sa

revision = '0009_add_user_bio'
down_revision = '0008_add_oauth_fields'
branch_labels = None
depends_on = None


def _columns(table: str) -> set:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c['name'] for c in insp.get_columns(table)}


def upgrade() -> None:
    if 'bio' not in _columns('users'):
        op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))


def downgrade() -> None:
    if 'bio' in _columns('users'):
        op.drop_column('users', 'bio')
