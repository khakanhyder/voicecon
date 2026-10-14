"""Pricing review (2026-10-14): new per-minute rates and the premium multiplier

Revision ID: 0041_pricing_review
Revises: 0039_call_billed_amount
Create Date: 2026-10-14

* Pay As You Go: $0.35 -> $0.29 per minute.
* Overage: Starter 0.30 -> 0.25, Growth 0.25 -> 0.22, Scale 0.20 -> 0.19,
  Agency 0.15 -> 0.17.

A plan is only moved when its rate is still the old default, so a rate a
platform admin set by hand in /admin/plans is left as it is. The ``premium``
section (minutes on a flagship model count 1.5x) is added by the startup
backfill, ``seed_plans._fill_missing_keys``, like any new catalogue key.

New rates apply to calls that end after the upgrade; nothing already charged
changes.
"""
import json
from decimal import Decimal

from alembic import op
import sqlalchemy as sa


revision = "0041_pricing_review"
down_revision = "0039_call_billed_amount"
branch_labels = None
depends_on = None

#: slug -> (old rate, new rate)
OVERAGE = {
    "starter": ("0.30", "0.25"),
    "growth": ("0.25", "0.22"),
    "scale": ("0.20", "0.19"),
    "agency": ("0.15", "0.17"),
}
PAYG = ("payg", "0.35", "0.29")


def _load(value):
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def _same(a, b) -> bool:
    try:
        return Decimal(str(a)).quantize(Decimal("0.0001")) == Decimal(str(b)).quantize(Decimal("0.0001"))
    except Exception:
        return False


def _move(direction: str) -> None:
    bind = op.get_bind()
    if "subscription_plans" not in set(sa.inspect(bind).get_table_names()):
        return
    rows = bind.execute(
        sa.text("SELECT id, slug, overage_rate_per_minute, entitlements FROM subscription_plans")
    ).fetchall()
    for row in rows:
        doc = _load(row.entitlements)
        if not isinstance(doc, dict):
            continue
        changed = False
        column = None

        if row.slug in OVERAGE:
            old, new = OVERAGE[row.slug]
            src, dst = (old, new) if direction == "up" else (new, old)
            overage = dict(doc.get("overage") or {})
            if "per_minute" in overage and _same(overage["per_minute"], src):
                overage["per_minute"] = float(dst)
                doc["overage"] = overage
                changed = True
            if _same(row.overage_rate_per_minute, src):
                column = dst
        elif row.slug == PAYG[0]:
            _, old, new = PAYG
            src, dst = (old, new) if direction == "up" else (new, old)
            billing = dict(doc.get("billing") or {})
            # A document without the key reads the catalogue default, which the
            # code change already moved.
            if "per_minute" in billing and _same(billing["per_minute"], src):
                billing["per_minute"] = float(dst)
                doc["billing"] = billing
                changed = True
            if _same(row.overage_rate_per_minute, src):
                column = dst

        if changed:
            bind.execute(
                sa.text("UPDATE subscription_plans SET entitlements = :doc WHERE id = :id"),
                {"doc": json.dumps(doc), "id": row.id},
            )
        if column is not None:
            bind.execute(
                sa.text("UPDATE subscription_plans SET overage_rate_per_minute = :rate WHERE id = :id"),
                {"rate": Decimal(column), "id": row.id},
            )


def upgrade() -> None:
    _move("up")


def downgrade() -> None:
    _move("down")
