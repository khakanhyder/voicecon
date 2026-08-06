# Free Trial & Subscription Management — Implementation Plan

**Status: implemented.** Phases 1–4 of the rollout in section 12 are done. This
document is now both the design rationale and the map of the code; section 0's
"five real gaps" describes the state this work replaced, and is kept because the
reasoning behind each fix only makes sense against it.

Where the built code differs from what is written below, the difference is
called out inline. The main one: the repeat-trial guard blocks a repeat *user*
but only logs a same-domain collision (§2.2), because a second team at the same
company is a real case and hard-blocking it cost us a legitimate signup in
testing.

Key files:

| Concern | File |
|---|---|
| Feature/limit matrix | `backend/app/services/billing/catalog.py` |
| Entitlement resolution | `backend/app/services/billing/entitlements.py` |
| Lifecycle transitions | `backend/app/services/billing/reconciler.py` |
| Scheduling | `backend/app/services/billing/scheduler.py` |
| HTTP enforcement + 402 | `backend/app/core/entitlement_guard.py` |
| Audit ledger | `backend/app/services/billing/events.py` |
| Endpoints | `backend/app/api/v1/endpoints/billing.py` |
| Schema | `backend/alembic/versions/0015_subscription_entitlements.py` |
| Frontend state | `frontend/src/store/entitlementStore.ts`, `frontend/src/lib/entitlements.ts` |
| Frontend UI | `frontend/src/components/billing/` |
| Tests | `backend/tests/unit/test_entitlements.py`, `test_subscription_lifecycle.py` |

This plan is written against the code in this repo, not a generic SaaS template.
Section 0 records what was in place before, because several of the
recommendations below exist to close a specific gap rather than to add polish.

---

## 0. Where we are today

### What works

- `POST /api/v1/billing/trial` (`backend/app/api/v1/endpoints/billing.py:692`)
  creates a `Subscription` row with `status="trialing"`, `trial_start=now`,
  `trial_end=now + 7d`, and marks onboarding complete. No card required, works
  with Stripe unconfigured.
- The data model is already good bones: `SubscriptionPlan`, `Subscription`,
  `UsageRecord`, `Invoice`, `PaymentFailure`
  (`backend/app/models/subscription.py`).
- RBAC is mature and well factored: `backend/app/core/permissions.py` +
  `require_permission` / `workspace_guard` in `backend/app/core/dependencies.py`.
  The frontend mirrors it through `useWorkspaceStore().can(...)`.
- Stripe webhooks handle `invoice.paid`, `invoice.payment_failed`,
  `customer.subscription.updated`, `customer.subscription.deleted`
  (`stripe_service.py:750`).

### The five real gaps

| # | Gap | Evidence | Impact |
|---|-----|----------|--------|
| 1 | **Trials never expire** | `beat_schedule={}` (`workers/celery_app.py:20`); no request-time expiry check anywhere | A trial from any date in the past still reads as `trialing` → permanently free account |
| 2 | **Entitlements are never enforced** | `Subscription` is imported nowhere outside `billing.py` and `onboarding.py`. `max_agents`, `max_phone_numbers`, `max_knowledge_bases`, `included_minutes`, `included_calls` are stored, returned to the UI, and never checked | Any org can create unlimited agents, buy unlimited numbers, burn unlimited minutes on any plan |
| 3 | **`check_usage_limit` is a no-op** | `usage_tracker.py:286` — `within_limit = True  # Allow overage`, and nothing calls it as a gate anyway | No spend ceiling; a runaway loop on a trial account bills us for real Twilio + LLM usage |
| 4 | **Trialing users can't upgrade** | `/billing/checkout` returns 400 "already has an active subscription" when status is `trialing` (`billing.py:787`) | The conversion path — the entire point of the trial — is blocked |
| 5 | **Nothing stops repeat trials** | `/billing/trial` only checks for an existing live subscription in *this* org | Sign up again → new org → new trial, forever |

Two smaller ones worth fixing in the same pass:

- `stripe_subscription_id` is `nullable=False, unique=True`, so the trial path
  fabricates `local_trial_<uuid>` to satisfy it. That fake id then flows into
  Stripe-shaped code paths. Make the column nullable instead.
- "One live subscription per org" is enforced with `SELECT` → `INSERT`, which is
  a race under concurrent requests. It needs a DB constraint.

---

## 1. System architecture

The design principle is one sentence:

> **Subscription rows are the source of truth. Entitlements are a derived,
> cached projection of them. Every gate in the product reads the projection,
> never the raw rows.**

```
                    ┌─────────────────────────────────────────┐
   Stripe webhooks  │  subscriptions / subscription_plans     │  ← source of truth
   Admin actions ──►│  organization_entitlements (overrides)  │
   Trial start      │  subscription_events (append-only log)  │
                    └───────────────────┬─────────────────────┘
                                        │
                            EntitlementService.resolve(org_id)
                        (applies expiry + grace at read time)
                                        │
                                 ┌──────▼──────┐
                                 │ Redis cache │  60s TTL, invalidated on write
                                 └──────┬──────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        │                               │                               │
  HTTP boundary                 Non-HTTP boundary              Read boundary
  require_entitlement()      assert_entitled() in services    GET /billing/entitlements
  (FastAPI dependency)       (inbound-call webhook,           (frontend hydration)
                              celery tasks, scheduler)
```

**Why three enforcement boundaries and not one.** A FastAPI dependency alone is
not enough for this product. The most expensive operation we have — an inbound
call that spins up STT + LLM + TTS + a Twilio leg — does **not** arrive through
an authenticated API request. It arrives on a Twilio webhook, and workflows fire
from `services/workflows/scheduler.py`. Gating only at the API layer leaves the
two paths that actually cost money wide open. So the entitlement check lives in
a plain service function, and the FastAPI dependency is a thin wrapper over it.

**Three distinct checks**, deliberately separated because they fail differently:

1. **State gate** — is the subscription live at all? (`active`, `trialing`,
   `past_due` within grace). Failure → 402, "your trial ended".
2. **Feature gate** — does this plan include this capability?
   Failure → 402, "upgrade to Voice AI".
3. **Quota gate** — is there headroom left this period?
   Failure → 429/402, "you've used 1,000 of 1,000 minutes".

Collapsing these into one boolean is the most common mistake here; the user-facing
message and the correct call-to-action differ for each.

---

## 2. Database schema

### 2.1 Changes to existing tables

**`subscription_plans`** — additions:

```python
slug:            Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
tier:            Mapped[int] = mapped_column(Integer, default=0)   # ordering for up/downgrade logic
entitlements:    Mapped[dict] = mapped_column(JSONB, default=dict) # machine-readable, see 2.3
trial_days:      Mapped[int] = mapped_column(Integer, default=7)
is_trialable:    Mapped[bool] = mapped_column(Boolean, default=True)
stripe_price_id_yearly: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
```

Notes:
- `features` (existing) stays as **marketing copy** — the bullet list the pricing
  page renders. `entitlements` is the **machine-readable** contract the backend
  enforces. Keeping them in one column guarantees they drift.
- `slug` is what code branches on. Never branch on `name` or on a UUID that
  differs between dev and prod.
- The model has `price_yearly` but only one `stripe_price_id`, while the UI ships
  a monthly/yearly toggle. `ensure_stripe_price` papers over this at checkout
  time; store both ids explicitly.

**`subscriptions`** — additions and changes:

```python
# CHANGE: trials have no Stripe object. Stop fabricating `local_trial_<uuid>`.
stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
stripe_customer_id:     Mapped[Optional[str]] = mapped_column(String(255))

# ADD
source:              Mapped[str]  = mapped_column(String(20), default="stripe")  # stripe | trial | manual | comp
cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
grace_period_end:    Mapped[Optional[datetime]]   # set when trial/subscription lapses
expired_at:          Mapped[Optional[datetime]]   # when the reconciler flipped it to expired
trial_converted_at:  Mapped[Optional[datetime]]   # trial → paid; the conversion metric
previous_plan_id:    Mapped[Optional[uuid.UUID]]  # for downgrade-at-period-end
scheduled_plan_id:   Mapped[Optional[uuid.UUID]]  # plan taking effect next period
```

Constraint — replaces the SELECT-then-INSERT race:

```sql
CREATE UNIQUE INDEX uq_one_live_subscription_per_org
  ON subscriptions (organization_id)
  WHERE status IN ('trialing', 'active', 'past_due');
```

Also switch all `DateTime` columns to `DateTime(timezone=True)` and all
`datetime.utcnow()` to `datetime.now(timezone.utc)`. Naive UTC timestamps are
consistent today only because everything is naive; the first tz-aware value
introduced anywhere causes a `TypeError` in a comparison, and the natural place
for that to happen is a trial-expiry check.

### 2.2 New tables

**`subscription_events`** — append-only history. Answers "why is this account in
this state?", which is the single most common billing support question.

```python
id, organization_id, subscription_id
event_type:    str    # trial_started | trial_expiring | trial_expired | trial_converted
                      # | activated | renewed | payment_failed | past_due | canceled
                      # | plan_changed | reactivated | grace_started | grace_ended
from_status:   str | None
to_status:     str | None
from_plan_id:  UUID | None
to_plan_id:    UUID | None
actor_type:    str    # user | system | stripe | admin
actor_id:      UUID | None
stripe_event_id: str | None
payload:       JSONB
created_at:    datetime
```

Never delete or update rows here. Current state is a materialized convenience;
this table is the ledger.

**`processed_stripe_events`** — webhook idempotency. Stripe retries; without
this, a retried `invoice.paid` double-applies.

```python
stripe_event_id: str  (PRIMARY KEY)
event_type:      str
processed_at:    datetime
```

Insert inside the same transaction as the effect. A duplicate-key violation is
the signal to skip, not an error to log.

**`organization_entitlements`** — per-org overrides, so sales can comp an
account or extend a trial without hand-editing subscription rows.

```python
id, organization_id (unique)
overrides:  JSONB    # merged over the plan's entitlements, same shape
reason:     str
expires_at: datetime | None
created_by: UUID
```

**`trial_grants`** — abuse control. Without it, "delete org, sign up again" is
an infinite trial.

```python
id
organization_id
user_id
email_domain:    str          # normalized; blocks gmail+alias churn per-domain for business signups
signup_ip:       str | None
device_hash:     str | None   # optional client fingerprint
granted_at, expires_at
converted:       bool
```

Check on `POST /billing/trial`: refuse a second grant for the same
`(email_domain)` **or** the same verified user, unless an admin overrides.
Keep this advisory-with-logging at first — a hard block will catch legitimate
customers at a company where a second team signs up — so log the collision,
allow it, and review before tightening.

**`payment_records`** — the user asked for this explicitly. We already have
`Invoice` + `PaymentFailure`, which covers 90% of it. Add a thin
`payment_records` table only if we ever take payment outside Stripe (wire,
manual, a second PSP). Until then, do not duplicate Stripe's ledger — reconciling
two payment ledgers is a well-known source of billing bugs. **Recommendation:
skip for now**, and record it as a deliberate decision.

### 2.3 The `entitlements` JSON shape

One schema, used by plans, overrides, and the resolved projection:

```jsonc
{
  "features": {
    "inbound_calls":        true,
    "outbound_calls":       true,
    "outbound_campaigns":   false,   // Voice AI only
    "sms":                  true,
    "email":                true,
    "workflows":            true,
    "workflow_scheduling":  false,   // Voice AI only
    "crm_integrations":     true,
    "knowledge_base":       true,
    "virtual_meetings":     false,   // Voice AI only
    "lead_scoring":         false,   // Voice AI only
    "api_access":           false,   // Voice AI only
    "team_members":         true,
    "custom_voice":         false,
    "white_label":          false
  },
  "limits": {
    "agents":            1,
    "phone_numbers":     1,
    "knowledge_bases":   1,
    "team_members":      2,
    "minutes_per_month": 1000,
    "calls_per_month":   350,
    "sms_per_month":     600,
    "emails_per_month":  2500,
    "workflows":         5,
    "api_keys":          0
  },
  "overage": { "allowed": true, "per_minute": 0.015, "per_call": 0.05 }
}
```

`-1` means unlimited. Absent key means "inherit from the plan" (for overrides).

Keep the existing `max_agents` / `included_minutes` columns as a denormalized
mirror for the pricing page and for cheap SQL reporting, but make
`entitlements` authoritative and populate the columns from it on write.

---

## 3. Trial period tracking

### Store the absolute end timestamp; derive everything else

`trial_end` is already stored — that is correct and should not change. Never
store "days remaining"; a counter must be decremented by something, and that
something will be wrong across timezones, downtime, and DST.

Derive the display value on read:

```python
days_remaining = max(0, ceil((trial_end - now).total_seconds() / 86400))
```

### Answering "is the trial active?" — both request-time and scheduled

This is the question the plan hinges on, so to be explicit:

**Request time (authoritative for access).** `EntitlementService.resolve()`
compares `trial_end` to `now` on every resolve. Access decisions never trust the
stored `status` string alone, because that string is only as fresh as the last
job run. This makes access correct the instant the trial ends, with zero
dependency on the scheduler being healthy.

**Scheduled job (authoritative for side effects and reporting).** A Celery beat
task runs every 15 minutes and reconciles: flips `trialing` → `expired`, writes
the `subscription_events` row, sends the email, releases pooled phone numbers,
pauses scheduled workflows.

Why both, in one line each:
- Cron only → a user keeps full access for up to 15 minutes after expiry, and
  indefinitely if the worker is down. Unacceptable for a metered product.
- Request-time only → nobody ever gets the "your trial ended" email, dashboards
  report a stale status, and pooled resources are never reclaimed.

This "derive on read, reconcile on a schedule" split is what production SaaS
actually does. Stripe itself works this way: the API returns a live-computed
status, and webhooks are the scheduled side-effect channel.

### The status model

Persisted `status` values on `subscriptions`:

| Status | Meaning | Access |
|---|---|---|
| `trialing` | Trial running, `now < trial_end` | Trial entitlements |
| `active` | Paid and current | Plan entitlements |
| `past_due` | Payment failed, inside dunning window | Plan entitlements (degrades at grace end) |
| `grace` | Trial or subscription lapsed, inside grace period | Read-only + billing |
| `expired` | Trial ended without conversion | Read-only + billing |
| `canceled` | User canceled; may still be inside paid period | Full until `current_period_end`, then read-only |
| `incomplete` | Stripe checkout started, not confirmed | No access |

Derived (never persisted, computed in the resolver): `trial_expiring_soon`
(≤ 3 days left), `over_quota`, `in_grace`.

---

## 4. Handling trial expiration

### The reconciler

```python
# backend/app/workers/tasks.py
@celery_app.task(name="billing.reconcile_subscriptions")
def reconcile_subscriptions():
    """Flip lapsed subscriptions and fire the side effects. Idempotent."""
```

Registered in `celery_app.py`, which currently has `beat_schedule={}`:

```python
beat_schedule={
    "reconcile-subscriptions": {
        "task": "billing.reconcile_subscriptions",
        "schedule": crontab(minute="*/15"),
    },
    "trial-expiry-notices": {
        "task": "billing.send_trial_notices",
        "schedule": crontab(hour=9, minute=0),   # daily, 09:00 UTC
    },
    "reset-usage-counters": {
        "task": "billing.reset_period_counters",
        "schedule": crontab(hour=0, minute=5),
    },
}
```

Reconciler logic, in order:

1. `trialing` where `trial_end <= now` → `grace`, set
   `grace_period_end = trial_end + 3d`, emit `trial_expired`, send email,
   invalidate entitlement cache.
2. `grace` where `grace_period_end <= now` → `expired`, emit `grace_ended`,
   release pooled phone numbers, pause scheduled workflows, disable inbound
   routing.
3. `past_due` where `grace_period_end <= now` → `expired` (Stripe's dunning has
   given up), emit `payment_failed_final`.
4. `canceled` where `current_period_end <= now` → `expired`.
5. `active` where `current_period_end <= now` and no Stripe update received →
   **do not expire**; log a reconciliation warning and re-fetch from Stripe.
   Stripe is the truth for paid subscriptions; a missed webhook must never lock
   out a paying customer.

Point 5 matters. The asymmetry is deliberate: **fail closed for trials, fail
open for payers.** The cost of a wrongly-extended trial is a few dollars of
usage. The cost of locking out a paying customer because a webhook was dropped
is a churned account and a support escalation.

Every transition writes a `subscription_events` row and busts the Redis key.
The task must be safe to run twice concurrently — guard each org with a
`SELECT ... FOR UPDATE SKIP LOCKED`.

### Notices

`send_trial_notices` (daily): day 3 ("here's what you haven't tried yet"),
day 6 (1 day left), day 7 (expired), day 10 (grace ending), day 14 (win-back).
Track sent notices in `subscription_events` so a retry never double-sends.

Also subscribe to Stripe's `customer.subscription.trial_will_end` (fires 3 days
out) for card-on-file trials, if we ever add that variant.

---

## 5. User access after the trial ends

### Recommendation: graduated degradation — grace → read-only, never delete

The four options the user asked about, judged against a metered voice product:

**A. Hard block everything.** Pro: maximum upgrade pressure, trivially simple.
Con: the user cannot export their data, cannot see what they built, and cannot
show it to the person who signs off on the purchase. In B2B, the buyer is often
not the trial user — locking the account out kills the internal sell. Also
a support burden ("I just need my call transcripts"). **Reject.**

**B. Limited features (a free tier).** Pro: keeps users in the product,
long-tail conversion. Con: for this product, "limited" still means live phone
calls, which means we pay Twilio and LLM costs indefinitely for a non-paying
account. A free tier is a pricing decision with real COGS, not a lock-screen
decision. **Reject for now** — revisit as an explicit business choice.

**C. Read-only + premium restricted.** Pro: data is visible and exportable,
conversion path stays warm, our variable costs go to zero. Con: slightly more
implementation than A. **Recommended.**

**D. Grace period then read-only.** This is C with a 3-day cushion so a Friday
expiry does not become a Monday emergency, and so a card that fails once does
not immediately break someone's phone line. **Recommended, combined with C.**

### The line to draw

The right boundary is not "read vs write" — it is **"does this action cost us
money at runtime?"**

| Category | After trial/subscription ends |
|---|---|
| **Runtime** — answer inbound calls, place outbound calls, run agents, execute workflows, send SMS/email, KB ingestion | **Hard off.** This is where Twilio/LLM spend happens. Inbound calls get a polite recorded message and hang up; they must not reach the agent runtime. |
| **Data read** — view agents, prompts, call history, transcripts, recordings, analytics, exports | **Full read-only access, retained.** |
| **Config write** — edit agents, workflows, tools, KB | **Blocked** with an inline upgrade prompt. Nothing is deleted. |
| **Billing / settings / team** | **Fully open.** They must be able to pay us and to change who can. |
| **Phone numbers** | Trial numbers (from the shared pool) are released at grace end; the user is warned twice first. Customer-owned numbers on their own Twilio are untouched. |

**Data retention:** keep everything for 60 days after expiry, warn by email at
30 and 55 days, then purge recordings and transcripts (the expensive storage)
while keeping metadata for another 6 months. Never silently delete.

**Reactivation must be instant and lossless.** Paying on day 45 restores exactly
the prior state — same agents, same prompts, same history. If reactivation is
not seamless, the read-only period buys nothing.

---

## 6. Feature access matrix

The two paid plans are $119 Sales Chatbot and $359 Voice AI, already seeded in
`backend/app/services/billing/seed_plans.py`.

### Trial design decision: trial the *top* plan, meter it hard

Today `_get_trial_plan()` (`billing.py:665`) defaults to the **first plan by
sort_order** — Sales Chatbot, the cheaper one. Change this to trial **Voice AI**.

The reasoning: trials convert on feature discovery, not on volume. A user who
never sees lead scoring or campaigns has no reason to pick the $359 plan, so
defaulting to the cheap plan caps our own ARPU. The cost risk is not features —
it is minutes and calls, and those get their own tight caps. Be generous with
capability, strict with consumption.

### Matrix

Legend: ✅ full · 🔶 limited · 👁 read-only · ❌ blocked

| Capability | Trial (7d) | Sales Chatbot $119 | Voice AI $359 | Expired / none |
|---|---|---|---|---|
| **Volume** ||||
| Voice minutes / mo | 🔶 60 | 1,000 | 3,000 | ❌ 0 |
| Calls / mo | 🔶 25 | 350 | 600 | ❌ 0 |
| SMS / mo | 🔶 25 | 600 | 1,000 | ❌ 0 |
| Emails / mo | 🔶 100 | 2,500 | 5,000 | ❌ 0 |
| Overage billing | ❌ hard stop | ✅ $0.015/min | ✅ $0.015/min | ❌ |
| **Resources** ||||
| AI agents | 🔶 1 | 1 | 5 | 👁 |
| Phone numbers | 🔶 1 (pooled, reclaimed) | 1 | 5 | 👁 |
| Knowledge bases | 🔶 1 (10 MB) | 1 | 5 | 👁 |
| Team members | 🔶 2 | 3 | 10 | 👁 |
| Workflows | 🔶 2 | 5 | unlimited | 👁 |
| **Features** ||||
| Inbound calls | ✅ | ✅ | ✅ | ❌ |
| Outbound calls | ✅ | ✅ | ✅ | ❌ |
| Outbound campaigns | ❌ | ❌ | ✅ | ❌ |
| Real-time conversational AI | ✅ | ✅ | ✅ | ❌ |
| CRM integrations | ✅ | ✅ | ✅ | 👁 config |
| Scheduling & follow-up | ✅ | ✅ | ✅ | ❌ |
| Workflow builder | ✅ | ✅ | ✅ | 👁 |
| Scheduled/triggered workflows | ❌ manual runs only | ❌ | ✅ | ❌ |
| Virtual meetings & note taking | ✅ | ❌ | ✅ | ❌ |
| Lead scoring & data enrichment | ✅ | ❌ | ✅ | ❌ |
| Analytics dashboard | 🔶 7d window | ✅ 90d | ✅ unlimited | 👁 |
| Data export (CSV) | ✅ | ✅ | ✅ | ✅ **always** |
| Call recordings & transcripts | ✅ | ✅ | ✅ | 👁 60d then purge |
| Public API + API keys | ❌ | ❌ | ✅ | ❌ |
| Webhooks | ❌ | 🔶 3 | ✅ unlimited | ❌ |
| Custom voice cloning | ❌ | ❌ | ✅ | ❌ |
| White-label / remove branding | ❌ | ❌ | ✅ | ❌ |
| Support | Docs + email | Email | Priority | Email |
| **Account** ||||
| Billing & settings | ✅ | ✅ | ✅ | ✅ **always** |
| Invite/manage team | 🔶 2 | ✅ | ✅ | 👁 |
| Delete own data | ✅ | ✅ | ✅ | ✅ **always** |

Three rows are non-negotiable regardless of billing state: **billing access,
data export, and account deletion.** Blocking any of those creates legal
exposure under GDPR/CCPA and reads as hostage-taking.

### Trial-specific rules

- **No overage on trial. Ever.** At 60 minutes the runtime stops. A trial with
  metered overage and no card on file is an unbounded liability.
- Trial phone numbers come from the shared Voicecon Twilio pool and are released
  at grace end. Today `POST /onboarding/phone-number` buys a real number with no
  subscription check at all — that is a live cost and fraud surface.
- Outbound calls on trial restricted to numbers verified by the trial user (a
  standard anti-fraud measure; Twilio does the same for its own trials).
- Watermark: a short "powered by Voicecon" on transcripts/exports. Cheap
  conversion pressure, no functional cost.

---

## 7. Access control architecture

### The four approaches, and what each is actually for

**RBAC — "who is this person in this workspace?"** Already built and good.
`owner > admin > member > viewer`, permission sets in `permissions.py`. Keep
exactly as is.

**Permission-based (ABAC-lite) — "what actions map to that role?"** Also already
built: `AGENTS_WRITE`, `BILLING_MANAGE`, etc., checked via `require_permission`.
Keep as is.

**Subscription feature flags — "what did this organization buy?"** Missing.
This is the new axis.

**Middleware / policy-based authorization — "where is it enforced?"** This is an
enforcement question, not a model question, and the answer is: a dependency at
the HTTP boundary *plus* a service-level function for non-HTTP paths.

### Recommendation: keep RBAC, add entitlements as an orthogonal axis

Do **not** encode plans as roles ("voice_ai_user"). Roles and plans are
independent dimensions: a *viewer* on Voice AI and an *owner* on Sales Chatbot
are both legitimate, and the cross product of roles × plans as roles is
unmaintainable. Every action is authorized by a two-part answer:

> **RBAC: may *you* do this?  ×  Entitlement: did your *org* buy this?**

Both must pass. They are checked independently and produce different HTTP
statuses — 403 for the first, **402 Payment Required** for the second. That
distinction is what lets the frontend show "ask your admin" versus "upgrade
your plan" without string-matching error messages.

### The service

```python
# backend/app/services/billing/entitlements.py

@dataclass(frozen=True)
class Entitlements:
    organization_id: uuid.UUID
    plan_slug: str | None
    plan_name: str | None
    status: str                  # trialing | active | past_due | grace | expired | none
    is_live: bool                # runtime allowed
    is_read_only: bool
    trial_end: datetime | None
    days_remaining: int | None
    grace_period_end: datetime | None
    features: frozenset[str]
    limits: Mapping[str, int]
    usage: Mapping[str, int]

    def has(self, feature: str) -> bool:
        return self.is_live and feature in self.features

    def within(self, limit: str, requested: int = 1) -> bool:
        cap = self.limits.get(limit, 0)
        return cap == -1 or self.usage.get(limit, 0) + requested <= cap


class EntitlementService:
    async def resolve(self, db, org_id, *, fresh: bool = False) -> Entitlements:
        """Cached 60s in Redis. Applies expiry at read time — never trusts
        the stored status alone."""

    async def invalidate(self, org_id) -> None:
        """Called from webhooks, checkout, trial start, plan change, reconciler."""
```

### Enforcement — three call sites, one implementation

```python
# 1. HTTP boundary — mirrors require_permission's shape exactly
@router.post("/", dependencies=[
    Depends(require_permission(perms.AGENTS_WRITE)),   # who
    Depends(require_entitlement(limit="agents")),      # what was bought
])
async def create_agent(...): ...

@router.post("/campaigns", dependencies=[
    Depends(require_permission(perms.CALLS_WRITE)),
    Depends(require_entitlement(feature="outbound_campaigns")),
])
async def start_campaign(...): ...
```

```python
# 2. Non-HTTP boundary — the one that actually protects revenue.
# services/telephony inbound handler, before the agent runtime starts:
ent = await entitlements.resolve(db, org_id)
if not ent.has("inbound_calls") or not ent.within("minutes_per_month"):
    return twiml_polite_decline()   # never reaches STT/LLM/TTS
```

```python
# 3. Scheduler — services/workflows/scheduler.py, before enqueuing a run:
if not ent.has("workflow_scheduling"):
    await pause_schedule(schedule_id, reason="entitlement")
    continue
```

### Router-level default

Follow the pattern already established by `workspace_guard` in
`app.api.v1.api`: attach a router-level `entitlement_guard` so a newly added
endpoint is gated by default rather than open by default. Endpoints needing
something finer add their own `require_entitlement`.

Explicitly **exempt** from the guard: `/auth/*`, `/billing/*`, `/workspaces/*`,
`/onboarding/*`, `/health`, and every `GET` that only reads data. An expired
account must always be able to log in, look at its data, and pay.

### The 402 contract

```json
{
  "detail": "Your plan does not include outbound campaigns.",
  "code": "entitlement_required",
  "reason": "feature_not_in_plan",
  "feature": "outbound_campaigns",
  "current_plan": "sales-chatbot",
  "required_plans": ["voice-ai"],
  "upgrade_url": "/dashboard/settings/billing"
}
```

For a quota failure, `reason: "limit_exceeded"` plus `limit`, `used`, `cap`.
For a dead subscription, `reason: "subscription_inactive"` plus `status` and
`grace_period_end`. Machine-readable `reason` is what makes a single global
frontend interceptor possible.

---

## 8. Backend workflow

### 8.1 Registration

Unchanged. Create user + org + owner membership. **Do not auto-start a trial** —
the trial clock should start when the user reaches the product, not when they
click "sign up" and then go to lunch. Onboarding step stays `company`.

### 8.2 Start free trial — `POST /api/v1/billing/trial`

```
1. require_permission(BILLING_MANAGE)                    → 403
2. Reject if org already has a live subscription         → 409 (rely on the
   unique index; catch IntegrityError rather than SELECT-then-INSERT)
3. Refuse a repeat trial → 409 trial_already_used. Three arms, in order:
     a. this ORGANIZATION already has a trial_grant, or any subscription
        with source='trial' (covers grants the ledger never saw). Without
        this arm a second admin restarts the workspace trial forever.
     b. this USER already has a trial_grant, in any organization
     c. this EMAIL DOMAIN already has one — log-and-allow by default
        (BLOCK_REPEAT_TRIALS_BY_DOMAIN)
4. Require a verified email                              → 403 (blocks throwaway churn)
5. plan = Voice AI (is_trialable, highest tier)
6. INSERT subscriptions(status='trialing', source='trial',
     stripe_subscription_id=NULL, trial_start=now,
     trial_end=now + plan.trial_days, current_period_start/end = same)
7. INSERT trial_grants + subscription_events('trial_started')
8. Mark onboarding done                                  [exists]
9. entitlements.invalidate(org_id)
10. Enqueue welcome email + schedule day-3/6/7 notices
```

All of steps 6–8 in one transaction.

### 8.3 Trial active

Nothing scheduled runs per-org. `resolve()` computes live state per request.

### 8.4 Trial expires

Reconciler, per section 4: `trialing` → `grace` (3d) → `expired`, each step
emitting an event, an email, and a cache invalidation, and the grace-end step
releasing pooled numbers and pausing schedules.

### 8.5 Upgrade to paid — this is where the current bug is

`/billing/checkout` today rejects any org with a live subscription, including a
trialing one, which blocks the entire conversion path. Rework:

```
1. Load the live subscription.
2. If none → create a new Stripe subscription (today's path).
3. If status is trialing/grace/expired and source == 'trial':
     a. Create/reuse the Stripe customer, attach the payment method.
     b. Create the Stripe subscription (no trial_period_days — the trial
        was ours, not Stripe's).
     c. UPDATE the same row in place: plan_id, stripe ids, status from
        Stripe, source='stripe', trial_converted_at=now,
        current_period_* from Stripe.
     d. Event 'trial_converted'. Restore anything grace/expiry released.
4. If status is active → this is a plan change, not a checkout (see 8.7).
5. entitlements.invalidate(org_id).
```

Updating the row in place rather than inserting a second one keeps the unique
index satisfied and preserves the trial→paid link for cohort analysis.

Idempotency: pass a client-supplied `Idempotency-Key` through to Stripe so a
double-clicked upgrade button cannot create two subscriptions.

### 8.6 Renewal / payment failure

Driven by Stripe webhooks (all wrapped in `processed_stripe_events`):

- `invoice.paid` → status `active`, roll `current_period_*`, **reset
  `current_period_minutes`/`current_period_calls` to 0**, event `renewed`.
  (Resetting on the invoice, not on a calendar cron, is what keeps the counters
  aligned with the actual billing period.)
- `invoice.payment_failed` → status `past_due`, `grace_period_end = now + 7d`,
  event, dunning email. Access continues during dunning — Stripe retries four
  times over ~2 weeks and most failures self-resolve.
- `customer.subscription.updated` → mirror status, plan, period, and
  `cancel_at_period_end`.
- `customer.subscription.deleted` → `canceled`; access persists until
  `current_period_end`, then the reconciler moves it to `expired`.
- `customer.subscription.trial_will_end` → **add**; notice email.

### 8.7 Plan change

**Upgrade** ($119 → $359): immediate, Stripe prorates
(`proration_behavior="create_prorations"`). New entitlements apply at once.

**Downgrade** ($359 → $119): effective at `current_period_end`. Set
`scheduled_plan_id` and keep current entitlements until then. Before accepting,
validate that the org fits the target plan's limits — 5 agents cannot fit in a
1-agent plan. Return 409 with an explicit list of what must be removed first:

```json
{ "code": "downgrade_blocked",
  "conflicts": [{"resource": "agents", "current": 5, "allowed": 1}] }
```

Never silently delete resources to make a downgrade fit.

### 8.8 Cancel

Default to `cancel_at_period_end = true` — the user keeps what they paid for.
Immediate cancellation with proration only on explicit request. Offer a **pause**
(1–3 months) in the cancel flow; it recovers a meaningful share of would-be
churn. On cancel, always show what happens to their data and when.

---

## 9. Frontend behavior

### Hydration

Add entitlements to the `GET /workspaces/current` payload that
`useWorkspaceStore` already fetches once per session
(`frontend/src/store/workspaceStore.ts`) — no extra round trip. Add a dedicated
`GET /billing/entitlements` for explicit refresh after checkout and after a 402.

New `useEntitlements()` hook mirroring the existing `can()` pattern, with the
same caveat that already sits in the store's docstring: **presentation only,
never the security boundary.**

```tsx
const { has, within, status, daysRemaining, isReadOnly } = useEntitlements()

<Gated feature="outbound_campaigns" fallback={<UpgradeCard plan="voice-ai" />}>
  <CampaignBuilder />
</Gated>
```

### State-by-state UI

| State | Banner | Nav / actions | Prompts |
|---|---|---|---|
| **Trial active (>3d)** | Slim neutral bar: "Trial · 5 days left · Upgrade" | Everything enabled | Usage meter in sidebar (`18 / 60 min`) |
| **Trial expiring (≤3d)** | Amber, persistent, dismissible per session: "Trial ends Friday. Add a card to keep your number." | Everything enabled | Day-6 in-app modal, once |
| **Trial expired / grace** | Red, **not dismissible**: "Trial ended. Your agents are paused. Upgrade to resume — data kept 60 days." | Write actions disabled with tooltips; runtime toggles off | Full-page upgrade wall on Agents/Calls; dashboard stays readable |
| **Active subscription** | None | Everything enabled | Amber toast at 80% of quota, red at 100% |
| **Past due** | Amber: "Payment failed. We'll retry in 3 days — update your card." | Everything still enabled | Email + in-app |
| **Expired / canceled** | Red: "Subscription ended." | Read-only everywhere | Export button promoted |

### Rules

- **Never hide gated features — show them disabled with a lock and a reason.**
  Hidden features cannot be upsold. A greyed "Lead Scoring 🔒 Voice AI" row is
  an advertisement; an absent row is a lost sale.
- **One banner maximum**, by priority: expired > past due > expiring > quota >
  none. Stacked banners get ignored wholesale.
- Global axios interceptor on 402 → open the upgrade modal pre-filled from the
  `feature` / `required_plans` fields; never surface a raw error toast.
- Optimistic UI must not skip the server check. `within()` client-side prevents
  a doomed request; the 402 is still the authority.
- After a successful checkout, refetch entitlements before navigating, so the
  user does not land on a dashboard still rendering trial state.

---

## 10. Best practices, edge cases, and what to avoid

### Security

- Never trust a client-supplied `plan_id` for pricing — resolve the price
  server-side from the DB (already done in `checkout`; keep it that way).
- Verify every webhook signature; never act on an unsigned payload.
- Entitlement checks belong on the server. The frontend gate is UX.
- `BILLING_MANAGE` is admin+ in the current matrix, `BILLING_READ` too — correct.
  Consider making plan *changes* owner-only, since an admin can currently
  triple the bill.
- Log every entitlement denial with org, feature, and reason. This is both an
  audit trail and the best available signal for "which paywall is people
  hitting?" — that is upsell data.
- Rate-limit `/billing/trial` per IP and per email domain.

### Scalability

- Cache resolved entitlements in Redis, 60s TTL, keyed `ent:{org_id}:{version}`,
  invalidated explicitly on every write path. 60s is short enough that a missed
  invalidation self-heals.
- Never JOIN plans in a hot request path — the cached projection carries
  everything.
- Usage counters (`current_period_minutes`) update on call completion, not
  mid-call. For quota checks during a call, poll the cheap counter and cut off
  at the boundary.
- Under high concurrency, increment counters with an atomic `UPDATE ... SET x =
  x + n` rather than read-modify-write.

### Maintainability

- One matrix, one place: `entitlements` JSON on the plan row. If a limit is
  hardcoded in an `if` statement anywhere in the codebase, it is a bug.
- Never branch on plan name or UUID — branch on `slug` or, better, on a feature
  key. `if ent.has("lead_scoring")` survives a plan rename; `if plan.name ==
  "Voice AI"` does not.
- Feature keys are a public contract once the frontend uses them. Add, don't
  rename.
- Seed plans idempotently and keep dev/staging/prod slugs identical.

### Performance

- Entitlement resolution must be < 5 ms cached. It runs on nearly every request.
- The reconciler processes in batches with `SKIP LOCKED`; it must not table-lock
  `subscriptions`.
- Index `subscriptions (status, trial_end)` and `(status, current_period_end)`
  for the reconciler's scans.

### Edge cases to handle explicitly

| Case | Handling |
|---|---|
| Trial expires mid-call | Let the in-flight call finish. Cutting a live conversation is worse than eating 40 seconds of cost. Block the *next* one. |
| Clock skew / DST | `timezone.utc` everywhere, `DateTime(timezone=True)` columns. |
| Webhook arrives before the API response persists | Idempotent handlers + look up by `stripe_subscription_id`; retry with backoff if the row is not there yet. |
| Duplicate webhook | `processed_stripe_events` primary key. |
| User signs up twice for a trial | `trial_grants` check. |
| Org has 5 agents, downgrades to 1-agent plan | Block with a conflict list. Never auto-delete. |
| Payment succeeds while status is `expired` | Reactivate in place and restore released resources where possible; a released phone number may be gone — say so before releasing it. |
| Stripe is down at checkout | 503 with a retry, no partial local row. |
| Stripe unconfigured (current dev default) | Trial path must keep working with no Stripe at all — already true, keep it. |
| Org deleted with a live subscription | Cancel in Stripe first, then soft-delete. |
| Two admins upgrade simultaneously | Idempotency key + unique index. |

### The mistakes to avoid

1. **Storing "days remaining" instead of an end timestamp.** Guaranteed drift.
2. **Cron-only expiry.** Worker down = free product.
3. **Checking entitlements only in HTTP middleware.** In this codebase that
   leaves the inbound-call webhook and the workflow scheduler — the two most
   expensive paths — completely ungated.
4. **Overage on a trial with no card.** Unbounded liability.
5. **Deleting data at expiry.** Kills win-back and creates support load.
6. **403 for a billing problem.** The frontend cannot tell "ask your admin"
   from "upgrade your plan". Use 402.
7. **Plans as roles.** Unmaintainable cross product.
8. **Hiding locked features.** No upsell surface.
9. **Trusting the persisted `status` string for access.** It is only as fresh as
   the last reconciler run.
10. **Two payment ledgers.** Let Stripe own payment truth; mirror, don't
    duplicate.
11. **Blocking the paying customer on a missed webhook.** Fail closed for
    trials, fail open for payers.

---

## 11. API surface

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | `/billing/plans` | Public plan list | **[exists]** |
| GET | `/billing/config` | Stripe publishable key | **[exists]** |
| GET | `/billing/subscription` | Current subscription | **[exists]** |
| POST | `/billing/trial` | Start trial | **[exists]** — rework per 8.2 |
| POST | `/billing/checkout` | First paid subscription **+ trial conversion** | **[exists]** — fix per 8.5 |
| GET | `/billing/entitlements` | Resolved entitlements + usage | **new** |
| POST | `/billing/subscription/change-plan` | Up/downgrade | rework of existing update |
| POST | `/billing/subscription/cancel` | Cancel at period end | **[exists]** — verify |
| POST | `/billing/subscription/reactivate` | Undo a pending cancel | **new** |
| GET | `/billing/usage` | Current-period usage | **[exists]** |
| GET | `/billing/invoices` | Invoice history | **[exists]** |
| GET | `/billing/events` | Subscription history (support/audit) | **new** |
| POST | `/billing/portal` | Stripe Customer Portal session | **new** — cheapest way to get card updates, tax, and dunning UI |
| POST | `/billing/webhook` | Stripe webhooks | **[exists]** — add idempotency + `trial_will_end` |
| PATCH | `/admin/orgs/{id}/entitlements` | Comps / trial extension | **new**, staff only |

`GET /workspaces/current` gains an `entitlements` block alongside `permissions`.

**Consider the Stripe Customer Portal seriously.** It gives card updates, invoice
history, cancellation, and tax handling for roughly a day of work, versus weeks
of building and maintaining equivalents. Keep plan selection in-app (it's part of
the product experience) and delegate payment-method management to the portal.

---

## 12. Rollout

**Phase 1 — stop the bleeding (highest value, ~2–3 days)**
1. `EntitlementService` + Redis cache + `resolve()` with read-time expiry.
2. Reconciler task + beat schedule + `subscription_events`.
3. Fix `/billing/checkout` so trialing users can convert (8.5).
4. Gate the inbound-call path and the outbound-call path on `is_live`.

After phase 1 the two revenue-critical bugs — trials that never end and a
conversion path that 400s — are closed.

**Phase 2 — schema (~2 days)**
Alembic migration: `slug`, `tier`, `entitlements`, `trial_days`,
`stripe_price_id_yearly`; nullable `stripe_subscription_id`; new columns on
`subscriptions`; `subscription_events`, `processed_stripe_events`,
`trial_grants`, `organization_entitlements`; the partial unique index;
tz-aware timestamps. Backfill: existing `local_trial_*` ids → `NULL` with
`source='trial'`; derive `slug` from name; build `entitlements` from the
existing `max_*` columns.

**Phase 3 — enforcement (~3 days)**
`require_entitlement` dependency, router-level guard with the exemption list,
per-resource limit checks (agents, numbers, KBs, team, workflows), scheduler
gate, quota enforcement in `usage_tracker` (replace `within_limit = True`),
402 contract.

**Phase 4 — frontend (~3 days)**
`useEntitlements`, `<Gated>`, banner system, 402 interceptor, upgrade modal,
usage meters, read-only mode.

**Phase 5 — lifecycle polish (~2 days)**
Notice emails, grace handling, pooled-number release, downgrade conflict
checks, Customer Portal, admin overrides.

### Testing

- Unit: `resolve()` across every status × plan × clock-offset combination.
- Reconciler: freeze time, assert exactly one transition and one event per run;
  assert running it twice is a no-op.
- Webhooks: replay the same event id twice, assert single application.
- Integration: full lifecycle — register → trial → expire → grace → expire →
  pay → active → downgrade → cancel — asserting entitlements at each step.
- Concurrency: two simultaneous `/billing/trial` calls produce one subscription.
- The existing suite already has DB/plugin quirks; add these under
  `backend/tests/unit/test_entitlements.py` and
  `backend/tests/integration/test_subscription_lifecycle.py`.

### Metrics worth instrumenting from day one

Trial starts, trial→paid conversion rate and time-to-convert, which paywall each
402 came from (upsell signal), grace-period recoveries, involuntary churn from
failed payments, and quota-exhaustion rate per plan.
