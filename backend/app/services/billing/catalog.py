"""
The feature/limit matrix — the one place that decides what each plan includes.

Every gate in the product resolves back to a key defined here. If a limit is
hardcoded in an ``if`` statement anywhere else in the codebase, that is a bug:
the matrix has to be readable in one screen or it stops being maintainable.

Two dimensions, and they fail differently:

* **features** — a capability the plan either includes or does not. Failing this
  means "upgrade your plan".
* **limits** — how much of something the plan allows. ``-1`` is unlimited.
  Failing this means "you have used all of your allowance".

The documents here are seeded onto ``SubscriptionPlan.entitlements`` and can be
edited per-plan in the database afterwards; the code only ever reads the column,
never this module, at request time. This is the default, not the authority.
"""
from __future__ import annotations

from typing import Any, Dict

# ---- Feature keys ----
# These are a public contract the moment the frontend uses them: add, never
# rename.
INBOUND_CALLS = "inbound_calls"
OUTBOUND_CALLS = "outbound_calls"
OUTBOUND_CAMPAIGNS = "outbound_campaigns"
SMS = "sms"
EMAIL = "email"
WORKFLOWS = "workflows"
WORKFLOW_SCHEDULING = "workflow_scheduling"
CRM_INTEGRATIONS = "crm_integrations"
KNOWLEDGE_BASE = "knowledge_base"
VIRTUAL_MEETINGS = "virtual_meetings"
LEAD_SCORING = "lead_scoring"
API_ACCESS = "api_access"
CUSTOM_VOICE = "custom_voice"
WHITE_LABEL = "white_label"
ANALYTICS = "analytics"
CALL_RECORDINGS = "call_recordings"
WEBHOOKS = "webhooks"
#: Buying a number from a carrier. Off during the trial, so a card-free
#: account can never place a recurring charge with Twilio or Telnyx —
#: including on a carrier account the user connected themselves, because the
#: gate is on the action, not on whose credentials pay for it.
PHONE_NUMBER_PURCHASE = "phone_number_purchase"

# ---- Limit keys ----
# Resource limits are counted live from the owning table; usage limits are read
# from the per-period counters on the subscription row.
LIMIT_AGENTS = "agents"
LIMIT_PHONE_NUMBERS = "phone_numbers"
LIMIT_KNOWLEDGE_BASES = "knowledge_bases"
LIMIT_TEAM_MEMBERS = "team_members"
LIMIT_WORKFLOWS = "workflows"
LIMIT_API_KEYS = "api_keys"
LIMIT_MINUTES = "minutes_per_month"
LIMIT_CALLS = "calls_per_month"
LIMIT_SMS = "sms_per_month"
LIMIT_EMAILS = "emails_per_month"

#: ``-1`` means "no ceiling". Read by ``Entitlements.within``, which short-
#: circuits before comparing against usage.
UNLIMITED = -1

#: Limits counted by a ``SELECT COUNT(*)`` against the resource's own table.
RESOURCE_LIMITS = frozenset(
    {
        LIMIT_AGENTS,
        LIMIT_PHONE_NUMBERS,
        LIMIT_KNOWLEDGE_BASES,
        LIMIT_TEAM_MEMBERS,
        LIMIT_WORKFLOWS,
        LIMIT_API_KEYS,
    }
)

#: Limits read from the subscription's per-period counters, reset each cycle.
USAGE_LIMITS = frozenset({LIMIT_MINUTES, LIMIT_CALLS, LIMIT_SMS, LIMIT_EMAILS})

ALL_FEATURES = (
    INBOUND_CALLS,
    OUTBOUND_CALLS,
    OUTBOUND_CAMPAIGNS,
    SMS,
    EMAIL,
    WORKFLOWS,
    WORKFLOW_SCHEDULING,
    CRM_INTEGRATIONS,
    KNOWLEDGE_BASE,
    VIRTUAL_MEETINGS,
    LEAD_SCORING,
    API_ACCESS,
    CUSTOM_VOICE,
    WHITE_LABEL,
    ANALYTICS,
    CALL_RECORDINGS,
    WEBHOOKS,
    PHONE_NUMBER_PURCHASE,
)

#: Human labels for the 402 body and the upgrade dialog.
FEATURE_LABELS: Dict[str, str] = {
    INBOUND_CALLS: "Inbound calls",
    OUTBOUND_CALLS: "Outbound calls",
    OUTBOUND_CAMPAIGNS: "Outbound campaigns",
    SMS: "SMS messaging",
    EMAIL: "Email sending",
    WORKFLOWS: "Workflows",
    WORKFLOW_SCHEDULING: "Scheduled & triggered workflows",
    CRM_INTEGRATIONS: "CRM integrations",
    KNOWLEDGE_BASE: "Knowledge base",
    VIRTUAL_MEETINGS: "Virtual meetings & note taking",
    LEAD_SCORING: "Lead scoring & data enrichment",
    API_ACCESS: "Public API access",
    CUSTOM_VOICE: "Custom voice cloning",
    WHITE_LABEL: "White labelling",
    ANALYTICS: "Analytics",
    CALL_RECORDINGS: "Call recordings & transcripts",
    WEBHOOKS: "Webhooks",
    PHONE_NUMBER_PURCHASE: "Buying phone numbers",
}

LIMIT_LABELS: Dict[str, str] = {
    LIMIT_AGENTS: "AI agents",
    LIMIT_PHONE_NUMBERS: "phone numbers",
    LIMIT_KNOWLEDGE_BASES: "knowledge bases",
    LIMIT_TEAM_MEMBERS: "team members",
    LIMIT_WORKFLOWS: "workflows",
    LIMIT_API_KEYS: "API keys",
    LIMIT_MINUTES: "minutes this month",
    LIMIT_CALLS: "calls this month",
    LIMIT_SMS: "SMS this month",
    LIMIT_EMAILS: "emails this month",
}


def _features(**overrides: bool) -> Dict[str, bool]:
    """Every feature off, then switch on what this plan includes."""
    doc = {key: False for key in ALL_FEATURES}
    doc.update(overrides)
    return doc


# ---- Free trial ----
# Deliberately generous on *capability*. Trials convert on feature discovery: a
# user who never sees lead scoring has no reason to pick the expensive plan.
#
# Minutes and calls are uncapped. The one thing a trial cannot do is buy a phone
# number, and that single gate replaces the old consumption caps: a number is a
# recurring charge at the carrier that outlives the trial, whereas conversation
# usage is bounded by the trial window itself. Restricting the durable
# commitment rather than the exploration is both cheaper to run and far less
# frustrating to evaluate on.
TRIAL_ENTITLEMENTS: Dict[str, Any] = {
    "features": _features(
        **{
            INBOUND_CALLS: True,
            OUTBOUND_CALLS: True,
            OUTBOUND_CAMPAIGNS: True,
            SMS: True,
            EMAIL: True,
            WORKFLOWS: True,
            CRM_INTEGRATIONS: True,
            KNOWLEDGE_BASE: True,
            VIRTUAL_MEETINGS: True,
            LEAD_SCORING: True,
            ANALYTICS: True,
            CALL_RECORDINGS: True,
            # PHONE_NUMBER_PURCHASE stays off — see the note above the key.
        }
    ),
    "limits": {
        LIMIT_AGENTS: 1,
        LIMIT_PHONE_NUMBERS: 1,
        LIMIT_KNOWLEDGE_BASES: 1,
        LIMIT_TEAM_MEMBERS: 2,
        LIMIT_WORKFLOWS: 2,
        LIMIT_API_KEYS: 0,
        LIMIT_MINUTES: UNLIMITED,
        LIMIT_CALLS: UNLIMITED,
        LIMIT_SMS: 25,
        LIMIT_EMAILS: 100,
    },
    "overage": {"allowed": False},
}

# ---- Nothing live: expired trial, lapsed subscription, no subscription ----
# Runtime is off, so we stop paying for calls the moment the account lapses.
# Everything the user built stays visible and exportable — see
# ``Entitlements.is_read_only``, which the API's write guards consult.
EXPIRED_ENTITLEMENTS: Dict[str, Any] = {
    "features": _features(),
    "limits": {key: 0 for key in (*RESOURCE_LIMITS, *USAGE_LIMITS)},
    "overage": {"allowed": False},
}

# ---- Paid plans ----
PLAN_ENTITLEMENTS: Dict[str, Dict[str, Any]] = {
    "sales-chatbot": {
        "features": _features(
            **{
                INBOUND_CALLS: True,
                OUTBOUND_CALLS: True,
                SMS: True,
                EMAIL: True,
                WORKFLOWS: True,
                CRM_INTEGRATIONS: True,
                KNOWLEDGE_BASE: True,
                ANALYTICS: True,
                CALL_RECORDINGS: True,
                WEBHOOKS: True,
                PHONE_NUMBER_PURCHASE: True,
            }
        ),
        "limits": {
            LIMIT_AGENTS: 3,
            LIMIT_PHONE_NUMBERS: 1,
            LIMIT_KNOWLEDGE_BASES: 1,
            LIMIT_TEAM_MEMBERS: 3,
            LIMIT_WORKFLOWS: 5,
            LIMIT_API_KEYS: 0,
            LIMIT_MINUTES: UNLIMITED,
            LIMIT_CALLS: UNLIMITED,
            LIMIT_SMS: 600,
            LIMIT_EMAILS: 2500,
        },
        "overage": {"allowed": True, "per_minute": 0.015, "per_call": 0.05},
    },
    "voice-ai": {
        "features": _features(**{key: True for key in ALL_FEATURES}),
        "limits": {
            LIMIT_AGENTS: 5,
            LIMIT_PHONE_NUMBERS: 5,
            LIMIT_KNOWLEDGE_BASES: 5,
            LIMIT_TEAM_MEMBERS: 10,
            LIMIT_WORKFLOWS: -1,
            LIMIT_API_KEYS: 10,
            LIMIT_MINUTES: UNLIMITED,
            LIMIT_CALLS: UNLIMITED,
            LIMIT_SMS: 1000,
            LIMIT_EMAILS: 5000,
        },
        "overage": {"allowed": True, "per_minute": 0.015, "per_call": 0.05},
    },
}


def entitlements_for_plan(slug: str | None) -> Dict[str, Any]:
    """Default entitlement document for a plan slug.

    An unknown slug gets the most restrictive paid plan rather than a permissive
    default — a typo in a slug should under-grant, never over-grant.
    """
    if slug and slug in PLAN_ENTITLEMENTS:
        return PLAN_ENTITLEMENTS[slug]
    return PLAN_ENTITLEMENTS["sales-chatbot"]


def plans_offering(feature: str) -> list[str]:
    """Which paid plans include ``feature`` — powers "upgrade to X" in the 402."""
    return [
        slug
        for slug, doc in PLAN_ENTITLEMENTS.items()
        if doc["features"].get(feature, False)
    ]


def plans_allowing(limit: str, required: int) -> list[str]:
    """Which paid plans allow at least ``required`` of ``limit``."""
    out = []
    for slug, doc in PLAN_ENTITLEMENTS.items():
        cap = doc["limits"].get(limit, 0)
        if cap == -1 or cap >= required:
            out.append(slug)
    return out


def merge_entitlements(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Merge an override document over a base one, one level deep per section.

    Only the keys present in ``overrides`` are replaced, so a comp that unlocks
    a single feature does not wipe out the rest of the plan.
    """
    merged: Dict[str, Any] = {
        "features": dict(base.get("features") or {}),
        "limits": dict(base.get("limits") or {}),
        "overage": dict(base.get("overage") or {}),
    }
    for section in ("features", "limits", "overage"):
        section_overrides = (overrides or {}).get(section)
        if isinstance(section_overrides, dict):
            merged[section].update(section_overrides)
    return merged
