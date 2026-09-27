"""daily summaries: unique per organization and day, not per day

Revision ID: 0023_daily_summary_per_org
Revises: 0022_integration_changes
Create Date: 2026-09-26

``daily_summaries.summary_date`` was unique on its own, so the first
organization to open the analytics dashboard on a given day claimed that
date and every other organization's insert failed with a unique violation:
``GET /analytics/dashboard`` returned 500 for them for the rest of the day,
and the nightly aggregation stopped after the first organization.

Guarded like 0022 so it is safe on a database whose tables ``create_all``
built, and on one where the constraint has already been fixed.
"""
from alembic import op
import sqlalchemy as sa


revision = "0023_daily_summary_per_org"
down_revision = "0022_integration_changes"
branch_labels = None
depends_on = None

_TABLE = "daily_summaries"
_NEW = "uq_daily_summary_org_date"


def _unique_constraints() -> dict | None:
    """Column tuple → constraint name, or None when the table doesn't exist."""
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return None
    return {
        tuple(c["column_names"]): c["name"]
        for c in inspector.get_unique_constraints(_TABLE)
    }


def upgrade() -> None:
    constraints = _unique_constraints()
    if constraints is None:
        return
    old = constraints.get(("summary_date",))
    if old:
        op.drop_constraint(old, _TABLE, type_="unique")
    if ("organization_id", "summary_date") not in constraints:
        op.create_unique_constraint(_NEW, _TABLE, ["organization_id", "summary_date"])


def downgrade() -> None:
    # Restoring the old single-column constraint would fail as soon as two
    # organizations have a summary for the same day, and would bring the bug
    # back; only the new constraint is removed.
    if ("organization_id", "summary_date") in (_unique_constraints() or {}):
        op.drop_constraint(_NEW, _TABLE, type_="unique")
