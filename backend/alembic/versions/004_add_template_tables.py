"""Add template marketplace tables

Revision ID: 004
Revises: 003
Create Date: 2024-01-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create agent_templates table
    op.create_table(
        'agent_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('long_description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('version', sa.String(length=50), nullable=False, server_default='1.0.0'),
        sa.Column('agent_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('first_message', sa.Text(), nullable=True),
        sa.Column('functions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('icon', sa.String(length=500), nullable=True),
        sa.Column('banner_image', sa.String(length=500), nullable=True),
        sa.Column('screenshots', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('author_name', sa.String(length=255), nullable=False),
        sa.Column('author_organization', sa.String(length=255), nullable=True),
        sa.Column('is_official', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_free', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('install_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_rating', sa.Numeric(precision=3, scale=2), nullable=False, server_default='0.0'),
        sa.Column('review_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('customizable_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('required_integrations', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('setup_guide', sa.Text(), nullable=True),
        sa.Column('use_cases', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('demo_url', sa.String(length=500), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('idx_agent_template_category', 'agent_templates', ['category'])
    op.create_index('idx_agent_template_status', 'agent_templates', ['status'])
    op.create_index('idx_agent_template_featured', 'agent_templates', ['is_featured'])
    op.create_index('idx_agent_template_slug', 'agent_templates', ['slug'])

    # Create workflow_templates table
    op.create_table(
        'workflow_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('long_description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('version', sa.String(length=50), nullable=False, server_default='1.0.0'),
        sa.Column('workflow_definition', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('trigger_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('icon', sa.String(length=500), nullable=True),
        sa.Column('banner_image', sa.String(length=500), nullable=True),
        sa.Column('screenshots', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('author_name', sa.String(length=255), nullable=False),
        sa.Column('author_organization', sa.String(length=255), nullable=True),
        sa.Column('is_official', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_free', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('install_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_rating', sa.Numeric(precision=3, scale=2), nullable=False, server_default='0.0'),
        sa.Column('review_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('required_integrations', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('compatible_agents', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('setup_guide', sa.Text(), nullable=True),
        sa.Column('use_cases', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('idx_workflow_template_category', 'workflow_templates', ['category'])
    op.create_index('idx_workflow_template_status', 'workflow_templates', ['status'])
    op.create_index('idx_workflow_template_slug', 'workflow_templates', ['slug'])

    # Create template_installations table
    op.create_table(
        'template_installations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('workflow_template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('installed_version', sa.String(length=50), nullable=False),
        sa.Column('customizations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_workflow_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('uninstalled_at', sa.DateTime(), nullable=True),
        sa.Column('installation_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('installed_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_template_id'], ['agent_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_template_id'], ['workflow_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_agent_id'], ['agents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_workflow_id'], ['workflows.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_installation_org', 'template_installations', ['organization_id'])
    op.create_index('idx_installation_agent', 'template_installations', ['agent_template_id'])
    op.create_index('idx_installation_workflow', 'template_installations', ['workflow_template_id'])

    # Create template_reviews table
    op.create_table(
        'template_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('workflow_template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('review_text', sa.Text(), nullable=True),
        sa.Column('verified_installation', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('helpful_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_approved', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_flagged', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('moderation_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_template_id'], ['agent_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_template_id'], ['workflow_templates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_review_agent', 'template_reviews', ['agent_template_id'])
    op.create_index('idx_review_workflow', 'template_reviews', ['workflow_template_id'])
    op.create_index('idx_review_user', 'template_reviews', ['user_id'])
    op.create_index('idx_review_approved', 'template_reviews', ['is_approved'])

    # Create template_versions table
    op.create_table(
        'template_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('workflow_template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('changelog', sa.Text(), nullable=False),
        sa.Column('config_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_breaking_change', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('migration_guide', sa.Text(), nullable=True),
        sa.Column('released_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['agent_template_id'], ['agent_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_template_id'], ['workflow_templates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_version_agent', 'template_versions', ['agent_template_id'])
    op.create_index('idx_version_workflow', 'template_versions', ['workflow_template_id'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_version_workflow', table_name='template_versions')
    op.drop_index('idx_version_agent', table_name='template_versions')
    op.drop_table('template_versions')

    op.drop_index('idx_review_approved', table_name='template_reviews')
    op.drop_index('idx_review_user', table_name='template_reviews')
    op.drop_index('idx_review_workflow', table_name='template_reviews')
    op.drop_index('idx_review_agent', table_name='template_reviews')
    op.drop_table('template_reviews')

    op.drop_index('idx_installation_workflow', table_name='template_installations')
    op.drop_index('idx_installation_agent', table_name='template_installations')
    op.drop_index('idx_installation_org', table_name='template_installations')
    op.drop_table('template_installations')

    op.drop_index('idx_workflow_template_slug', table_name='workflow_templates')
    op.drop_index('idx_workflow_template_status', table_name='workflow_templates')
    op.drop_index('idx_workflow_template_category', table_name='workflow_templates')
    op.drop_table('workflow_templates')

    op.drop_index('idx_agent_template_slug', table_name='agent_templates')
    op.drop_index('idx_agent_template_featured', table_name='agent_templates')
    op.drop_index('idx_agent_template_status', table_name='agent_templates')
    op.drop_index('idx_agent_template_category', table_name='agent_templates')
    op.drop_table('agent_templates')
