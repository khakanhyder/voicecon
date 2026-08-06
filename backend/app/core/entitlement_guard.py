"""
Entitlement enforcement at the HTTP boundary.

Authorization in this app has two independent axes, and both must pass:

* **RBAC** — *may you do this?* Handled by ``require_permission`` /
  ``workspace_guard`` in :mod:`app.core.dependencies`. Fails with **403**.
* **Entitlements** — *did your organization buy this?* Handled here. Fails with
  **402 Payment Required**.

Keeping the two statuses distinct is what lets the frontend say "ask your admin"
rather than "upgrade your plan" without pattern-matching on error text. It also
keeps the models orthogonal: a *viewer* on Voice AI and an *owner* on Sales
Chatbot are both legitimate, so plans must never be encoded as roles.

Three checks live here, and they fail differently on purpose:

1. **state** — is the subscription live at all?  → "your trial ended"
2. **feature** — does the plan include this capability?  → "upgrade to Voice AI"
3. **limit** — is there headroom left?  → "you've used all 5 agents"
"""
from __future__ import annotations

import logging
import uuid as _uuid
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from app.core.dependencies import get_db, get_workspace
from app.core.workspace import WorkspaceContext
from app.services.billing import catalog
from app.services.billing.entitlements import Entitlements, resolve_entitlements

logger = logging.getLogger(__name__)

#: Reasons carried in the 402 body. The frontend switches on these, so they are
#: a contract: add new ones, never rename.
REASON_INACTIVE = "subscription_inactive"
REASON_FEATURE = "feature_not_in_plan"
REASON_LIMIT = "limit_exceeded"
REASON_READ_ONLY = "read_only"

UPGRADE_URL = "/dashboard/settings/billing"

#: Path prefixes the router-level guard never blocks. An organization that has
#: stopped paying must always be able to sign in, look at what it built, export
#: it, and give us money — blocking any of those is both hostile and, for export
#: and deletion, a data-protection problem.
EXEMPT_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/billing",
    "/api/v1/workspaces",
    "/api/v1/onboarding",
    "/api/v1/users",
    "/api/v1/team",
    "/api/v1/invitations",
    "/api/v1/notifications",
    "/api/v1/health",
    "/api/v1/waitlist",
)

#: Read-only methods. An expired account keeps full read access by design.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class EntitlementError(HTTPException):
    """402 Payment Required, with a machine-readable body.

    Subclasses ``HTTPException`` so anything already catching one keeps working,
    but carries a ``payload`` that the handler in :mod:`app.main` renders at the
    top level of the response::

        {
          "detail": "Outbound campaigns are not included in your current plan.",
          "code": "entitlement_required",
          "reason": "feature_not_in_plan",
          "feature": "outbound_campaigns",
          "current_plan": "sales-chatbot",
          "required_plans": ["voice-ai"],
          "upgrade_url": "/dashboard/settings/billing"
        }

    ``detail`` stays a plain string so existing clients that render it verbatim
    show a sensible message instead of ``[object Object]``; everything a client
    would branch on sits beside it.
    """

    def __init__(
        self,
        *,
        message: str,
        reason: str,
        entitlements: Entitlements,
        feature: Optional[str] = None,
        limit: Optional[str] = None,
        required_plans: Optional[list[str]] = None,
    ):
        payload = {
            "detail": message,
            "code": "entitlement_required",
            "reason": reason,
            "status": entitlements.status,
            "current_plan": entitlements.plan_slug,
            "current_plan_name": entitlements.plan_name,
            "upgrade_url": UPGRADE_URL,
        }
        if feature:
            payload["feature"] = feature
            payload["feature_label"] = catalog.FEATURE_LABELS.get(feature, feature)
        if limit:
            payload["limit"] = limit
            payload["limit_label"] = catalog.LIMIT_LABELS.get(limit, limit)
            payload["used"] = entitlements.used(limit)
            payload["cap"] = entitlements.limit(limit)
        if required_plans:
            payload["required_plans"] = required_plans
        if entitlements.grace_period_end:
            payload["grace_period_end"] = entitlements.grace_period_end.isoformat()

        self.payload = payload
        super().__init__(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=message)


def _inactive_message(ent: Entitlements) -> str:
    if ent.status == "expired" and ent.source == "trial":
        return "Your free trial has ended. Choose a plan to switch your agents back on."
    if ent.status == "expired":
        return "Your subscription has ended. Choose a plan to switch your agents back on."
    if not ent.has_subscription:
        return "Start a free trial or choose a plan to begin."
    return "Your subscription is not active. Update your billing details to continue."


def assert_live(ent: Entitlements) -> None:
    """Raise unless the organization may run anything at all."""
    if not ent.is_live:
        raise EntitlementError(
            message=_inactive_message(ent),
            reason=REASON_INACTIVE,
            entitlements=ent,
        )


def assert_feature(ent: Entitlements, feature: str) -> None:
    """Raise unless the plan includes ``feature``."""
    assert_live(ent)
    if feature not in ent.features:
        label = catalog.FEATURE_LABELS.get(feature, feature.replace("_", " "))
        raise EntitlementError(
            message=f"{label} is not included in your current plan.",
            reason=REASON_FEATURE,
            entitlements=ent,
            feature=feature,
            required_plans=catalog.plans_offering(feature),
        )


def assert_within_limit(ent: Entitlements, limit_key: str, requested: int = 1) -> None:
    """Raise unless there is room for ``requested`` more of ``limit_key``.

    Monthly *usage* allowances behave differently from *resource* caps once they
    run out. A paid plan with overage enabled keeps going and bills the excess —
    that is the metered-billing model working as designed. A trial has no card
    on file, so it stops dead: metered overage on an account we cannot charge is
    an unbounded liability.

    Resource caps (agents, phone numbers, seats) never overflow either way —
    "one more agent, billed as overage" is not a thing.
    """
    assert_live(ent)
    if ent.within(limit_key, requested):
        return

    if limit_key in catalog.USAGE_LIMITS and ent.overage_allowed:
        return

    label = catalog.LIMIT_LABELS.get(limit_key, limit_key.replace("_", " "))
    cap = ent.limit(limit_key)
    used = ent.used(limit_key)
    required = used + requested

    if limit_key in catalog.USAGE_LIMITS:
        message = (
            f"You've used all {cap} {label} included in your "
            f"{'trial' if ent.is_trial else 'plan'}. Upgrade to keep going."
        )
    else:
        message = (
            f"Your plan includes {cap} {label}, and you're using {used}. "
            f"Upgrade to add more."
        )

    raise EntitlementError(
        message=message,
        reason=REASON_LIMIT,
        entitlements=ent,
        limit=limit_key,
        required_plans=catalog.plans_allowing(limit_key, required),
    )


async def entitlements_for_request(
    workspace: WorkspaceContext = Depends(get_workspace),
    db=Depends(get_db),
) -> Entitlements:
    """The resolved entitlements for the workspace this request acts inside."""
    return await resolve_entitlements(db, workspace.organization_id)


def require_entitlement(
    *,
    feature: Optional[str] = None,
    limit: Optional[str] = None,
    quantity: int = 1,
):
    """Dependency factory gating an endpoint on what the organization bought.

    Mirrors the shape of ``require_permission`` so the two read side by side::

        @router.post("/", dependencies=[
            Depends(require_permission(perms.AGENTS_WRITE)),   # may *you*?
            Depends(require_entitlement(limit="agents")),      # did the *org* buy it?
        ])

    A resource limit costs one extra COUNT query, and only on the endpoints that
    declare one — reads and unlimited plans never pay for it.
    """

    async def checker(
        workspace: WorkspaceContext = Depends(get_workspace),
        db=Depends(get_db),
    ) -> Entitlements:
        org_id = workspace.organization_id
        ent = await resolve_entitlements(db, org_id)

        assert_live(ent)

        if feature:
            assert_feature(ent, feature)

        if limit:
            if limit in catalog.RESOURCE_LIMITS:
                from app.services.billing.entitlements import get_entitlement_service

                count = await get_entitlement_service().count_for_limit(db, org_id, limit)
                ent = ent.with_usage({limit: count})
            assert_within_limit(ent, limit, quantity)

        return ent

    return checker


def entitlement_guard():
    """Router-level default: reads always pass, writes need a live subscription.

    Attached once per resource router in ``app.api.v1.api`` so a newly added
    endpoint is gated by default rather than open by default — the same reason
    ``workspace_guard`` exists. Endpoints needing a specific feature or limit
    add their own :func:`require_entitlement` on top.
    """

    async def guard(
        request: Request,
        workspace: WorkspaceContext = Depends(get_workspace),
        db=Depends(get_db),
    ) -> Optional[Entitlements]:
        if request.method in SAFE_METHODS:
            return None
        path = request.url.path
        if any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
            return None

        ent = await resolve_entitlements(db, workspace.organization_id)
        assert_live(ent)
        return ent

    return guard


async def assert_runtime_allowed(
    db,
    organization_id: _uuid.UUID,
    feature: str,
) -> None:
    """Gate for code paths that spend money but never see an HTTP dependency.

    An inbound call arrives on a carrier webhook and a scheduled workflow fires
    from a background loop — neither passes through :func:`require_entitlement`,
    and between them they account for most of what a customer costs us. Callers
    that can present an error to a human should prefer the dependency; this is
    for everything else.
    """
    from app.services.billing.entitlements import get_entitlement_service

    allowed, reason = await get_entitlement_service().check_runtime(
        db, organization_id, feature
    )
    if not allowed:
        ent = await resolve_entitlements(db, organization_id)
        if reason == REASON_FEATURE:
            assert_feature(ent, feature)
        elif reason == REASON_LIMIT:
            usage_limit = {
                catalog.INBOUND_CALLS: catalog.LIMIT_CALLS,
                catalog.OUTBOUND_CALLS: catalog.LIMIT_CALLS,
                catalog.OUTBOUND_CAMPAIGNS: catalog.LIMIT_CALLS,
                catalog.SMS: catalog.LIMIT_SMS,
                catalog.EMAIL: catalog.LIMIT_EMAILS,
            }.get(feature, catalog.LIMIT_CALLS)
            assert_within_limit(ent, usage_limit)
        else:
            assert_live(ent)
