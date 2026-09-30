"""How affiliates, referrals and commissions are described to the portal and the console."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Iterable, Optional
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.affiliate import (
    COMMISSION_REJECTED,
    COMMISSION_REVERSED,
    Affiliate,
    AffiliateClick,
    AffiliateCommission,
    AffiliatePayout,
    AffiliateProgram,
)
from app.models.subscription import (
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_PAST_DUE,
    STATUS_TRIALING,
    Subscription,
    SubscriptionPlan,
)
from app.services.affiliates import coupons, payouts
from app.services.affiliates.program import max_payments_for, rate_for


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _num(value) -> float:
    return float(value or 0)


# ---- Links ----


def landing_base() -> str:
    """The marketing site: ``LANDING_URL``, else the app URL without ``app.``."""
    explicit = (settings.LANDING_URL or "").rstrip("/")
    if explicit:
        return explicit
    frontend = (settings.FRONTEND_URL or "").rstrip("/")
    parsed = urlparse(frontend)
    if parsed.hostname and parsed.hostname.startswith("app."):
        host = parsed.hostname[4:]
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://{host}{port}"
    return frontend


def links(affiliate: Affiliate) -> dict:
    code = affiliate.referral_code
    return {
        "landing": f"{landing_base()}/?ref={code}",
        "signup": f"{(settings.FRONTEND_URL or '').rstrip('/')}/register?ref={code}",
    }


# ---- Referral status ----


def referral_status(sub: Optional[Subscription]) -> str:
    """``signed_up`` | ``trial`` | ``paying_monthly`` | ``paying_annual`` | ``canceled`` | ``lapsed``"""
    if sub is None:
        return "signed_up"
    if sub.source == "trial":
        return "trial" if sub.status == STATUS_TRIALING else "lapsed"
    if sub.status in (STATUS_ACTIVE, STATUS_PAST_DUE):
        return "paying_annual" if sub.billing_period == "yearly" else "paying_monthly"
    if sub.status == STATUS_CANCELED:
        return "canceled"
    return "lapsed"


async def latest_subscriptions(db: AsyncSession, org_ids: Iterable[uuid.UUID]) -> Dict[uuid.UUID, Subscription]:
    ids = list(org_ids)
    if not ids:
        return {}
    latest: Dict[uuid.UUID, Subscription] = {}
    rows = await db.execute(
        select(Subscription).where(Subscription.organization_id.in_(ids)).order_by(Subscription.created_at.desc())
    )
    for sub in rows.scalars().all():
        latest.setdefault(sub.organization_id, sub)
    return latest


async def earned_by_referral(db: AsyncSession, referral_ids: list) -> Dict[uuid.UUID, Decimal]:
    if not referral_ids:
        return {}
    rows = await db.execute(
        select(AffiliateCommission.referral_id, func.coalesce(func.sum(AffiliateCommission.amount), 0))
        .where(
            AffiliateCommission.referral_id.in_(referral_ids),
            AffiliateCommission.status.notin_((COMMISSION_REJECTED, COMMISSION_REVERSED)),
        )
        .group_by(AffiliateCommission.referral_id)
    )
    return {rid: Decimal(total or 0) for rid, total in rows.all()}


async def click_counts(db: AsyncSession, affiliate_ids: list) -> Dict[uuid.UUID, Dict[str, int]]:
    if not affiliate_ids:
        return {}
    since = datetime.utcnow() - timedelta(days=30)
    rows = await db.execute(
        select(
            AffiliateClick.affiliate_id,
            func.count(AffiliateClick.id),
            func.count(AffiliateClick.id).filter(AffiliateClick.created_at >= since),
        )
        .where(AffiliateClick.affiliate_id.in_(affiliate_ids))
        .group_by(AffiliateClick.affiliate_id)
    )
    return {aid: {"clicks": int(total), "clicks_30d": int(recent)} for aid, total, recent in rows.all()}


# ---- Serializers ----


def stripe_view(affiliate: Affiliate) -> dict:
    return {
        "state": payouts.connect_state(affiliate),
        "account_id": affiliate.stripe_account_id,
        "country": affiliate.stripe_country,
        "details_submitted": affiliate.stripe_details_submitted,
        "transfers_enabled": affiliate.stripe_transfers_enabled,
        "payouts_enabled": affiliate.stripe_payouts_enabled,
        "checked_at": _iso(affiliate.stripe_checked_at),
        "connect_available": payouts.connect_ready(),
    }


def coupon_view(affiliate: Affiliate) -> Optional[dict]:
    if not affiliate.coupon_code:
        return None
    percent = Decimal(affiliate.discount_percent or 0)
    return {
        "code": affiliate.coupon_code,
        "percent_off": float(percent),
        "applies_to": affiliate.discount_applies_to,
        "duration": affiliate.discount_duration,
        "duration_in_months": affiliate.discount_duration_months,
        "active": coupons.has_discount(affiliate),
        "description": coupons.describe(percent, affiliate.discount_duration, affiliate.discount_duration_months)
        if percent > 0
        else "No discount",
    }


def rules_view(affiliate: Affiliate, program: AffiliateProgram, plan_names: Dict[str, str]) -> dict:
    eligible = [s for s in (program.eligible_plan_slugs or []) if s]
    return {
        #: ``yearly`` | ``monthly`` | ``both`` — which payments earn.
        "billing_periods": affiliate.commission_billing_periods,
        "commission_percent": _num(rate_for(affiliate, "yearly")),
        "commission_percent_monthly": _num(rate_for(affiliate, "monthly")),
        "hold_days": program.hold_days,
        "min_payout_amount": _num(program.min_payout_amount),
        "max_commission_payments": max_payments_for(affiliate, program, "yearly"),
        "max_monthly_commission_payments": max_payments_for(affiliate, program, "monthly"),
        "referral_window_days": program.referral_window_days,
        "cookie_days": program.cookie_days,
        "eligible_plans": [plan_names.get(slug, slug) for slug in eligible] if eligible else [],
    }


def balance_view(balance: Dict[str, Decimal]) -> dict:
    return {key: _num(value) for key, value in balance.items()}


def commission_view(c: AffiliateCommission, *, customer: Optional[str] = None, extra: Optional[dict] = None) -> dict:
    view = {
        "id": str(c.id),
        "kind": c.kind,
        "provider": c.provider,
        "customer": customer,
        "plan_slug": c.plan_slug,
        "billing_period": c.billing_period,
        "billing_reason": c.billing_reason,
        "base_amount": _num(c.base_amount),
        "rate_percent": _num(c.rate_percent),
        "amount": _num(c.amount),
        "original_amount": _num(c.original_amount),
        "refunded_fraction": _num(c.refunded_fraction),
        "currency": c.currency,
        "status": c.status,
        "note": c.note,
        "earned_at": _iso(c.earned_at),
        "available_at": _iso(c.available_at),
        "approved_at": _iso(c.approved_at),
        "paid_at": _iso(c.paid_at),
        "payout_id": str(c.payout_id) if c.payout_id else None,
    }
    if extra:
        view.update(extra)
    return view


def payout_view(p: AffiliatePayout, *, staff: bool = False) -> dict:
    view = {
        "id": str(p.id),
        "amount": _num(p.amount),
        "currency": p.currency,
        "method": p.method,
        "status": p.status,
        "reference": p.reference,
        "commission_count": p.commission_count,
        "created_at": _iso(p.created_at),
        "paid_at": _iso(p.paid_at),
    }
    if staff:
        view.update(
            {
                "affiliate_id": str(p.affiliate_id),
                "stripe_transfer_id": p.stripe_transfer_id,
                "note": p.note,
                "failure_reason": p.failure_reason,
            }
        )
    return view


async def plan_names(db: AsyncSession) -> Dict[str, str]:
    rows = await db.execute(select(SubscriptionPlan.slug, SubscriptionPlan.name))
    return {slug: name for slug, name in rows.all() if slug}
