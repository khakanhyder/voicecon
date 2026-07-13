"""add embedding column to document_chunks

Revision ID: 0004_add_chunk_embedding
Revises: 0003_add_api_key_encrypted
Create Date: 2026-07-13

Stores each chunk's vector in-row (JSON array) so knowledge-base semantic search
is DB-backed and survives restarts, with no external vector store required.
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_add_chunk_embedding'
down_revision = '0003_add_api_key_encrypted'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('document_chunks', sa.Column('embedding', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('document_chunks', 'embedding')
