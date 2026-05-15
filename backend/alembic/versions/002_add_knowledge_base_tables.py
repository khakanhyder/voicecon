"""Add knowledge base tables

Revision ID: 002_knowledge_base
Revises: 001_analytics
Create Date: 2025-11-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_knowledge_base'
down_revision = '001_analytics'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create knowledge_bases table
    op.create_table(
        'knowledge_bases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('embedding_model', sa.String(100), nullable=False, server_default='text-embedding-ada-002'),
        sa.Column('chunk_size', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('chunk_overlap', sa.Integer(), nullable=False, server_default='200'),
        sa.Column('vector_dimension', sa.Integer(), nullable=False, server_default='1536'),
        sa.Column('vector_store_type', sa.String(50), nullable=False, server_default='pinecone'),
        sa.Column('vector_store_config', postgresql.JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )

    # Create indexes for knowledge_bases
    op.create_index('idx_kb_org', 'knowledge_bases', ['organization_id'])
    op.create_index('idx_kb_active', 'knowledge_bases', ['is_active'])

    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('knowledge_base_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_url', sa.String(1000), nullable=True),
        sa.Column('file_type', sa.String(50), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('language', sa.String(10), nullable=False, server_default='en'),
        sa.Column('processing_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('total_chunks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    )

    # Create indexes for documents
    op.create_index('idx_doc_kb', 'documents', ['knowledge_base_id'])
    op.create_index('idx_doc_hash', 'documents', ['content_hash'])
    op.create_index('idx_doc_status', 'documents', ['processing_status'])

    # Create document_chunks table
    op.create_table(
        'document_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('start_char', sa.Integer(), nullable=False),
        sa.Column('end_char', sa.Integer(), nullable=False),
        sa.Column('vector_id', sa.String(255), nullable=True),
        sa.Column('embedding_model', sa.String(100), nullable=False),
        sa.Column('embedding_dimension', sa.Integer(), nullable=False, server_default='1536'),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    )

    # Create indexes for document_chunks
    op.create_index('idx_chunk_doc', 'document_chunks', ['document_id'])
    op.create_index('idx_chunk_vector', 'document_chunks', ['vector_id'])
    op.create_index('idx_chunk_index', 'document_chunks', ['document_id', 'chunk_index'])

    # Create agent_knowledge_bases table
    op.create_table(
        'agent_knowledge_bases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('knowledge_base_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_results', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('min_similarity', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('auto_inject', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    )

    # Create indexes for agent_knowledge_bases
    op.create_index('idx_akb_agent', 'agent_knowledge_bases', ['agent_id'])
    op.create_index('idx_akb_kb', 'agent_knowledge_bases', ['knowledge_base_id'])
    op.create_index('idx_akb_priority', 'agent_knowledge_bases', ['agent_id', 'priority'])

    # Create search_queries table
    op.create_table(
        'search_queries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('knowledge_base_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('call_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('query_type', sa.String(50), nullable=False, server_default='semantic'),
        sa.Column('results_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('top_similarity', sa.Float(), nullable=True),
        sa.Column('avg_similarity', sa.Float(), nullable=True),
        sa.Column('result_chunk_ids', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('query_duration_ms', sa.Integer(), nullable=True),
        sa.Column('was_helpful', sa.Boolean(), nullable=True),
        sa.Column('user_feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['call_id'], ['calls.id'], ondelete='SET NULL'),
    )

    # Create indexes for search_queries
    op.create_index('idx_query_kb', 'search_queries', ['knowledge_base_id'])
    op.create_index('idx_query_agent', 'search_queries', ['agent_id'])
    op.create_index('idx_query_call', 'search_queries', ['call_id'])
    op.create_index('idx_query_created', 'search_queries', ['created_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_query_created', table_name='search_queries')
    op.drop_index('idx_query_call', table_name='search_queries')
    op.drop_index('idx_query_agent', table_name='search_queries')
    op.drop_index('idx_query_kb', table_name='search_queries')
    op.drop_table('search_queries')

    op.drop_index('idx_akb_priority', table_name='agent_knowledge_bases')
    op.drop_index('idx_akb_kb', table_name='agent_knowledge_bases')
    op.drop_index('idx_akb_agent', table_name='agent_knowledge_bases')
    op.drop_table('agent_knowledge_bases')

    op.drop_index('idx_chunk_index', table_name='document_chunks')
    op.drop_index('idx_chunk_vector', table_name='document_chunks')
    op.drop_index('idx_chunk_doc', table_name='document_chunks')
    op.drop_table('document_chunks')

    op.drop_index('idx_doc_status', table_name='documents')
    op.drop_index('idx_doc_hash', table_name='documents')
    op.drop_index('idx_doc_kb', table_name='documents')
    op.drop_table('documents')

    op.drop_index('idx_kb_active', table_name='knowledge_bases')
    op.drop_index('idx_kb_org', table_name='knowledge_bases')
    op.drop_table('knowledge_bases')
