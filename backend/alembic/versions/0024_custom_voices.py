"""custom voices: a workspace's own provider voices

Revision ID: 0024_custom_voices
Revises: 0023_daily_summary_per_org
Create Date: 2026-09-28

Workspaces can add voices from their own TTS provider account (ElevenLabs
cloned voices, for one) to a voice library and pick them for agents. A row
optionally holds the customer's provider key, encrypted.

Guarded like 0020 so it is safe on a database ``create_all`` already built.
"""
from alembic import op
import sqlalchemy as sa


revision = "0024_custom_voices"
down_revision = "0023_daily_summary_per_org"
branch_labels = None
depends_on = None


def _tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "custom_voices" in _tables():
        return
    op.create_table(
        "custom_voices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("voice_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "provider", "voice_id", name="uq_custom_voice_org_provider_voice"
        ),
    )
    op.create_index("ix_custom_voices_organization_id", "custom_voices", ["organization_id"])


def downgrade() -> None:
    if "custom_voices" in _tables():
        op.drop_table("custom_voices")
