"""add_tools_table

Revision ID: 0002_add_tools_table
Revises: 3692b80d76f5
Create Date: 2026-06-02

"""
from alembic import op
import sqlalchemy as sa

revision = '0002_add_tools_table'
down_revision = '3692b80d76f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tools',
        sa.Column('id', sa.String(32), nullable=False),
        sa.Column('user_id', sa.String(32), nullable=False),
        sa.Column('organization_id', sa.String(32), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tool_type', sa.String(50), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_tools_user_id', 'tools', ['user_id'])
    op.create_index('idx_tools_tool_type', 'tools', ['tool_type'])

    op.create_table(
        'agent_tool_assignments',
        sa.Column('id', sa.String(32), nullable=False),
        sa.Column('agent_id', sa.String(32), nullable=False),
        sa.Column('tool_id', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_id', 'tool_id', name='uq_agent_tool'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_id'], ['tools.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_agent_tool_agent_id', 'agent_tool_assignments', ['agent_id'])
    op.create_index('idx_agent_tool_tool_id', 'agent_tool_assignments', ['tool_id'])


def downgrade() -> None:
    op.drop_table('agent_tool_assignments')
    op.drop_table('tools')
