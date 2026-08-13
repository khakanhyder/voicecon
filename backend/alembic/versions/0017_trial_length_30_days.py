"""lengthen the free trial from 7 to 30 days

Revision ID: 0017_trial_length_30d
Revises: 0016_backfill_call_timing
Create Date: 2026-08-13

``subscription_plans.trial_days`` was seeded at 7. Trial length is a product
decision that lives in ``app.services.billing.catalog.DEFAULT_TRIAL_DAYS``, and
the startup backfill re-syncs every plan to it — but a deployment reads the
column before that runs, so the value is corrected here too.

Only the old default is rewritten: a plan an operator has since set to some
other length is left alone by this migration (the startup backfill still brings
it in line, which is where a deliberate per-plan length would have to be
reconsidered).

In-flight trials keep the ``trial_end`` they were granted — this changes what
new trials get, not what existing ones already promised.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0017_trial_length_30d"
down_revision = "0016_backfill_call_timing"
branch_labels = None
depends_on = None

OLD_TRIAL_DAYS = 7
NEW_TRIAL_DAYS = 30


def upgrade() -> None:
    op.alter_column(
        "subscription_plans",
        "trial_days",
        existing_type=sa.Integer(),
        existing_nullable=False,
        server_default=str(NEW_TRIAL_DAYS),
    )
    op.execute(
        sa.text(
            "UPDATE subscription_plans SET trial_days = :new WHERE trial_days = :old"
        ).bindparams(new=NEW_TRIAL_DAYS, old=OLD_TRIAL_DAYS)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE subscription_plans SET trial_days = :old WHERE trial_days = :new"
        ).bindparams(new=NEW_TRIAL_DAYS, old=OLD_TRIAL_DAYS)
    )
    op.alter_column(
        "subscription_plans",
        "trial_days",
        existing_type=sa.Integer(),
        existing_nullable=False,
        server_default=str(OLD_TRIAL_DAYS),
    )
