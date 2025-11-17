"""Add analytics tables

Revision ID: 001_analytics
Revises:
Create Date: 2025-11-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_analytics'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create call_metrics table
    op.create_table(
        'call_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metric_date', sa.Date(), nullable=False),
        sa.Column('granularity', sa.String(20), nullable=False, server_default='daily'),
        sa.Column('hour', sa.Integer(), nullable=True),

        # Volume metrics
        sa.Column('total_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('abandoned_calls', sa.Integer(), nullable=False, server_default='0'),

        # Duration metrics
        sa.Column('total_duration', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_duration', sa.Numeric(10, 2), nullable=True),
        sa.Column('min_duration', sa.Integer(), nullable=True),
        sa.Column('max_duration', sa.Integer(), nullable=True),

        # Quality metrics
        sa.Column('avg_sentiment', sa.Numeric(3, 2), nullable=True),
        sa.Column('success_rate', sa.Numeric(5, 2), nullable=True),

        # Cost metrics
        sa.Column('total_cost', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('llm_cost', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('telephony_cost', sa.Numeric(10, 2), nullable=False, server_default='0'),

        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),

        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
    )

    # Create indexes for call_metrics
    op.create_index('idx_call_metrics_org_date', 'call_metrics', ['organization_id', 'metric_date'])
    op.create_index('idx_call_metrics_agent_date', 'call_metrics', ['agent_id', 'metric_date'])
    op.create_index('idx_call_metrics_granularity', 'call_metrics', ['granularity'])

    # Create agent_metrics table
    op.create_table(
        'agent_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_date', sa.Date(), nullable=False),

        # Performance metrics
        sa.Column('total_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_response_time', sa.Integer(), nullable=True),
        sa.Column('avg_sentiment', sa.Numeric(3, 2), nullable=True),
        sa.Column('success_rate', sa.Numeric(5, 2), nullable=True),

        # Function metrics
        sa.Column('total_function_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_function_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_function_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_function_latency', sa.Integer(), nullable=True),

        # LLM metrics
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('llm_cost', sa.Numeric(10, 2), nullable=False, server_default='0'),

        # Knowledge base metrics
        sa.Column('kb_queries', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('kb_hits', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_relevance_score', sa.Numeric(3, 2), nullable=True),

        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),

        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
    )

    # Create indexes for agent_metrics
    op.create_index('idx_agent_metrics_org_date', 'agent_metrics', ['organization_id', 'metric_date'])
    op.create_index('idx_agent_metrics_agent_date', 'agent_metrics', ['agent_id', 'metric_date'])

    # Create integration_metrics table
    op.create_table(
        'integration_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('integration_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_date', sa.Date(), nullable=False),

        # Execution metrics
        sa.Column('total_executions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_executions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_executions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_execution_time', sa.Integer(), nullable=True),

        # API metrics
        sa.Column('total_api_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_api_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_response_time', sa.Integer(), nullable=True),

        # Health metrics
        sa.Column('health_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('uptime_percentage', sa.Numeric(5, 2), nullable=True),
        sa.Column('error_rate', sa.Numeric(5, 2), nullable=True),

        # Usage metrics
        sa.Column('data_transferred', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('rate_limit_hits', sa.Integer(), nullable=False, server_default='0'),

        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),

        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['integration_id'], ['integration_connections.id'], ondelete='CASCADE'),
    )

    # Create indexes for integration_metrics
    op.create_index('idx_integration_metrics_org_date', 'integration_metrics', ['organization_id', 'metric_date'])
    op.create_index('idx_integration_metrics_int_date', 'integration_metrics', ['integration_id', 'metric_date'])

    # Create daily_summary table
    op.create_table(
        'daily_summary',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('summary_date', sa.Date(), nullable=False),

        # Call summary
        sa.Column('total_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_duration', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_duration', sa.Numeric(10, 2), nullable=True),
        sa.Column('success_rate', sa.Numeric(5, 2), nullable=True),
        sa.Column('total_cost', sa.Numeric(10, 2), nullable=False, server_default='0'),

        # Agent summary
        sa.Column('active_agents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_agent_sentiment', sa.Numeric(3, 2), nullable=True),
        sa.Column('total_function_calls', sa.Integer(), nullable=False, server_default='0'),

        # Integration summary
        sa.Column('active_integrations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_workflow_executions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_integration_health', sa.Numeric(5, 2), nullable=True),

        # Trends (percentage change from previous day)
        sa.Column('calls_trend', sa.Numeric(5, 2), nullable=True),
        sa.Column('duration_trend', sa.Numeric(5, 2), nullable=True),
        sa.Column('cost_trend', sa.Numeric(5, 2), nullable=True),
        sa.Column('success_rate_trend', sa.Numeric(5, 2), nullable=True),

        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),

        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )

    # Create indexes for daily_summary
    op.create_index('idx_daily_summary_org_date', 'daily_summary', ['organization_id', 'summary_date'])
    op.create_index('idx_daily_summary_date', 'daily_summary', ['summary_date'])

    # Create realtime_metrics table
    op.create_table(
        'realtime_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Current activity
        sa.Column('active_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('calls_last_hour', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('calls_last_5min', sa.Integer(), nullable=False, server_default='0'),

        # Performance
        sa.Column('avg_response_time', sa.Integer(), nullable=True),
        sa.Column('error_rate', sa.Numeric(5, 2), nullable=True),

        # System health
        sa.Column('system_health', sa.String(20), nullable=False, server_default='healthy'),
        sa.Column('active_agents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active_integrations', sa.Integer(), nullable=False, server_default='0'),

        # Metadata
        sa.Column('last_updated', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),

        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )

    # Create indexes for realtime_metrics
    op.create_index('idx_realtime_metrics_org', 'realtime_metrics', ['organization_id'])

    # Create metrics_cache table
    op.create_table(
        'metrics_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cache_key', sa.String(255), nullable=False),
        sa.Column('cache_value', postgresql.JSONB(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),

        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )

    # Create indexes for metrics_cache
    op.create_index('idx_metrics_cache_org_key', 'metrics_cache', ['organization_id', 'cache_key'], unique=True)
    op.create_index('idx_metrics_cache_expires', 'metrics_cache', ['expires_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_metrics_cache_expires', table_name='metrics_cache')
    op.drop_index('idx_metrics_cache_org_key', table_name='metrics_cache')
    op.drop_table('metrics_cache')

    op.drop_index('idx_realtime_metrics_org', table_name='realtime_metrics')
    op.drop_table('realtime_metrics')

    op.drop_index('idx_daily_summary_date', table_name='daily_summary')
    op.drop_index('idx_daily_summary_org_date', table_name='daily_summary')
    op.drop_table('daily_summary')

    op.drop_index('idx_integration_metrics_int_date', table_name='integration_metrics')
    op.drop_index('idx_integration_metrics_org_date', table_name='integration_metrics')
    op.drop_table('integration_metrics')

    op.drop_index('idx_agent_metrics_agent_date', table_name='agent_metrics')
    op.drop_index('idx_agent_metrics_org_date', table_name='agent_metrics')
    op.drop_table('agent_metrics')

    op.drop_index('idx_call_metrics_granularity', table_name='call_metrics')
    op.drop_index('idx_call_metrics_agent_date', table_name='call_metrics')
    op.drop_index('idx_call_metrics_org_date', table_name='call_metrics')
    op.drop_table('call_metrics')
