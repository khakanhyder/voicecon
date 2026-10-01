"""knowledge base: keep the original uploaded file for preview and download

Revision ID: 0032_document_files
Revises: 0031_affiliate_billing_periods
Create Date: 2026-10-01

Uploads used to keep only the extracted text, so "Download" handed back a .txt
of a PDF. ``document_files`` holds the uploaded bytes, one row per document,
removed with the document by ``ON DELETE CASCADE``. Documents uploaded before
this have no row and keep previewing/downloading as extracted text.

Guarded so it is safe on a database ``create_all`` already built.
"""
from alembic import op
import sqlalchemy as sa


revision = "0032_document_files"
down_revision = "0031_affiliate_billing_periods"
branch_labels = None
depends_on = None


def _tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "document_files" in _tables():
        return
    op.create_table(
        "document_files",
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    if "document_files" in _tables():
        op.drop_table("document_files")
