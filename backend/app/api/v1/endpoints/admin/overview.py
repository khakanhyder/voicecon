"""Platform-wide KPIs for the admin landing page."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import runtime_settings
from app.core.admin import require_platform_admin
from app.core.config import settings
from app.database import get_db
from app.models.agent import Agent
from app.models.call import Call, PhoneNumber
from app.models.integration import IntegrationConnection, WorkflowExecution
from app.models.subscription import PaymentFailure
from app.models.user import Organization, User

from ._common import iso, latest_subscriptions, plans_by_id, subscription_view, utcnow

router = APIRouter()

CHART_DAYS = 14


async def _scalar(db: AsyncSession, query) -> int:
    return int((await db.execute(query)).scalar() or 0)


def _as_date(value) -> date:
    """``func.date`` returns a date on Postgres and a string on SQLite."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _daily(rows, start: date, days: int, key: str) -> List[Dict[str, Any]]:
    """One entry per day from ``start``, zero-filled. Rows are (day, count[, seconds])."""
    by_day = {_as_date(row[0]): row for row in rows}
    out = []
    for i in range(days):
        day = start + timedelta(days=i)
        row = by_day.get(day)
        entry: Dict[str, Any] = {"date": day.isoformat(), key: int(row[1]) if row else 0}
        if key == "calls":
            entry["minutes"] = round(float(row[2] or 0) / 60, 1) if row else 0
        out.append(entry)
    return out


def provider_summary() -> List[Dict[str, Any]]:
    """Which platform integrations have their required credential in place."""
    required = {
        "openai": ["OPENAI_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "deepgram": ["DEEPGRAM_API_KEY"],
        "elevenlabs": ["ELEVENLABS_API_KEY"],
        "twilio": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"],
        "stripe": ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"],
        "email": [],
        "storage": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_S3_BUCKET"],
    }
    out = []
    for group in runtime_settings.GROUPS:
        if group.id not in required:
            continue
        if group.id == "email":
            configured = settings.resolved_email_provider != "console"
        elif group.id == "stripe":
            # Same test checkout applies: a placeholder key counts as missing.
            configured = settings.stripe_configured and bool(settings.STRIPE_WEBHOOK_SECRET)
        else:
            configured = all(getattr(settings, k, None) for k in required[group.id])
        out.append({"id": group.id, "label": group.label, "configured": configured})
    return out


@router.get("/overview")
async def overview(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    now = utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    chart_start = (now - timedelta(days=CHART_DAYS - 1)).date()
    chart_start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=CHART_DAYS - 1)

    users_total = await _scalar(db, select(func.count(User.id)).where(User.deleted_at.is_(None)))
    users_new_7d = await _scalar(db, select(func.count(User.id)).where(User.created_at >= week_ago))
    orgs_total = await _scalar(db, select(func.count(Organization.id)))
    orgs_suspended = await _scalar(db, select(func.count(Organization.id)).where(Organization.is_active.is_(False)))
    agents_total = await _scalar(db, select(func.count(Agent.id)).where(Agent.deleted_at.is_(None)))
    numbers_active = await _scalar(db, select(func.count(PhoneNumber.id)).where(PhoneNumber.status == "active"))
    calls_24h = await _scalar(db, select(func.count(Call.id)).where(Call.created_at >= day_ago))
    calls_30d = await _scalar(db, select(func.count(Call.id)).where(Call.created_at >= month_ago))
    failed_calls_24h = await _scalar(
        db,
        select(func.count(Call.id)).where(
            Call.created_at >= day_ago, Call.status.in_(("failed", "busy", "no-answer", "no_answer", "error"))
        ),
    )
    seconds_30d = await _scalar(
        db, select(func.coalesce(func.sum(Call.duration_seconds), 0)).where(Call.created_at >= month_ago)
    )
    open_payment_failures = await _scalar(
        db, select(func.count(PaymentFailure.id)).where(PaymentFailure.resolved.is_(False))
    )
    expired_connections = await _scalar(
        db,
        select(func.count(IntegrationConnection.id)).where(
            IntegrationConnection.status.in_(("expired", "error")), IntegrationConnection.is_active.is_(True)
        ),
    )
    failed_runs_24h = await _scalar(
        db,
        select(func.count(WorkflowExecution.id)).where(
            WorkflowExecution.started_at >= day_ago, WorkflowExecution.status == "failed"
        ),
    )

    # Subscription mix and recurring revenue, from each org's current row.
    plans = await plans_by_id(db)
    latest = await latest_subscriptions(db)
    status_counts: Counter = Counter()
    mrr = Decimal("0")
    for sub in latest.values():
        view = subscription_view(sub, plans, now)
        status_counts[view["status"]] += 1
        plan = plans.get(sub.plan_id)
        if plan and view["status"] in ("active", "past_due") and sub.source == "stripe":
            if sub.billing_period == "yearly" and plan.price_yearly:
                mrr += Decimal(plan.price_yearly) / 12
            else:
                mrr += Decimal(plan.price_monthly or 0)
    no_subscription = max(0, orgs_total - len(latest))

    day_col = func.date(Call.created_at)
    call_rows = (
        await db.execute(
            select(day_col, func.count(Call.id), func.coalesce(func.sum(Call.duration_seconds), 0))
            .where(Call.created_at >= chart_start_dt)
            .group_by(day_col)
        )
    ).all()
    signup_col = func.date(User.created_at)
    signup_rows = (
        await db.execute(
            select(signup_col, func.count(User.id)).where(User.created_at >= chart_start_dt).group_by(signup_col)
        )
    ).all()

    # Newest workspaces, with owner and plan, for the "recent sign-ups" list.
    recent = (
        await db.execute(
            select(Organization, User)
            .join(User, User.id == Organization.owner_id)
            .order_by(Organization.created_at.desc())
            .limit(8)
        )
    ).all()
    recent_latest = await latest_subscriptions(db, [o.id for o, _ in recent])

    return {
        "kpis": {
            "users_total": users_total,
            "users_new_7d": users_new_7d,
            "organizations_total": orgs_total,
            "organizations_suspended": orgs_suspended,
            "agents_total": agents_total,
            "phone_numbers_active": numbers_active,
            "calls_24h": calls_24h,
            "calls_30d": calls_30d,
            "failed_calls_24h": failed_calls_24h,
            "minutes_30d": round(seconds_30d / 60, 1),
            "mrr": float(round(mrr, 2)),
            "open_payment_failures": open_payment_failures,
            "broken_connections": expired_connections,
            "failed_workflow_runs_24h": failed_runs_24h,
        },
        "subscriptions": {**dict(status_counts), "none": no_subscription},
        "calls_daily": _daily(call_rows, chart_start, CHART_DAYS, "calls"),
        "signups_daily": _daily(signup_rows, chart_start, CHART_DAYS, "users"),
        "recent_organizations": [
            {
                "id": str(org.id),
                "name": org.name,
                "is_active": org.is_active,
                "created_at": iso(org.created_at),
                "owner": {"id": str(owner.id), "email": owner.email, "full_name": owner.full_name},
                "subscription": subscription_view(recent_latest.get(org.id), plans, now),
            }
            for org, owner in recent
        ],
        "providers": provider_summary(),
        "generated_at": iso(now),
    }
