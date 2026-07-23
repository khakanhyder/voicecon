"""add oauth fields to users

Revision ID: 0008_add_oauth_fields
Revises: 0007_add_call_summary
Create Date: 2026-07-22

Adds social-login support to the users table:
  - hashed_password becomes NULLABLE (social users have no local password)
  - auth_provider ("email" | "google" | "apple")
  - google_id / apple_id (stable per-provider subject ids, indexed)

Idempotent so it runs cleanly on both a fresh DB and a dev DB where
Base.metadata.create_all already applied the model changes.
"""
from alembic import op
import sqlalchemy as sa

revision = '0008_add_oauth_fields'
down_revision = '0007_add_call_summary'
branch_labels = None
depends_on = None


def _columns(table: str) -> set:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c['name'] for c in insp.get_columns(table)}


def _indexes(table: str) -> set:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {ix['name'] for ix in insp.get_indexes(table)}


def upgrade() -> None:
    cols = _columns('users')

    if 'auth_provider' not in cols:
        op.add_column(
            'users',
            sa.Column('auth_provider', sa.String(20), nullable=False, server_default='email'),
        )
    if 'google_id' not in cols:
        op.add_column('users', sa.Column('google_id', sa.String(255), nullable=True))
    if 'apple_id' not in cols:
        op.add_column('users', sa.Column('apple_id', sa.String(255), nullable=True))

    idx = _indexes('users')
    if 'ix_users_google_id' not in idx:
        op.create_index('ix_users_google_id', 'users', ['google_id'])
    if 'ix_users_apple_id' not in idx:
        op.create_index('ix_users_apple_id', 'users', ['apple_id'])

    # Relax the NOT NULL on hashed_password for social-only accounts.
    op.alter_column('users', 'hashed_password', existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    op.drop_index('ix_users_apple_id', table_name='users')
    op.drop_index('ix_users_google_id', table_name='users')
    op.drop_column('users', 'apple_id')
    op.drop_column('users', 'google_id')
    op.drop_column('users', 'auth_provider')
    # Note: leaving hashed_password nullable on downgrade is intentional — any
    # social users created meanwhile would violate a re-imposed NOT NULL.
