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

A third section, **billing**, exists only on a prepaid plan (Pay As You Go). It
says the plan has no monthly allowance at all: every call minute is paid for
from the workspace's wallet, at the rate held here. Code asks
:func:`is_prepaid` — it never compares a slug.

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
#: Retired 29 Sep 2026: plans are metered in minutes only, because a minute is
#: what a call costs us. Still counted on the subscription for reporting, and
#: still present (as unlimited) in documents seeded before the change, but no
#: plan sets it and no gate reads it.
LIMIT_CALLS = "calls_per_month"
LIMIT_SMS = "sms_per_month"
LIMIT_EMAILS = "emails_per_month"
#: Calls live at the same time. Counted from in-flight ``Call`` rows at the
#: moment a call starts — see ``EntitlementService.active_call_count``.
LIMIT_CONCURRENT_CALLS = "concurrent_calls"
#: Voices in the workspace's custom voice library (cloned voices).
LIMIT_CUSTOM_VOICES = "custom_voices"

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
        LIMIT_CUSTOM_VOICES,
    }
)

#: Limits read from the subscription's per-period counters, reset each cycle.
#: SMS is not part of any plan (29 Sep 2026), so it has no allowance.
USAGE_LIMITS = frozenset({LIMIT_MINUTES, LIMIT_EMAILS})

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
    CRM_INTEGRATIONS: "CRM, messaging & automation integrations",
    KNOWLEDGE_BASE: "Knowledge base",
    VIRTUAL_MEETINGS: "Virtual meetings & note taking",
    LEAD_SCORING: "Lead scoring & data enrichment",
    API_ACCESS: "Public API access",
    CUSTOM_VOICE: "Custom voice cloning",
    WHITE_LABEL: "White labelling",
    ANALYTICS: "Analytics",
    CALL_RECORDINGS: "Call recordings & transcripts",
    WEBHOOKS: "Webhooks & custom tools",
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
    LIMIT_EMAILS: "emails this month",
    LIMIT_CONCURRENT_CALLS: "concurrent calls",
    LIMIT_CUSTOM_VOICES: "custom voices",
}


def _features(**overrides: bool) -> Dict[str, bool]:
    """Every feature off, then switch on what this plan includes."""
    doc = {key: False for key in ALL_FEATURES}
    doc.update(overrides)
    return doc


# ---- Free trial ----
#: How long a card-free trial runs, in days. The single source of truth: plans
#: are seeded with it, existing plans are re-synced to it on startup (see
#: ``seed_plans.backfill_plan_entitlements``), and ``POST /billing/trial`` falls
#: back to it when a plan carries no length of its own. Change it here and the
#: whole product follows — there is no per-plan trial length in the UI today.
DEFAULT_TRIAL_DAYS = 14

# Deliberately generous on *capability*. Trials convert on feature discovery: a
# user who never sees lead scoring has no reason to pick the expensive plan.
#
# Consumption is capped hard: 30 call minutes, with no
# overage, because a trial has no card to bill (pricing sheet, 29 Sep 2026). A
# trial also cannot buy a phone number: a number is a recurring charge at the
# carrier that outlives the trial. Restricting what costs us money rather than
# what can be explored keeps the trial cheap to run and still worth evaluating.
TRIAL_ENTITLEMENTS: Dict[str, Any] = {
    "features": _features(
        **{
            INBOUND_CALLS: True,
            OUTBOUND_CALLS: True,
            OUTBOUND_CAMPAIGNS: True,
            EMAIL: True,
            WORKFLOWS: True,
            CRM_INTEGRATIONS: True,
            KNOWLEDGE_BASE: True,
            VIRTUAL_MEETINGS: True,
            LEAD_SCORING: True,
            ANALYTICS: True,
            CALL_RECORDINGS: True,
            # Custom tools and custom voices were never gated before plans were
            # tiered; keeping them on means a trial can still build the agent
            # it would run on Growth or Scale.
            WEBHOOKS: True,
            CUSTOM_VOICE: True,
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
        LIMIT_MINUTES: 30,
        LIMIT_EMAILS: 100,
        LIMIT_CONCURRENT_CALLS: 2,
        LIMIT_CUSTOM_VOICES: 1,
    },
    "overage": {"allowed": False},
}

# ---- Nothing live: expired trial, lapsed subscription, no subscription ----
# Runtime is off, so we stop paying for calls the moment the account lapses.
# Everything the user built stays visible and exportable — see
# ``Entitlements.is_read_only``, which the API's write guards consult.
EXPIRED_ENTITLEMENTS: Dict[str, Any] = {
    "features": _features(),
    "limits": {
        key: 0 for key in (*RESOURCE_LIMITS, *USAGE_LIMITS, LIMIT_CONCURRENT_CALLS)
    },
    "overage": {"allowed": False},
}

# ---- Paid plans ----
# From "VoiceCon Pricing Packages — Final" (29 Sep 2026). Each plan includes
# everything in the one before it. Enterprise is sold by contract, not through
# checkout, so it has no row here: staff put those customers on a plan with an
# ``OrganizationEntitlementOverride``.
#
# Minutes are a real allowance now. Paid plans keep working past it and the
# excess is priced at ``overage.per_minute`` (see ``UsageTracker``); a trial
# stops at its allowance because there is no card to bill.
_STARTER_FEATURES = {
    INBOUND_CALLS: True,
    EMAIL: True,
    WORKFLOWS: True,
    KNOWLEDGE_BASE: True,
    ANALYTICS: True,
    CALL_RECORDINGS: True,
    PHONE_NUMBER_PURCHASE: True,
}
_GROWTH_FEATURES = {
    **_STARTER_FEATURES,
    OUTBOUND_CALLS: True,
    CRM_INTEGRATIONS: True,
    WEBHOOKS: True,
    API_ACCESS: True,
}
_SCALE_FEATURES = {
    **_GROWTH_FEATURES,
    OUTBOUND_CAMPAIGNS: True,
    LEAD_SCORING: True,
    WORKFLOW_SCHEDULING: True,
    CUSTOM_VOICE: True,
}
_AGENCY_FEATURES = {
    **_SCALE_FEATURES,
    WHITE_LABEL: True,
}

PLAN_ENTITLEMENTS: Dict[str, Dict[str, Any]] = {
    "starter": {
        "features": _features(**_STARTER_FEATURES),
        "limits": {
            LIMIT_AGENTS: 1,
            LIMIT_PHONE_NUMBERS: 1,
            LIMIT_KNOWLEDGE_BASES: 1,
            LIMIT_TEAM_MEMBERS: 2,
            LIMIT_WORKFLOWS: 3,
            LIMIT_API_KEYS: 0,
            LIMIT_CUSTOM_VOICES: 0,
            LIMIT_CONCURRENT_CALLS: 3,
            LIMIT_MINUTES: 200,
            LIMIT_EMAILS: 500,
        },
        "overage": {"allowed": True, "per_minute": 0.30},
    },
    "growth": {
        "features": _features(**_GROWTH_FEATURES),
        "limits": {
            LIMIT_AGENTS: 3,
            LIMIT_PHONE_NUMBERS: 2,
            LIMIT_KNOWLEDGE_BASES: 5,
            LIMIT_TEAM_MEMBERS: 5,
            LIMIT_WORKFLOWS: 15,
            LIMIT_API_KEYS: 3,
            LIMIT_CUSTOM_VOICES: 0,
            LIMIT_CONCURRENT_CALLS: 5,
            LIMIT_MINUTES: 750,
            LIMIT_EMAILS: 2000,
        },
        "overage": {"allowed": True, "per_minute": 0.25},
    },
    "scale": {
        "features": _features(**_SCALE_FEATURES),
        "limits": {
            LIMIT_AGENTS: 10,
            LIMIT_PHONE_NUMBERS: 5,
            LIMIT_KNOWLEDGE_BASES: UNLIMITED,
            LIMIT_TEAM_MEMBERS: 10,
            LIMIT_WORKFLOWS: UNLIMITED,
            LIMIT_API_KEYS: 10,
            LIMIT_CUSTOM_VOICES: 2,
            LIMIT_CONCURRENT_CALLS: 15,
            LIMIT_MINUTES: 2000,
            LIMIT_EMAILS: 5000,
        },
        "overage": {"allowed": True, "per_minute": 0.20},
    },
    "agency": {
        "features": _features(**_AGENCY_FEATURES),
        "limits": {
            LIMIT_AGENTS: UNLIMITED,
            LIMIT_PHONE_NUMBERS: 20,
            LIMIT_KNOWLEDGE_BASES: UNLIMITED,
            LIMIT_TEAM_MEMBERS: 25,
            LIMIT_WORKFLOWS: UNLIMITED,
            LIMIT_API_KEYS: 25,
            LIMIT_CUSTOM_VOICES: 10,
            LIMIT_CONCURRENT_CALLS: 30,
            LIMIT_MINUTES: 3000,
            LIMIT_EMAILS: 20000,
        },
        "overage": {"allowed": True, "per_minute": 0.15},
    },
}

# ---- Pay As You Go ----
# No monthly fee and no monthly allowance: the workspace loads money into a
# wallet and each call minute is deducted from it (see ``services/billing/
# wallet``). Minutes are therefore "unlimited" as far as the allowance checks
# are concerned — what stops a call is an empty wallet, not a counter.
#
# The rate sits above Starter's overage rate on purpose: a subscription has to
# stay the cheaper way to buy minutes for anyone who uses them regularly.
BILLING_PREPAID = "prepaid"

#: Everything about how a prepaid plan charges. Amounts are in the plan's
#: currency, as numbers an admin can read and edit; they are turned into whole
#: cents with ``Decimal`` where money moves, never used as floats.
PAYG_BILLING: Dict[str, Any] = {
    "mode": BILLING_PREPAID,
    #: Price of one call minute.
    "per_minute": 0.35,
    #: Monthly rent of each Voicecon phone number, taken from the wallet. ``0``
    #: makes numbers free on this plan.
    "number_monthly_fee": 2.00,
    #: Amounts the top-up dialog offers, and the bounds for a custom amount.
    "topup_presets": [10, 25, 50, 100],
    "topup_min": 10,
    "topup_max": 1000,
    #: Owners are warned once the balance falls below this.
    "low_balance": 5,
}

#: Slug of the prepaid plan the seeder creates. For seeding and migrations
#: only — runtime code must ask :func:`is_prepaid`.
PREPAID_PLAN_SLUG = "payg"

#: Kept apart from :data:`PLAN_ENTITLEMENTS`, which is the ladder of
#: subscriptions (each one includes the one before, and a 402 suggests the
#: next rung). Pay As You Go is not a rung on it.
PREPAID_PLAN_ENTITLEMENTS: Dict[str, Dict[str, Any]] = {}

PREPAID_PLAN_ENTITLEMENTS[PREPAID_PLAN_SLUG] = {
    "features": _features(**_STARTER_FEATURES),
    "limits": {
        LIMIT_AGENTS: 1,
        LIMIT_PHONE_NUMBERS: 1,
        LIMIT_KNOWLEDGE_BASES: 1,
        LIMIT_TEAM_MEMBERS: 2,
        LIMIT_WORKFLOWS: 3,
        LIMIT_API_KEYS: 0,
        LIMIT_CUSTOM_VOICES: 0,
        LIMIT_CONCURRENT_CALLS: 2,
        LIMIT_MINUTES: UNLIMITED,
        LIMIT_EMAILS: 500,
    },
    # Nothing is billed afterwards: a minute is paid for before it is used.
    "overage": {"allowed": False},
    "billing": dict(PAYG_BILLING),
}

#: Sections of an entitlement document, in the order they are merged.
DOCUMENT_SECTIONS = ("features", "limits", "overage", "billing")

#: The two launch plans the pricing sheet replaced. No longer sold (the seeder
#: hides them), but customers already subscribed keep them — their entitlements
#: resolve from the stored row, and these documents are the fallback for a row
#: that has none. Deliberately absent from :data:`PLAN_ENTITLEMENTS`, so a 402
#: never suggests upgrading to a plan nobody can buy.
LEGACY_PLAN_ENTITLEMENTS: Dict[str, Dict[str, Any]] = {
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
                CUSTOM_VOICE: True,
            }
        ),
        "limits": {
            LIMIT_AGENTS: 10,
            LIMIT_PHONE_NUMBERS: 10,
            LIMIT_KNOWLEDGE_BASES: 10,
            LIMIT_TEAM_MEMBERS: 10,
            LIMIT_WORKFLOWS: 10,
            LIMIT_API_KEYS: 100,
            LIMIT_CUSTOM_VOICES: UNLIMITED,
            LIMIT_CONCURRENT_CALLS: UNLIMITED,
            LIMIT_MINUTES: UNLIMITED,
            LIMIT_EMAILS: UNLIMITED,
        },
        "overage": {"allowed": True, "per_minute": 0.015},
    },
    "voice-ai": {
        "features": _features(**{key: True for key in ALL_FEATURES}),
        "limits": {
            LIMIT_AGENTS: 30,
            LIMIT_PHONE_NUMBERS: 30,
            LIMIT_KNOWLEDGE_BASES: 30,
            LIMIT_TEAM_MEMBERS: 30,
            LIMIT_WORKFLOWS: 30,
            LIMIT_API_KEYS: 200,
            LIMIT_CUSTOM_VOICES: UNLIMITED,
            LIMIT_CONCURRENT_CALLS: UNLIMITED,
            LIMIT_MINUTES: UNLIMITED,
            LIMIT_EMAILS: UNLIMITED,
        },
        "overage": {"allowed": True, "per_minute": 0.015},
    },
}

#: Slug a card-free trial is attached to when the client names none.
TRIAL_PLAN_SLUG = "growth"

#: The most restrictive plan, used for an unknown slug.
FALLBACK_PLAN_SLUG = "starter"


def entitlements_for_plan(slug: str | None) -> Dict[str, Any]:
    """Default entitlement document for a plan slug.

    An unknown slug gets the most restrictive paid plan rather than a permissive
    default — a typo in a slug should under-grant, never over-grant.
    """
    if slug and slug in PLAN_ENTITLEMENTS:
        return PLAN_ENTITLEMENTS[slug]
    if slug and slug in PREPAID_PLAN_ENTITLEMENTS:
        return PREPAID_PLAN_ENTITLEMENTS[slug]
    if slug and slug in LEGACY_PLAN_ENTITLEMENTS:
        return LEGACY_PLAN_ENTITLEMENTS[slug]
    return PLAN_ENTITLEMENTS[FALLBACK_PLAN_SLUG]


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
        section: dict(base.get(section) or {}) for section in DOCUMENT_SECTIONS
    }
    for section in DOCUMENT_SECTIONS:
        section_overrides = (overrides or {}).get(section)
        if isinstance(section_overrides, dict):
            merged[section].update(section_overrides)
    return merged


def is_prepaid(document: Dict[str, Any] | None) -> bool:
    """Does this entitlement document describe a prepaid (wallet) plan?"""
    return ((document or {}).get("billing") or {}).get("mode") == BILLING_PREPAID


def billing_config(document: Dict[str, Any] | None) -> Dict[str, Any]:
    """A prepaid plan's billing settings, with catalogue defaults filled in.

    A stored document may predate a key added here later; reading through this
    means such a plan keeps working instead of charging nothing.
    """
    stored = (document or {}).get("billing") or {}
    return {**PAYG_BILLING, **stored}
