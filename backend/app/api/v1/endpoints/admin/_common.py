"""Helpers shared by the platform-admin endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, Optional

from fastapi import HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription, SubscriptionPlan
from app.services.billing.entitlements import effective_grace_end, effective_status


def utcnow() -> datetime:
    return datetime.utcnow()


def iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def num(value: Any) -> Any:
    """JSON-friendly number from a Decimal column."""
    if isinstance(value, Decimal):
        return float(value)
    return value


def parse_uuid(raw: str, what: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown {what}")


class PageParams:
    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def paginated(items: list, total: int, params: PageParams) -> Dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "pages": max(1, -(-total // params.page_size)),
    }


def like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def plans_by_id(db: AsyncSession) -> Dict[uuid.UUID, SubscriptionPlan]:
    return {p.id: p for p in (await db.execute(select(SubscriptionPlan))).scalars().all()}


async def latest_subscriptions(
    db: AsyncSession, org_ids: Optional[Iterable[uuid.UUID]] = None
) -> Dict[uuid.UUID, Subscription]:
    """The newest subscription row per organization — the one entitlements read."""
    query = select(Subscription).order_by(Subscription.created_at.desc())
    if org_ids is not None:
        ids = list(org_ids)
        if not ids:
            return {}
        query = query.where(Subscription.organization_id.in_(ids))
    latest: Dict[uuid.UUID, Subscription] = {}
    for sub in (await db.execute(query)).scalars().all():
        latest.setdefault(sub.organization_id, sub)
    return latest


def subscription_view(
    sub: Optional[Subscription],
    plans: Dict[uuid.UUID, SubscriptionPlan],
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    if sub is None:
        return None
    now = now or utcnow()
    plan = plans.get(sub.plan_id)
    return {
        "id": str(sub.id),
        "status": effective_status(sub, now),
        "stored_status": sub.status,
        "source": sub.source,
        "billing_period": sub.billing_period,
        "plan": {"id": str(plan.id), "name": plan.name, "slug": plan.slug} if plan else None,
        "trial_end": iso(sub.trial_end),
        "current_period_start": iso(sub.current_period_start),
        "current_period_end": iso(sub.current_period_end),
        "grace_period_end": iso(effective_grace_end(sub, now)),
        "cancel_at_period_end": sub.cancel_at_period_end,
        "stripe_customer_id": sub.stripe_customer_id,
        "stripe_subscription_id": sub.stripe_subscription_id,
        "polar_customer_id": sub.polar_customer_id,
        "polar_subscription_id": sub.polar_subscription_id,
        "usage": {
            "minutes": sub.current_period_minutes,
            "calls": sub.current_period_calls,
            "sms": sub.current_period_sms,
            "emails": sub.current_period_emails,
        },
        "created_at": iso(sub.created_at),
    }
