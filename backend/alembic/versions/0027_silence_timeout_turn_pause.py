"""silence_timeout becomes the real end-of-turn pause; move the old default

Revision ID: 0027_silence_timeout_turn_pause
Revises: 0026_stt_keywords
Create Date: 2026-09-29

`agents.silence_timeout` was saved from the agent editor ("How long to wait
after the caller stops speaking before responding") but never used for that:
speech recognition ran on hardcoded pauses (300ms on calls, 700ms in the
browser test), and the only readers clamped it up to 15 seconds for an idle
check-in, so no slider position changed anything.

It now drives Deepgram's end-of-turn pause on both paths. At the old default
of 3000ms every agent would wait three seconds before answering, so rows still
on that untouched default move to the new default of 1000ms. Any other value
was chosen by someone and is kept; values above the editor's new 5s ceiling
are brought down to it.

Downgrade is a no-op: the previous values had no effect, so there is nothing
meaningful to restore.
"""
from alembic import op
import sqlalchemy as sa

revision = "0027_silence_timeout_turn_pause"
down_revision = "0026_stt_keywords"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "agents" not in insp.get_table_names():
        return
    op.execute("UPDATE agents SET silence_timeout = 1000 WHERE silence_timeout = 3000")
    op.execute("UPDATE agents SET silence_timeout = 5000 WHERE silence_timeout > 5000")


def downgrade() -> None:
    pass
