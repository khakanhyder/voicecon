"""add chat widget tables

Revision ID: 0006_add_chat_widget
Revises: 0005_add_company_profiles
Create Date: 2026-07-21

Adds the chat widget channel: chat_widgets (embed key + branding per agent),
chat_sessions (a visitor conversation), and chat_messages (the turns).

These are created by Base.metadata.create_all in dev; this migration creates
them in production.
"""
from alembic import op
import sqlalchemy as sa

revision = '0006_add_chat_widget'
down_revision = '0005_add_company_profiles'
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    # Idempotent: dev builds these tables via Base.metadata.create_all.
    if not _has_table('chat_widgets'):
        _create_chat_widgets()
    if not _has_table('chat_sessions'):
        _create_chat_sessions()
    if not _has_table('chat_messages'):
        _create_chat_messages()


def _create_chat_widgets() -> None:
    op.create_table(
        'chat_widgets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('agent_id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('public_key', sa.String(64), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('agent_id', name='uq_chat_widgets_agent_id'),
        sa.UniqueConstraint('public_key', name='uq_chat_widgets_public_key'),
    )
    op.create_index('ix_chat_widgets_agent_id', 'chat_widgets', ['agent_id'])
    op.create_index('ix_chat_widgets_public_key', 'chat_widgets', ['public_key'])
    op.create_index('ix_chat_widgets_organization_id', 'chat_widgets', ['organization_id'])


def _create_chat_sessions() -> None:
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('widget_id', sa.Uuid(), nullable=False),
        sa.Column('agent_id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('visitor_id', sa.String(128), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_activity_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['widget_id'], ['chat_widgets.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_chat_sessions_widget_id', 'chat_sessions', ['widget_id'])
    op.create_index('ix_chat_sessions_agent_id', 'chat_sessions', ['agent_id'])
    op.create_index('ix_chat_sessions_organization_id', 'chat_sessions', ['organization_id'])
    op.create_index('ix_chat_sessions_visitor_id', 'chat_sessions', ['visitor_id'])
    op.create_index('ix_chat_sessions_started_at', 'chat_sessions', ['started_at'])


def _create_chat_messages() -> None:
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tool_name', sa.String(128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])
    op.create_index('ix_chat_messages_created_at', 'chat_messages', ['created_at'])


def downgrade() -> None:
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
    op.drop_table('chat_widgets')
