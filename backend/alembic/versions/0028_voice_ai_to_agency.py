"""move every Voice AI subscription onto the Agency plan

Revision ID: 0028_voice_ai_to_agency
Revises: 0027_silence_timeout_turn_pause
Create Date: 2026-09-30

Voice AI was retired by the 29 Sep 2026 pricing change (Starter, Growth,
Scale, Agency). Its subscribers were left on the retired row so nothing broke;
at the owner's request they now move to Agency, the plan that includes
everything Voice AI did. Every status moves — live trials, staff comps and
lapsed accounts — so an expired account is offered Agency, not a plan that can
no longer be bought. Queued downgrades that pointed at Voice AI now point at
Agency.

Two cases are deliberately left alone:

* **Subscriptions a payment provider bills** (Stripe or Polar) that are still
  live. Changing the local plan would not change what the provider charges,
  and the provider's next webhook would move the plan back. Those need a real
  plan change (``POST /billing/subscription/change-plan``). Voice AI never had
  a Stripe or Polar product in production, so this is expected to be empty;
  the count is printed either way.
* **A database without both plans.** The Agency row is created by the app's
  startup seeding, which runs after migrations, so on a fresh database there
  is nothing to move and this is a no-op.

Each move writes a ``plan_migrated`` subscription event (from/to plan ids), so
the history shows why the plan changed and the downgrade moves back exactly
those subscriptions.
"""
import uuid
from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = "0028_voice_ai_to_agency"
down_revision = "0027_silence_timeout_turn_pause"
branch_labels = None
depends_on = None

FROM_SLUG = "voice-ai"
TO_SLUG = "agency"
EVENT = "plan_migrated"
PROVIDER_SOURCES = ("stripe", "polar")
LIVE_STATUSES = ("trialing", "active", "past_due", "grace")


def _plan_id(bind, slug):
    return bind.execute(
        sa.text("SELECT id FROM subscription_plans WHERE slug = :slug"), {"slug": slug}
    ).scalar()


def _ready(bind) -> bool:
    tables = set(sa.inspect(bind).get_table_names())
    return {"subscription_plans", "subscriptions", "subscription_events"} <= tables


def upgrade() -> None:
    bind = op.get_bind()
    if not _ready(bind):
        return
    old_id = _plan_id(bind, FROM_SLUG)
    new_id = _plan_id(bind, TO_SLUG)
    if old_id is None or new_id is None:
        print(f"0028: '{FROM_SLUG}' or '{TO_SLUG}' plan not found; nothing to move")
        return

    rows = bind.execute(
        sa.text(
            "SELECT id, organization_id, status, source FROM subscriptions "
            "WHERE plan_id = :old"
        ),
        {"old": old_id},
    ).fetchall()

    skipped = [
        r for r in rows if r.source in PROVIDER_SOURCES and r.status in LIVE_STATUSES
    ]
    moving = [r for r in rows if r not in skipped]

    now = datetime.utcnow()
    for r in moving:
        bind.execute(
            sa.text("UPDATE subscriptions SET plan_id = :new, updated_at = :now WHERE id = :id"),
            {"new": new_id, "now": now, "id": r.id},
        )
        bind.execute(
            sa.text(
                "INSERT INTO subscription_events "
                "(id, organization_id, subscription_id, event_type, from_status, to_status, "
                " from_plan_id, to_plan_id, actor_type, payload, created_at) "
                "VALUES (:id, :org, :sub, :event, :status, :status, :old, :new, 'system', "
                " CAST(:payload AS JSON), :now)"
            ),
            {
                "id": str(uuid.uuid4()),
                "org": r.organization_id,
                "sub": r.id,
                "event": EVENT,
                "status": r.status,
                "old": old_id,
                "new": new_id,
                "payload": '{"reason": "Voice AI retired; moved to Agency (migration 0028)"}',
                "now": now,
            },
        )

    rescheduled = bind.execute(
        sa.text(
            "UPDATE subscriptions SET scheduled_plan_id = :new WHERE scheduled_plan_id = :old"
        ),
        {"new": new_id, "old": old_id},
    ).rowcount

    print(
        f"0028: moved {len(moving)} subscription(s) from {FROM_SLUG} to {TO_SLUG}; "
        f"repointed {rescheduled} queued plan change(s); "
        f"left {len(skipped)} provider-billed subscription(s) for a real plan change"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _ready(bind):
        return
    old_id = _plan_id(bind, FROM_SLUG)
    new_id = _plan_id(bind, TO_SLUG)
    if old_id is None or new_id is None:
        return
    # Only subscriptions this migration moved and nobody has moved since.
    bind.execute(
        sa.text(
            "UPDATE subscriptions SET plan_id = :old "
            "WHERE plan_id = :new AND id IN ("
            "  SELECT subscription_id FROM subscription_events "
            "  WHERE event_type = :event AND from_plan_id = :old AND to_plan_id = :new)"
        ),
        {"old": old_id, "new": new_id, "event": EVENT},
    )
    bind.execute(
        sa.text(
            "DELETE FROM subscription_events "
            "WHERE event_type = :event AND from_plan_id = :old AND to_plan_id = :new"
        ),
        {"old": old_id, "new": new_id, "event": EVENT},
    )
