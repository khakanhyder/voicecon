"""Add subscription and billing tables

Revision ID: 003
Revises: 002
Create Date: 2024-01-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002_knowledge_base'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create subscription_plans table
    op.create_table(
        'subscription_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('stripe_product_id', sa.String(length=255), nullable=False),
        sa.Column('stripe_price_id', sa.String(length=255), nullable=False),
        sa.Column('price_monthly', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('price_yearly', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='usd'),
        sa.Column('included_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('included_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_agents', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('max_phone_numbers', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('max_knowledge_bases', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('overage_rate_per_minute', sa.Numeric(precision=10, scale=4), nullable=False, server_default='0.015'),
        sa.Column('overage_rate_per_call', sa.Numeric(precision=10, scale=4), nullable=False, server_default='0.05'),
        sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_product_id'),
        sa.UniqueConstraint('stripe_price_id')
    )

    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('billing_period', sa.String(length=20), nullable=False, server_default='monthly'),
        sa.Column('current_period_start', sa.DateTime(), nullable=False),
        sa.Column('current_period_end', sa.DateTime(), nullable=False),
        sa.Column('trial_start', sa.DateTime(), nullable=True),
        sa.Column('trial_end', sa.DateTime(), nullable=True),
        sa.Column('canceled_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('current_period_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_period_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plans.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_subscription_id')
    )
    op.create_index('idx_subscription_org', 'subscriptions', ['organization_id'])
    op.create_index('idx_subscription_status', 'subscriptions', ['status'])
    op.create_index('idx_subscription_stripe', 'subscriptions', ['stripe_subscription_id'])

    # Create usage_records table
    op.create_table(
        'usage_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('usage_type', sa.String(length=50), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('stripe_usage_record_id', sa.String(length=255), nullable=True),
        sa.Column('reported_to_stripe', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_usage_subscription', 'usage_records', ['subscription_id'])
    op.create_index('idx_usage_org', 'usage_records', ['organization_id'])
    op.create_index('idx_usage_period', 'usage_records', ['period_start', 'period_end'])
    op.create_index('idx_usage_type', 'usage_records', ['usage_type'])

    # Create invoices table
    op.create_table(
        'invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stripe_invoice_id', sa.String(length=255), nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=False),
        sa.Column('invoice_number', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('amount_due', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('amount_paid', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('amount_remaining', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('tax', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('total', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='usd'),
        sa.Column('invoice_pdf', sa.String(length=500), nullable=True),
        sa.Column('hosted_invoice_url', sa.String(length=500), nullable=True),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('payment_intent_id', sa.String(length=255), nullable=True),
        sa.Column('charge_id', sa.String(length=255), nullable=True),
        sa.Column('line_items', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('attempted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('next_payment_attempt', sa.DateTime(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_invoice_id')
    )
    op.create_index('idx_invoice_subscription', 'invoices', ['subscription_id'])
    op.create_index('idx_invoice_org', 'invoices', ['organization_id'])
    op.create_index('idx_invoice_status', 'invoices', ['status'])
    op.create_index('idx_invoice_stripe', 'invoices', ['stripe_invoice_id'])

    # Create payment_failures table
    op.create_table(
        'payment_failures',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('failure_code', sa.String(length=100), nullable=True),
        sa.Column('failure_message', sa.Text(), nullable=False),
        sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True),
        sa.Column('stripe_charge_id', sa.String(length=255), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('customer_notified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('admin_notified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_payment_failure_invoice', 'payment_failures', ['invoice_id'])
    op.create_index('idx_payment_failure_resolved', 'payment_failures', ['resolved'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_payment_failure_resolved', table_name='payment_failures')
    op.drop_index('idx_payment_failure_invoice', table_name='payment_failures')
    op.drop_table('payment_failures')

    op.drop_index('idx_invoice_stripe', table_name='invoices')
    op.drop_index('idx_invoice_status', table_name='invoices')
    op.drop_index('idx_invoice_org', table_name='invoices')
    op.drop_index('idx_invoice_subscription', table_name='invoices')
    op.drop_table('invoices')

    op.drop_index('idx_usage_type', table_name='usage_records')
    op.drop_index('idx_usage_period', table_name='usage_records')
    op.drop_index('idx_usage_org', table_name='usage_records')
    op.drop_index('idx_usage_subscription', table_name='usage_records')
    op.drop_table('usage_records')

    op.drop_index('idx_subscription_stripe', table_name='subscriptions')
    op.drop_index('idx_subscription_status', table_name='subscriptions')
    op.drop_index('idx_subscription_org', table_name='subscriptions')
    op.drop_table('subscriptions')

    op.drop_table('subscription_plans')
