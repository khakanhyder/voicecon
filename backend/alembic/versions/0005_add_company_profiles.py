"""add company_profiles table

Revision ID: 0005_add_company_profiles
Revises: 0004_add_chunk_embedding
Create Date: 2026-07-13

The company_profiles table was previously created only by
``Base.metadata.create_all`` (which runs solely when DEBUG is true), so it
never existed in production. This migration creates it properly.

"""
from alembic import op
import sqlalchemy as sa

revision = '0005_add_company_profiles'
down_revision = '0004_add_chunk_embedding'
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    # Idempotent: dev builds this table via Base.metadata.create_all.
    if _has_table('company_profiles'):
        return
    op.create_table(
        'company_profiles',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('industry_type', sa.String(100), nullable=True),
        sa.Column('company_size', sa.String(50), nullable=True),
        sa.Column('company_url', sa.String(255), nullable=True),
        sa.Column('assistant_name', sa.String(255), nullable=True),
        sa.Column('preferred_language', sa.String(50), nullable=False, server_default='English'),
        sa.Column('assistant_instructions', sa.Text(), nullable=True),
        sa.Column('phone_number', sa.String(50), nullable=True),
        sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('onboarding_step', sa.String(20), nullable=False, server_default='company'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('organization_id', name='uq_company_profiles_organization_id'),
    )
    op.create_index('idx_company_profiles_organization_id', 'company_profiles', ['organization_id'])
    op.create_index('idx_company_profiles_user_id', 'company_profiles', ['user_id'])


def downgrade() -> None:
    op.drop_table('company_profiles')
