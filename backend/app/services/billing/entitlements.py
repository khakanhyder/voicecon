"""
What an organization is allowed to do right now.

This is the single answer every gate in the product asks for, and it is
*derived* — never read straight off ``Subscription.status``. That column is only
as fresh as the last reconciler run, so trusting it would leave a trial that
ended overnight looking live until the next sweep, and would hand out a free
product entirely if the scheduler were down.

    Access decisions derive expiry at read time.
    The reconciler persists the same decision, for side effects and reporting.

Both are needed. Read-time derivation alone means nobody is ever emailed and
pooled phone numbers are never reclaimed; the reconciler alone means access is
wrong between sweeps. See ``app.services.billing.reconciler``.

Two things are deliberately kept apart:

* :meth:`EntitlementService.resolve` is cheap — two indexed queries, cached —
  and answers "what does this org have". It runs on nearly every request.
* :meth:`EntitlementService.usage_snapshot` counts live resources and is only
  called when a limit is actually being checked, or by the billing page.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import ceil
from typing import Any, Dict, Mapping, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import (
    LIVE_STATUSES,
    RUNTIME_STATUSES,
    SOURCE_TRIAL,
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_EXPIRED,
    STATUS_GRACE,
    STATUS_PAST_DUE,
    STATUS_TRIALING,
    OrganizationEntitlementOverride,
    Subscription,
    SubscriptionPlan,
)
from app.services.billing import catalog

logger = logging.getLogger(__name__)

#: How long a lapsed trial or a failed payment keeps working before the account
#: goes read-only. A trial ending on a Friday should not be a weekend outage,
#: and a card that fails once should not take a phone line down the same day.
TRIAL_GRACE_DAYS = 3
PAYMENT_GRACE_DAYS = 7

#: A trial is "expiring soon" — and the UI turns amber — inside this window.
EXPIRING_SOON_DAYS = 3

#: Warn in the UI once usage passes this fraction of an allowance.
USAGE_WARNING_THRESHOLD = 0.8

#: Statuses that leave the account visible but frozen: everything the user built
#: stays readable and exportable, nothing runs and nothing can be edited.
READ_ONLY_STATUSES = (STATUS_EXPIRED, STATUS_CANCELED)


def _utcnow() -> datetime:
    """Naive UTC, matching the DateTime columns in this schema.

    The whole schema stores naive UTC. Introducing an aware datetime here would
    raise ``TypeError`` on the first comparison against a stored value, and the
    natural place for that to happen is a trial-expiry check — so this stays
    consistent with the columns rather than being "more correct" in isolation.
    """
    return datetime.utcnow()


@dataclass(frozen=True)
class Entitlements:
    """A resolved, point-in-time answer to "what may this organization do?"."""

    organization_id: uuid.UUID
    status: str
    """Effective status, after applying expiry at read time. May differ from
    the persisted ``Subscription.status`` until the reconciler catches up."""

    stored_status: Optional[str] = None
    subscription_id: Optional[uuid.UUID] = None
    plan_id: Optional[uuid.UUID] = None
    plan_slug: Optional[str] = None
    plan_name: Optional[str] = None
    plan_tier: int = 0
    source: Optional[str] = None
    billing_period: Optional[str] = None

    trial_end: Optional[datetime] = None
    grace_period_end: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False

    features: frozenset = frozenset()
    limits: Mapping[str, int] = field(default_factory=dict)
    usage: Mapping[str, int] = field(default_factory=dict)
    overage_allowed: bool = False

    # ---- Derived state ----

    @property
    def is_trial(self) -> bool:
        """A trial remains a trial even when in grace or expired."""
        return self.source == SOURCE_TRIAL

    @property
    def is_live(self) -> bool:
        """May this organization *run* anything — calls, agents, workflows?"""
        return self.status in RUNTIME_STATUSES

    @property
    def is_read_only(self) -> bool:
        """Account visible and exportable, but frozen."""
        return not self.is_live

    @property
    def in_grace(self) -> bool:
        return self.status == STATUS_GRACE

    @property
    def has_subscription(self) -> bool:
        return self.subscription_id is not None

    @property
    def days_remaining(self) -> Optional[int]:
        """Whole days left on the trial, rounded up. ``None`` when not trialing.

        Computed, never stored — a persisted counter has to be decremented by
        something, and that something is wrong across timezones and downtime.
        """
        if not self.is_trial or self.trial_end is None:
            return None
        seconds = (self.trial_end - _utcnow()).total_seconds()
        return max(0, ceil(seconds / 86400))

    @property
    def trial_expiring_soon(self) -> bool:
        days = self.days_remaining
        return days is not None and days <= EXPIRING_SOON_DAYS

    @property
    def grace_days_remaining(self) -> Optional[int]:
        if not self.in_grace or self.grace_period_end is None:
            return None
        seconds = (self.grace_period_end - _utcnow()).total_seconds()
        return max(0, ceil(seconds / 86400))

    # ---- Checks ----

    def has(self, feature: str) -> bool:
        """Does the plan include ``feature`` *and* is the account live?

        Both halves matter: an expired Voice AI trial still "has" lead scoring
        in the abstract, but must not be able to run it.
        """
        return self.is_live and feature in self.features

    def limit(self, key: str) -> int:
        """The cap for ``key``. ``-1`` is unlimited, ``0`` is none."""
        return int(self.limits.get(key, 0))

    def used(self, key: str) -> int:
        return int(self.usage.get(key, 0))

    def is_unlimited(self, key: str) -> bool:
        return self.limit(key) == -1

    def remaining(self, key: str) -> Optional[int]:
        """Headroom left, or ``None`` when unlimited."""
        if self.is_unlimited(key):
            return None
        return max(0, self.limit(key) - self.used(key))

    def within(self, key: str, requested: int = 1) -> bool:
        """Is there room for ``requested`` more of ``key``?"""
        if not self.is_live:
            return False
        if self.is_unlimited(key):
            return True
        return self.used(key) + requested <= self.limit(key)

    def usage_ratio(self, key: str) -> Optional[float]:
        cap = self.limit(key)
        if cap <= 0:
            return None
        return self.used(key) / cap

    def with_usage(self, usage: Mapping[str, int]) -> "Entitlements":
        """A copy carrying live resource counts, for limit checks and the UI."""
        merged = {**self.usage, **usage}
        return Entitlements(
            organization_id=self.organization_id,
            status=self.status,
            stored_status=self.stored_status,
            subscription_id=self.subscription_id,
            plan_id=self.plan_id,
            plan_slug=self.plan_slug,
            plan_name=self.plan_name,
            plan_tier=self.plan_tier,
            source=self.source,
            billing_period=self.billing_period,
            trial_end=self.trial_end,
            grace_period_end=self.grace_period_end,
            current_period_end=self.current_period_end,
            cancel_at_period_end=self.cancel_at_period_end,
            features=self.features,
            limits=self.limits,
            usage=merged,
            overage_allowed=self.overage_allowed,
        )


def effective_grace_end(
    subscription: Optional[Subscription], now: datetime
) -> Optional[datetime]:
    """When the cushion runs out, whether or not the reconciler has written it.

    ``grace_period_end`` is only persisted once the sweep has run, but the
    status is derived immediately — so between a trial lapsing and the next
    sweep the account is in grace with no stored deadline. Deriving the same
    value here keeps the UI able to say "2 days before your number is released"
    instead of falling back to vaguer copy.
    """
    if subscription is None:
        return None
    if subscription.grace_period_end is not None:
        return subscription.grace_period_end
    if subscription.status == STATUS_TRIALING:
        trial_end = subscription.trial_end or subscription.current_period_end
        if trial_end and trial_end <= now:
            return trial_end + timedelta(days=TRIAL_GRACE_DAYS)
    return None


def effective_status(subscription: Optional[Subscription], now: datetime) -> str:
    """The status a subscription *actually* has at ``now``.

    Applies the deadlines the reconciler would eventually apply, so access is
    correct the instant a trial ends rather than at the next sweep.

    One deliberate asymmetry: **fail closed for trials, fail open for payers.**
    An ``active`` subscription past its period end is left alone — Stripe is the
    truth for paid subscriptions, and locking out a paying customer because a
    webhook was dropped costs far more than a few hours of unbilled usage. The
    reconciler logs those for investigation instead.
    """
    if subscription is None:
        return STATUS_EXPIRED

    status = subscription.status

    if status == STATUS_TRIALING:
        trial_end = subscription.trial_end or subscription.current_period_end
        if trial_end and trial_end <= now:
            grace_end = subscription.grace_period_end or (
                trial_end + timedelta(days=TRIAL_GRACE_DAYS)
            )
            return STATUS_GRACE if now < grace_end else STATUS_EXPIRED
        return STATUS_TRIALING

    if status == STATUS_GRACE:
        grace_end = subscription.grace_period_end
        if grace_end and grace_end <= now:
            return STATUS_EXPIRED
        return STATUS_GRACE

    if status == STATUS_PAST_DUE:
        # Stripe retries for roughly two weeks and most failures self-resolve,
        # so access continues through dunning.
        grace_end = subscription.grace_period_end
        if grace_end and grace_end <= now:
            return STATUS_EXPIRED
        return STATUS_PAST_DUE

    if status == STATUS_CANCELED:
        # Cancelled but paid up: they keep what they bought until it runs out.
        if subscription.current_period_end and subscription.current_period_end > now:
            return STATUS_ACTIVE
        return STATUS_EXPIRED

    return status


class EntitlementService:
    """Resolves and caches entitlements for an organization.

    The cache is process-local with a short TTL rather than shared through
    Redis. With several API workers that means a change made in one worker can
    be up to ``CACHE_TTL_SECONDS`` stale in another; that is acceptable for the
    read path, and the paths where it is *not* acceptable — right after a
    checkout — pass ``fresh=True``.
    """

    CACHE_TTL_SECONDS = 30

    def __init__(self) -> None:
        self._cache: Dict[uuid.UUID, tuple[float, Entitlements]] = {}

    # ---- Cache ----

    def invalidate(self, organization_id: uuid.UUID) -> None:
        """Drop the cached answer. Call from every path that changes billing."""
        self._cache.pop(organization_id, None)

    def invalidate_all(self) -> None:
        self._cache.clear()

    # ---- Resolution ----

    async def resolve(
        self,
        db: AsyncSession,
        organization_id: uuid.UUID,
        *,
        fresh: bool = False,
    ) -> Entitlements:
        """What this organization may do right now."""
        if not fresh:
            cached = self._cache.get(organization_id)
            if cached and cached[0] > time.monotonic():
                return cached[1]

        resolved = await self._resolve_uncached(db, organization_id)
        self._cache[organization_id] = (
            time.monotonic() + self.CACHE_TTL_SECONDS,
            resolved,
        )
        return resolved

    async def _resolve_uncached(
        self, db: AsyncSession, organization_id: uuid.UUID
    ) -> Entitlements:
        now = _utcnow()
        subscription = await self.live_subscription(db, organization_id)
        if subscription is None:
            # Fall back to the most recent subscription of any status, so an
            # expired account still reports which plan it used to be on — the
            # upgrade screen needs that to say "reactivate Voice AI".
            subscription = await self._latest_subscription(db, organization_id)

        status = effective_status(subscription, now)
        plan = await self._plan_for(db, subscription)

        if status in RUNTIME_STATUSES and plan is not None:
            if status == STATUS_TRIALING:
                document = catalog.TRIAL_ENTITLEMENTS
            else:
                document = plan.entitlements or catalog.entitlements_for_plan(plan.slug)
        else:
            document = catalog.EXPIRED_ENTITLEMENTS

        document = await self._apply_overrides(db, organization_id, document, now)

        features = frozenset(
            key for key, enabled in (document.get("features") or {}).items() if enabled
        )
        limits = {key: int(value) for key, value in (document.get("limits") or {}).items()}
        overage = document.get("overage") or {}

        usage: Dict[str, int] = {}
        if subscription is not None:
            usage = {
                catalog.LIMIT_MINUTES: subscription.current_period_minutes or 0,
                catalog.LIMIT_CALLS: subscription.current_period_calls or 0,
                catalog.LIMIT_SMS: subscription.current_period_sms or 0,
                catalog.LIMIT_EMAILS: subscription.current_period_emails or 0,
            }

        return Entitlements(
            organization_id=organization_id,
            status=status,
            stored_status=subscription.status if subscription else None,
            subscription_id=subscription.id if subscription else None,
            plan_id=plan.id if plan else None,
            plan_slug=plan.slug if plan else None,
            plan_name=plan.name if plan else None,
            plan_tier=plan.tier if plan else 0,
            source=subscription.source if subscription else None,
            billing_period=subscription.billing_period if subscription else None,
            trial_end=subscription.trial_end if subscription else None,
            grace_period_end=effective_grace_end(subscription, now),
            current_period_end=(
                subscription.current_period_end if subscription else None
            ),
            cancel_at_period_end=(
                bool(subscription.cancel_at_period_end) if subscription else False
            ),
            features=features,
            limits=limits,
            usage=usage,
            overage_allowed=bool(overage.get("allowed", False)),
        )

    # ---- Queries ----

    @staticmethod
    async def live_subscription(
        db: AsyncSession, organization_id: uuid.UUID
    ) -> Optional[Subscription]:
        """The organization's one live subscription, if it has one.

        "Live" is about the persisted status only — whether it has actually
        lapsed is :func:`effective_status`'s job.
        """
        result = await db.execute(
            select(Subscription)
            .where(
                Subscription.organization_id == organization_id,
                Subscription.status.in_(LIVE_STATUSES),
            )
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _latest_subscription(
        db: AsyncSession, organization_id: uuid.UUID
    ) -> Optional[Subscription]:
        result = await db.execute(
            select(Subscription)
            .where(Subscription.organization_id == organization_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _plan_for(
        db: AsyncSession, subscription: Optional[Subscription]
    ) -> Optional[SubscriptionPlan]:
        if subscription is None:
            return None
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _apply_overrides(
        db: AsyncSession,
        organization_id: uuid.UUID,
        document: Dict[str, Any],
        now: datetime,
    ) -> Dict[str, Any]:
        result = await db.execute(
            select(OrganizationEntitlementOverride).where(
                OrganizationEntitlementOverride.organization_id == organization_id
            )
        )
        override = result.scalar_one_or_none()
        if override is None:
            return document
        if override.expires_at is not None and override.expires_at <= now:
            return document
        return catalog.merge_entitlements(document, override.overrides or {})

    # ---- Live resource counts ----

    async def usage_snapshot(
        self, db: AsyncSession, organization_id: uuid.UUID
    ) -> Dict[str, int]:
        """Count the resources that resource limits apply to.

        Kept out of :meth:`resolve` because it is six COUNT queries and most
        requests never look at a resource limit.
        """
        counts: Dict[str, int] = {}
        for key, model, column, extra in self._resource_specs():
            try:
                counts[key] = await self._count(db, model, column, organization_id, extra)
            except Exception as exc:  # pragma: no cover - defensive
                # A miscounted resource must never hard-fail a request; treat it
                # as zero and log, so the gate fails open rather than locking a
                # customer out of their own account over a schema mismatch.
                logger.warning(f"Could not count {key} for org {organization_id}: {exc}")
                counts[key] = 0
        return counts

    @staticmethod
    def _resource_specs():
        """(limit key, model, org column, "still counts" filter) for each resource.

        The last element differs per model — deactivated agents and released
        phone numbers should not occupy a slot, and each table spells that
        differently.
        """
        from app.models.agent import Agent
        from app.models.call import PhoneNumber
        from app.models.integration import Workflow
        from app.models.knowledge_base import KnowledgeBase
        from app.models.user import ApiKey, OrganizationMember

        return (
            (catalog.LIMIT_AGENTS, Agent, Agent.organization_id, Agent.is_active.is_(True)),
            (
                catalog.LIMIT_PHONE_NUMBERS,
                PhoneNumber,
                PhoneNumber.organization_id,
                PhoneNumber.status == "active",
            ),
            (
                catalog.LIMIT_KNOWLEDGE_BASES,
                KnowledgeBase,
                KnowledgeBase.organization_id,
                KnowledgeBase.is_active.is_(True),
            ),
            (
                catalog.LIMIT_WORKFLOWS,
                Workflow,
                Workflow.organization_id,
                Workflow.is_active.is_(True),
            ),
            (
                catalog.LIMIT_TEAM_MEMBERS,
                OrganizationMember,
                OrganizationMember.organization_id,
                None,
            ),
            (catalog.LIMIT_API_KEYS, ApiKey, ApiKey.organization_id, ApiKey.is_active.is_(True)),
        )

    async def count_for_limit(
        self, db: AsyncSession, organization_id: uuid.UUID, limit_key: str
    ) -> int:
        """Count just the one resource a limit check needs — a single query."""
        if limit_key not in catalog.RESOURCE_LIMITS:
            return 0
        for key, model, column, extra in self._resource_specs():
            if key != limit_key:
                continue
            try:
                return await self._count(db, model, column, organization_id, extra)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(f"Could not count {key} for org {organization_id}: {exc}")
                return 0
        return 0

    @staticmethod
    async def _count(
        db: AsyncSession, model, column, organization_id: uuid.UUID, extra=None
    ) -> int:
        filters = [column == organization_id]
        if extra is not None:
            filters.append(extra)
        result = await db.execute(select(func.count()).select_from(model).where(*filters))
        return int(result.scalar() or 0)

    # ---- Convenience used by non-HTTP call sites ----

    async def check_runtime(
        self, db: AsyncSession, organization_id: uuid.UUID, feature: str
    ) -> tuple[bool, Optional[str]]:
        """Gate for the paths that actually spend money.

        Returns ``(allowed, reason)``. Used by the inbound-call webhook, the
        outbound dialer and the workflow scheduler — none of which arrive
        through an authenticated HTTP request, so none of which the FastAPI
        dependency can protect.
        """
        ent = await self.resolve(db, organization_id)
        if not ent.is_live:
            return False, f"subscription_{ent.status}"
        if not ent.has(feature):
            return False, "feature_not_in_plan"

        usage_limit = {
            catalog.INBOUND_CALLS: catalog.LIMIT_CALLS,
            catalog.OUTBOUND_CALLS: catalog.LIMIT_CALLS,
            catalog.OUTBOUND_CAMPAIGNS: catalog.LIMIT_CALLS,
            catalog.SMS: catalog.LIMIT_SMS,
            catalog.EMAIL: catalog.LIMIT_EMAILS,
        }.get(feature)

        if usage_limit and not ent.within(usage_limit):
            # A paid plan with overage enabled bills past the allowance; a trial
            # has no card on file, so it stops dead instead.
            if not ent.overage_allowed:
                return False, "limit_exceeded"
        return True, None


#: Process-wide instance. Stateless apart from its cache, so sharing is safe.
_service: Optional[EntitlementService] = None


def get_entitlement_service() -> EntitlementService:
    global _service
    if _service is None:
        _service = EntitlementService()
    return _service


async def resolve_entitlements(
    db: AsyncSession, organization_id: uuid.UUID, *, fresh: bool = False
) -> Entitlements:
    """Shorthand for the common case."""
    return await get_entitlement_service().resolve(db, organization_id, fresh=fresh)


async def runtime_allows(
    db: AsyncSession, organization_id: uuid.UUID, feature: str
) -> tuple[bool, Optional[str]]:
    """``(allowed, reason)`` for a money-spending path that cannot raise HTTP.

    A carrier webhook has to answer with TwiML and a background loop has to
    decide whether to skip a run — neither can propagate a 402 to a human. They
    get a boolean and a reason string for the log instead.
    """
    return await get_entitlement_service().check_runtime(db, organization_id, feature)


def invalidate_entitlements(organization_id: uuid.UUID) -> None:
    """Drop cached entitlements for an org. Call after any billing change."""
    get_entitlement_service().invalidate(organization_id)
