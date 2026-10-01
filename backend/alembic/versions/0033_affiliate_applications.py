"""affiliates: requests to join the program, sent from the public form

Revision ID: 0033_affiliate_applications
Revises: 0032_document_files
Create Date: 2026-10-01

Affiliates used to be created by staff only. ``affiliate_applications`` holds
requests from the public "Affiliate Program" form; staff review one and create
the affiliate from it with the normal form, which fills ``affiliate_id``.

Guarded so it is safe on a database ``create_all`` already built.
"""
from alembic import op
import sqlalchemy as sa


revision = "0033_affiliate_applications"
down_revision = "0032_document_files"
branch_labels = None
depends_on = None


def _tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "affiliate_applications" in _tables():
        return
    op.create_table(
        "affiliate_applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("affiliate_id", sa.Uuid(), sa.ForeignKey("affiliates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_affiliate_applications_email", "affiliate_applications", ["email"])
    op.create_index("ix_affiliate_applications_status", "affiliate_applications", ["status"])
    op.create_index("ix_affiliate_applications_created_at", "affiliate_applications", ["created_at"])


def downgrade() -> None:
    if "affiliate_applications" in _tables():
        op.drop_table("affiliate_applications")
