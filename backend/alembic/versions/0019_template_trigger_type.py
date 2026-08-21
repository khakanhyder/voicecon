"""add workflow_templates.trigger_type so a template can be installed

Revision ID: 0019_template_trigger_type
Revises: 0018_user_token_version
Create Date: 2026-08-21

Installing a workflow template has to set two columns on the new workflow:
``trigger_type`` and ``trigger_config``. The template table only carried the
second, so the type had to be guessed — and a config on its own does not say
which one it belongs to. ``{"filters": {}}`` is equally valid for
``call_started`` and ``call_completed``; ``{}`` is valid for four of the six.

Existing rows default to ``manual``, which needs no configuration and cannot
fire on its own. That is the safe reading for a row whose intended trigger is
unknown: an installed workflow that waits to be run beats one that starts
firing on a schedule nobody chose.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0019_template_trigger_type"
down_revision = "0018_user_token_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default is required rather than cosmetic: the column is NOT NULL
    # and the table may already hold seeded templates, so without it the ALTER
    # fails on any database that has been seeded.
    op.add_column(
        "workflow_templates",
        sa.Column(
            "trigger_type",
            sa.String(length=100),
            nullable=False,
            server_default="manual",
        ),
    )


def downgrade() -> None:
    # Installs fall back to guessing the trigger type again.
    op.drop_column("workflow_templates", "trigger_type")
