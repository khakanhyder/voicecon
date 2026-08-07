"""backfill call start times and normalize carrier status strings

Revision ID: 0016_backfill_call_timing
Revises: 0015_subscription_ent
Create Date: 2026-08-07

Repairs rows written before the telephony webhooks were fixed:

* ``started_at`` was only ever set by a ``ringing`` status callback, which
  Twilio does not send for inbound numbers and which could arrive before an
  outbound row carried its SID. Every existing call therefore had it NULL,
  which the UI rendered as the epoch — "Jan 1, 1970". ``created_at`` is the
  best available stand-in: the row is written as the call arrives.
* ``status`` stored the carrier's string verbatim, so Twilio's hyphenated
  ``in-progress`` never matched the canonical ``in_progress`` used by the
  calls filter and the active-call analytics query.

Both statements are idempotent and safe to re-run.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0016_backfill_call_timing"
down_revision = "0015_subscription_ent"
branch_labels = None
depends_on = None


#: Carrier status -> canonical status. Mirrors ``_PROVIDER_CALL_STATUS`` in
#: app.api.v1.endpoints.telephony; keep the two in step.
_STATUS_FIXES = {
    "in-progress": "in_progress",
    "queued": "initiated",
    "answered": "in_progress",
    "no-answer": "missed",
    "no_answer": "missed",
    "busy": "missed",
    "canceled": "failed",
    "cancelled": "failed",
}


def upgrade() -> None:
    op.execute(
        "UPDATE calls SET started_at = created_at WHERE started_at IS NULL"
    )

    for carrier_value, canonical in _STATUS_FIXES.items():
        op.execute(
            f"UPDATE calls SET status = '{canonical}' WHERE status = '{carrier_value}'"
        )

    # A completed call with both ends known but no duration can be reconstructed.
    op.execute(
        """
        UPDATE calls
           SET duration_seconds = GREATEST(
                   0,
                   CAST(EXTRACT(EPOCH FROM (ended_at - COALESCE(answered_at, started_at))) AS INTEGER)
               )
         WHERE duration_seconds IS NULL
           AND ended_at IS NOT NULL
           AND COALESCE(answered_at, started_at) IS NOT NULL
           AND ended_at > COALESCE(answered_at, started_at)
        """
    )


    # Price the carrier leg for the rows we just gave a duration, using the same
    # rate table the status webhook applies. `cost_total` is a reporting figure
    # (analytics only — no billing path reads it), so this keeps the calls list
    # from showing a duration next to an empty cost.
    op.execute(
        """
        UPDATE calls
           SET cost_telephony = ROUND(
                   CAST(duration_seconds AS NUMERIC) / 60
                   * CASE WHEN direction = 'inbound' THEN 0.0085 ELSE 0.0140 END,
                   4
               )
         WHERE cost_telephony IS NULL
           AND duration_seconds IS NOT NULL
           AND duration_seconds > 0
        """
    )
    op.execute(
        """
        UPDATE calls
           SET cost_total = ROUND(
                   COALESCE(cost_stt, 0) + COALESCE(cost_llm, 0)
                   + COALESCE(cost_tts, 0) + COALESCE(cost_telephony, 0),
                   4
               )
         WHERE cost_total IS NULL
           AND cost_telephony IS NOT NULL
        """
    )

    # Mirrors the webhook: what we charge for is what we measured.
    op.execute(
        """
        UPDATE calls
           SET billable_duration_seconds = duration_seconds
         WHERE billable_duration_seconds IS NULL
           AND duration_seconds IS NOT NULL
        """
    )


def downgrade() -> None:
    # A backfill of missing values; the previous state was "unknown", which is
    # not something to restore. Statuses are left canonical on purpose.
    pass
