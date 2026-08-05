# Voicecon — End-to-End Process Flow

This document describes the complete Voicecon user journey — from a first-time signup to a
completed AI voice call and its analytics — and records the verification status of every module
along the way. It is the single "whole flow" reference; the per-feature guides in [docs/](.)
cover individual subsystems in depth.

---

## 1. Scope

| | |
|---|---|
| **Goal** | Confirm every module works, and works *together*, along the real user journey |
| **Method** | Manual walkthrough on a clean account + existing automated suites |
| **Environment** | Local dev (see below) |
| **Deliverables** | This document, the test matrix (§4), the defect log (§5), and the Q/A gate (§6) |

### Test environment

| Service | Where | Notes |
|---|---|---|
| Backend (FastAPI) | `http://localhost:8001` | `./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload` |
| Frontend (Next.js) | `http://localhost:3000` | `npm run dev` |
| Postgres | `localhost:5435` | Docker container `voicecon_postgres` |
| API base path | `/api/v1` | routers registered in [api.py](../backend/app/api/v1/api.py) |

> `FRONTEND_URL` in `backend/.env` must match the frontend port — it builds the links inside
> invitation and verification emails. See defect **D-001** in §5.

---

## 2. The flow at a glance

```mermaid
flowchart TD
    A[Sign up] --> B[Gmail verification code]
    B --> C[Onboarding wizard]
    C --> D[Workspace created + default Twilio account]
    D --> E[Provision / connect phone number]
    E --> F[Create agent]
    F --> G[Attach tools + knowledge base]
    G --> H[Attach workflow]
    H --> I{Call}
    I -->|Inbound| J[Twilio webhook -> agent answers]
    I -->|Outbound| K[POST /calls -> Twilio dials]
    J --> L[Realtime voice stream WS]
    K --> L
    L --> M[Transcript + recording stored]
    M --> N[Analytics + usage metering]
    N --> O[Billing / plan limits]
    C --> P[Invite teammates]
    P --> Q[Accept invite -> team workspace]
    F --> R[Integrations + notifications]
```

Two parallel branches hang off the main line: **team collaboration** (invite → accept → roles)
and **integrations/notifications**, which feed data outward during and after calls.

---

## 3. Stage-by-stage walkthrough

Legend: ✅ verified manually · ⏳ pending · 🔁 covered by an automated suite

### 3.1 Authentication & email verification ✅

| | |
|---|---|
| **Frontend** | [/(auth)](../frontend/src/app/(auth)) |
| **Endpoints** | `POST /auth/register`, `/auth/email/send-code`, `/auth/email/verify-code`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/password/forgot`, `/auth/password/reset`, `/auth/google`, `/auth/apple`, `GET /auth/providers` |
| **Tests** | 🔁 [test_auth_api.py](../backend/tests/integration/test_auth_api.py), [test_auth_verification_api.py](../backend/tests/integration/test_auth_verification_api.py), [test_auth_service.py](../backend/tests/unit/test_auth_service.py), [auth.spec.ts](../frontend/e2e/auth.spec.ts) |

**Steps:** register with a real address → receive the 6-digit code by email → verify → land
authenticated. Password reset follows the same code path. Social login stays disabled until
`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` are set; `/auth/providers` reports availability.

**Expected:** unverified accounts cannot proceed; codes expire; a verified user receives access +
refresh tokens and is routed to onboarding.

**Status:** ✅ Verified manually — Sajid Ali, 2026-08-03.

---

### 3.2 Onboarding ✅

| | |
|---|---|
| **Frontend** | [/onboarding](../frontend/src/app/onboarding) |
| **Endpoints** | `GET /onboarding/status`, plus the wizard submission routes in [onboarding.py](../backend/app/api/v1/endpoints/onboarding.py) |

**Steps:** complete the wizard → workspace is created → the default Twilio account is attached so
a brand-new user can reach a working calling setup without bringing their own credentials.

**Expected:** `GET /onboarding/status` flips to complete; the dashboard becomes reachable; the
default telephony provider is present.

**Status:** ✅ Verified manually — Sajid Ali, 2026-08-03.

---

### 3.3 Team, workspaces & invitations ✅

| | |
|---|---|
| **Frontend** | [settings/team](../frontend/src/app/dashboard/settings/team), [invite/[token]](../frontend/src/app/invite/[token]), [WorkspaceSwitcher.tsx](../frontend/src/components/layout/WorkspaceSwitcher.tsx) |
| **Endpoints** | `GET/POST /team/members`, `POST /team/invite`, `GET /team/invitations`, `DELETE /team/invitations/{id}`, `PATCH /team/members/{id}`, `DELETE /team/members/{id}`, `GET /invitations/{token}`, `POST /invitations/{token}/accept`, `POST /invitations/{token}/reject`, `/workspaces/*` |
| **Tests** | 🔁 [test_invitations_api.py](../backend/tests/integration/test_invitations_api.py), [test_workspaces_api.py](../backend/tests/integration/test_workspaces_api.py), [test_permissions.py](../backend/tests/unit/test_permissions.py) |
| **Guide** | [TEAM_WORKSPACES_GUIDE.md](TEAM_WORKSPACES_GUIDE.md) |

**Steps:** owner invites by email → invitee receives the email → clicks **Accept invitation** →
joins the workspace with the assigned role → the workspace switcher lists both workspaces →
role changes and removal take effect immediately.

**Expected:** the emailed link resolves to a live invite page; tokens expire after 7 days;
role permissions are enforced server-side, not only in the UI.

**Status:** ✅ Verified manually — Sajid Ali, 2026-08-03. One defect found and fixed (**D-001**).

---

### 3.4 Phone numbers & telephony setup ✅

| | |
|---|---|
| **Frontend** | [phone-numbers](../frontend/src/app/dashboard/phone-numbers) |
| **Endpoints** | `GET /phone-numbers/providers`, `GET /phone-numbers/search`, `POST /phone-numbers/provision`, `GET/PATCH/DELETE /phone-numbers/{id}` |
| **Tests** | 🔁 [test_phone_numbers_api.py](../backend/tests/integration/test_phone_numbers_api.py), [test_number_providers.py](../backend/tests/unit/test_number_providers.py) |

**Steps:** search available numbers by country/area → provision → assign to an agent. Twilio and
Telnyx are both registered in the provider registry.

**Expected:** a provisioned number appears in the list with its webhook wired to the agent's
voice URL.

**Status:** ✅ Verified manually — Sajid Ali, 2026-08-03.

---

### 3.5 Agents ✅

| | |
|---|---|
| **Frontend** | [agents](../frontend/src/app/dashboard/agents) |
| **Endpoints** | `POST/GET /agents`, `GET/PATCH/DELETE /agents/{id}`, `POST /agents/{id}/clone`, `POST /agents/{id}/test`, `POST /agents/{id}/speak` |
| **Tests** | 🔁 [test_agent_api.py](../backend/tests/integration/test_agent_api.py), [test_agent_service.py](../backend/tests/unit/test_agent_service.py), [agent-creation.spec.ts](../frontend/e2e/agent-creation.spec.ts) |

**Steps:** create an agent (prompt, voice, model) → test it in the builder → clone → edit → delete.

**Status:** ✅ Verified manually — Sajid Ali, 2026-08-03.

---

### 3.6 Tools ✅

| | |
|---|---|
| **Frontend** | [tools](../frontend/src/app/dashboard/tools) |
| **Endpoints** | `POST/GET /tools`, `GET/PATCH/DELETE /tools/{id}`, `POST /tools/{id}/test`, `GET /tools/agents/{agent_id}/tools`, `POST/DELETE /tools/agents/{agent_id}/tools/{tool_id}` |
| **Tests** | 🔁 [test_agent_tool_chain.py](../backend/tests/unit/test_agent_tool_chain.py) |

**Steps:** define a tool → test it standalone → attach to an agent → confirm the agent can call it.

**Status:** ✅ Verified manually — Sajid Ali, 2026-08-03.
**Note:** tool execution *during a live call* is part of the pending call test (§3.10).

---

### 3.7 Knowledge base ✅

| | |
|---|---|
| **Frontend** | [knowledge](../frontend/src/app/dashboard/knowledge) |
| **Endpoints** | `POST/GET /knowledge-bases`, `GET/DELETE /knowledge-bases/{id}`, `POST /documents`, `POST /documents/upload`, `GET /knowledge-bases/{id}/documents`, `GET /documents/{id}/download` |
| **Guide** | [RAG_KNOWLEDGE_BASE_GUIDE.md](RAG_KNOWLEDGE_BASE_GUIDE.md) |

**Steps:** create a KB → upload documents → confirm indexing → attach to an agent → confirm
retrieval in agent responses.

**Status:** ✅ Verified manually — Sajid Ali, 2026-08-03.

---

### 3.8 Integrations ✅

| | |
|---|---|
| **Frontend** | [integrations](../frontend/src/app/dashboard/integrations) |
| **Endpoints** | `GET /integrations`, `GET /integrations/connectors`, `POST /integrations/oauth/authorize`, `/oauth/callback`, `/oauth/refresh`, `POST/GET /integrations/connections` |
| **Tests** | 🔁 [test_integration_api.py](../backend/tests/integration/test_integration_api.py), [test_integration_services.py](../backend/tests/unit/test_integration_services.py), [integration-workflow.spec.ts](../frontend/e2e/integration-workflow.spec.ts) |

**Steps:** browse connectors → OAuth authorize → callback stores the connection → token refresh →
data flows on trigger.

**Status:** ✅ Verified manually — Sajid Ali, 2026-08-03.

---

### 3.9 Notifications, chat widget, API keys, user settings ✅

| Module | Endpoints | Status |
|---|---|---|
| Notifications | `GET /notifications`, `/unread-count`, `POST /{id}/read`, `/read-all` | ✅ 2026-08-03 |
| Chat widget | `GET /chat/public/{key}/config`, `POST /chat/public/{key}/message`, `GET /chat/widget.js` | ✅ 2026-08-03 |
| API keys | `GET /api-keys/scopes`, `POST/GET /api-keys`, `PATCH /{id}`, `POST /{id}/regenerate`, `DELETE /{id}` | ✅ 2026-08-03 |
| User settings | `GET/PATCH /users/me`, `POST /users/me/change-password`, `DELETE /users/me` | ✅ 2026-08-03 |

🔁 [test_chat_widget.py](../backend/tests/unit/test_chat_widget.py), [test_settings_api.py](../backend/tests/integration/test_settings_api.py)

---

### 3.10 Calls — inbound & outbound ⚙️ **IMPLEMENTED — live-call verification pending**

| | |
|---|---|
| **Frontend** | [calls](../frontend/src/app/dashboard/calls) |
| **Endpoints** | `POST /calls`, `GET /calls`, `GET /calls/stats`, `GET /calls/{id}`, `DELETE /calls/{id}`, `GET /calls/contacts`, `WS /calls/ws/{agent_id}` |
| **Webhooks** | `POST /telephony/twilio/voice/{agent_id}` (inbound), `POST /telephony/twilio/status`, `POST /telephony/twilio/voice-outbound`, `GET /telephony/twilio/call/{sid}/details`, plus the Telnyx equivalents |
| **Voice stream** | `WS /voice/stream/{call_id}`, `GET /voice/sessions/active`, `GET /voice/sessions/{call_id}` |
| **Tests** | 🔁 [test_call_api.py](../backend/tests/integration/test_call_api.py), [test_call_manager.py](../backend/tests/unit/test_call_manager.py), [test_voice_roundtrip.py](../backend/tests/unit/test_voice_roundtrip.py), [test_twilio_webhook_validation.py](../backend/tests/unit/test_twilio_webhook_validation.py), [call-flow.spec.ts](../frontend/e2e/call-flow.spec.ts) |
| **Guide** | [TWILIO_SETUP_AND_TESTING.md](TWILIO_SETUP_AND_TESTING.md) |

#### Implementation status

The calling module is **fully implemented** on both directions and both providers:

- **Inbound:** the provisioned number's voice webhook points at
  `POST /telephony/twilio/voice/{agent_id}` (Telnyx equivalent at `/telephony/telnyx/voice/{agent_id}`),
  which answers the call and opens the media stream for that agent.
- **Outbound:** `POST /calls` creates the call record and places the dial; Twilio then fetches
  TwiML from `POST /telephony/twilio/voice-outbound`.
- **Realtime audio:** `WS /voice/stream/{call_id}` carries the bidirectional audio session
  (STT → LLM → TTS), with live sessions inspectable via `GET /voice/sessions/active` and
  `GET /voice/sessions/{call_id}`.
- **Lifecycle:** `POST /telephony/twilio/status` receives progress callbacks and moves the call
  record through its states to `completed`.
- **Retrieval:** `GET /calls`, `GET /calls/{id}`, `GET /calls/stats`, `GET /calls/contacts`, and
  the per-contact history endpoint expose the results, including transcript and recording URL.

#### Automated test status — run 2026-08-04

| Suite | Result |
|---|---|
| [test_twilio_webhook_validation.py](../backend/tests/unit/test_twilio_webhook_validation.py) | ✅ 6 passed |
| [test_voice_roundtrip.py](../backend/tests/unit/test_voice_roundtrip.py) | ✅ 2 passed |
| [test_call_manager.py](../backend/tests/unit/test_call_manager.py) | ⚠️ 3 passed, 15 errors at fixture setup |
| [test_call_api.py](../backend/tests/integration/test_call_api.py) | ⚠️ 18 errors at fixture setup |

The webhook-signature validation and the voice round-trip (STT → LLM → TTS) suites pass cleanly.
The DB-backed suites **do not currently execute** — every one of them errors in `conftest`
before the test body runs, so they are neither passing nor failing. This is a test-harness
problem, not a defect in the calling code: see **D-002** in §5. Until D-002 is fixed, the call
API layer has no automated verification, which raises the importance of the live-call test below.

#### Live-call verification — **the remaining gap**

Not yet performed. Everything above is either code-level or setup-level; no real audio has been
carried end to end. This is the one stage that cannot be inferred from the other modules being
green, because it is the only one that exercises the telephony provider, the media stream, the
transcription pipeline, and the recording storage together, in real time, against the live
network.

**To test — inbound:**
1. Call the provisioned number from a real phone.
2. Agent answers; hold a short conversation covering a tool call and a knowledge-base question.
3. Hang up; confirm the call row appears with correct duration and status.
4. Confirm the transcript is complete and the recording plays back.

**To test — outbound:**
1. `POST /calls` (or trigger from the UI) to your own phone.
2. Confirm ringing, agent speech, barge-in/interruption handling, and clean teardown.
3. Confirm the status webhook updates the record to `completed`.

**What to watch during the call:**
- backend logs for the `WS /voice/stream/{call_id}` connect and any mid-call disconnects,
- `GET /voice/sessions/active` while the call is up — the session should be listed,
- latency between the caller finishing a sentence and the agent replying,
- the call record's final status after hangup (should be `completed`, not stuck in-progress).

**Expected:** every call produces a stored record, a transcript, a recording, and a usage entry
that reaches analytics (§3.12) and billing (§3.13).

**Status:** ⚙️ Implemented; signature-validation and voice-round-trip tests pass; DB-backed call
tests blocked by D-002; **live-call verification pending**.

---

### 3.11 Workflows ⚙️ **IMPLEMENTED — engine fully tested, runtime verification pending**

| | |
|---|---|
| **Frontend** | [workflows](../frontend/src/app/dashboard/workflows) |
| **Endpoints** | `POST/GET /workflows`, `GET/PATCH/DELETE /workflows/{id}`, `POST /{id}/execute`, `GET /{id}/executions`, `GET /{id}/executions/{execution_id}`, `GET /{id}/stats`, `POST /{id}/validate`, `POST /{id}/test-trigger`, `WS /{id}/executions/stream`, `POST /trigger/voice-event`, `POST /trigger/integration-event`, `POST /workflows/webhook/{key}` |
| **Engine** | [app/services/workflows/](../backend/app/services/workflows/) — `graph.py`, `executor.py`, `step_handlers.py`, `trigger_handlers.py`, `scheduler.py`, `js_sandbox.py`, `data_mapper.py`, `channels.py` |
| **Tests** | ✅ [test_workflow_dag.py](../backend/tests/unit/test_workflow_dag.py), [test_workflow_graph.py](../backend/tests/unit/test_workflow_graph.py), [test_workflow_advanced.py](../backend/tests/unit/test_workflow_advanced.py), [test_workflow_phase0.py](../backend/tests/unit/test_workflow_phase0.py), [test_workflow_interpolation.py](../backend/tests/unit/test_workflow_interpolation.py), [test_voice_to_workflow.py](../backend/tests/unit/test_voice_to_workflow.py) |
| **Guides** | [WORKFLOW_SYSTEM_GUIDE.md](WORKFLOW_SYSTEM_GUIDE.md), [WORKFLOW_TRIGGERS_GUIDE.md](WORKFLOW_TRIGGERS_GUIDE.md), [VOICE_TO_WORKFLOW_GUIDE.md](VOICE_TO_WORKFLOW_GUIDE.md), [DATA_MAPPER_GUIDE.md](DATA_MAPPER_GUIDE.md) |

#### What the module does

A workflow is a **directed graph of steps** attached to a trigger. It is the automation layer that
turns a call or an external event into actions — during the call (speak, ask, transfer) or after
it (push to a CRM, send an email, call an API).

**Trigger types** ([schemas/workflow.py:14](../backend/app/schemas/workflow.py#L14)):

| Trigger | Fires when | Entry point |
|---|---|---|
| `manual` | a user clicks Run | `POST /workflows/{id}/execute` |
| `schedule` | cron / interval / one-time | [scheduler.py](../backend/app/services/workflows/scheduler.py) background loop |
| `webhook` | an external system POSTs | `POST /workflows/webhook/{webhook_key}` (public) |
| `call_started` | a call begins | `POST /workflows/trigger/voice-event` |
| `call_completed` | a call ends | `POST /workflows/trigger/voice-event` |
| `integration_event` | a connected app emits an event | `POST /workflows/trigger/integration-event` |

**Step types** ([schemas/workflow.py:24](../backend/app/schemas/workflow.py#L24)) — 16 in three families:

- **Flow control:** `condition`, `switch`, `filter`, `merge`, `loop`, `delay`, `end`
- **Data:** `transform`, `code` (sandboxed JS), `action`, `webhook`, `ai`
- **Voice (in-call):** `speak`, `ask`, `transfer`, `tool`

**Engine behaviour worth knowing when testing:**

- `graph.py` validates the graph — cycle detection, unreachable nodes, dangling edges — and this
  is what `POST /workflows/{id}/validate` calls. Invalid graphs are rejected before execution.
- `executor.py` (`GraphExecutor`) walks the DAG, deciding per node whether it is runnable or
  skippable based on inbound edges, so branches that a condition didn't select are marked
  **skipped**, not failed. Expect skipped nodes in the execution log — that is normal.
- `step_handlers.py` holds `WorkflowContext`, which carries variables and per-step results, and
  performs `{{ }}` interpolation so a later step can read an earlier step's output.
- `js_sandbox.py` runs `code` steps in isolation; `data_mapper.py` handles field mapping and
  transformations between systems.
- `channels.py` abstracts the voice side: a `SimulatedChannel` is used in tests, and the real
  channel drives the live call. **This is why unit tests passing does not prove in-call steps
  work** — see the gap note below.

#### Automated test status — run 2026-08-04

| Suite | Result | Covers |
|---|---|---|
| [test_workflow_interpolation.py](../backend/tests/unit/test_workflow_interpolation.py) | ✅ 36 passed | `{{ }}` variable interpolation, context resolution |
| [test_workflow_phase0.py](../backend/tests/unit/test_workflow_phase0.py) | ✅ 22 passed | core step execution |
| [test_workflow_advanced.py](../backend/tests/unit/test_workflow_advanced.py) | ✅ 19 passed | loops, switches, code steps, error paths |
| [test_workflow_graph.py](../backend/tests/unit/test_workflow_graph.py) | ✅ 18 passed | graph construction and validation |
| [test_workflow_dag.py](../backend/tests/unit/test_workflow_dag.py) | ✅ 16 passed | DAG traversal, skip/branch semantics |
| [test_voice_to_workflow.py](../backend/tests/unit/test_voice_to_workflow.py) | ✅ 9 passed | voice event → workflow trigger mapping |
| **Total** | **✅ 120 passed, 0 failed** | |

All six suites run clean and none depends on the database, so they are unaffected by **D-002**.
This makes workflows the **best-covered module in the codebase** — the graph engine, branching,
interpolation, and trigger mapping are genuinely verified, not just present.

#### What the tests do *not* cover

The suites exercise the engine in isolation. Still unverified:

1. **Persistence** — creating, updating, and listing workflows through the API against a real DB
   (the API-level suite is blocked by D-002).
2. **The live voice channel** — tests use `SimulatedChannel`, so `speak` / `ask` / `transfer`
   have never driven real audio on a real call.
3. **The scheduler in a running process** — cron/interval claiming is tested logically, but not
   observed firing on a live backend over time.
4. **Real integration events** — the trigger endpoint is tested; an actual connected app emitting
   an event that reaches it is not.
5. **The builder UI** — graph editing, saving, and the live execution stream in
   [workflows/](../frontend/src/app/dashboard/workflows/).

#### To test

**A — standalone (can be done now, no live call needed):**
1. Build a workflow in the builder with a branch: trigger → condition → two paths → merge → end.
2. `POST /workflows/{id}/validate` — then deliberately introduce a cycle and confirm it is rejected.
3. `POST /workflows/{id}/execute` manually; watch `WS /workflows/{id}/executions/stream` live.
4. `GET /workflows/{id}/executions/{execution_id}` — confirm per-step results, and that the
   unselected branch shows **skipped** rather than failed.
5. Use `{{ }}` interpolation to pass a value from step 1 into step 3 and confirm it resolves.
6. `POST /workflows/{id}/test-trigger`, then fire the real thing via `POST /workflows/webhook/{key}`.
7. Set a schedule trigger to a 1-minute interval and confirm it fires on its own.
8. `GET /workflows/{id}/stats` — success/failure counts should match what you ran.

**B — during the live call (§3.10):**
9. Attach a `call_started` workflow with a `speak` step; confirm the agent says it on the call.
10. Attach an `ask` step; confirm the caller's answer is captured into the workflow context.
11. Attach a `call_completed` workflow that writes to a connected integration; confirm the record
    lands in the external system after hangup.

**Status:** ⚙️ Engine implemented and fully unit-tested (120/120). Steps A can be done
immediately; steps B depend on §3.10. **Runtime verification pending.**

---

### 3.12 Analytics ⏳ **PENDING**

| | |
|---|---|
| **Frontend** | [analytics](../frontend/src/app/dashboard/analytics) |
| **Endpoints** | `GET /analytics/call-metrics`, `/agent-metrics/{id}`, `/integration-metrics/{id}`, `/daily-summary`, `/realtime`, `/dashboard`, `POST /analytics/aggregate` |
| **Guides** | [ANALYTICS_SYSTEM_GUIDE.md](ANALYTICS_SYSTEM_GUIDE.md), [ANALYTICS_SCHEDULER_GUIDE.md](ANALYTICS_SCHEDULER_GUIDE.md) |

#### Why analytics cannot be verified before the live call

**Analytics only populates once a live call has completed.** The dashboard is a reporting layer
over call data — it has no data of its own. The chain is:

```
live call ends
  -> POST /telephony/twilio/status marks the call record `completed`
     (duration, outcome, and cost are written at this point)
  -> the completed call row becomes the source record for metrics
  -> GET /analytics/realtime reflects it immediately
  -> POST /analytics/aggregate (or the scheduler) rolls it into daily buckets
  -> GET /analytics/call-metrics, /agent-metrics/{id}, /daily-summary, /dashboard read those buckets
```

Because of this, an empty analytics dashboard on a fresh workspace is **correct behaviour, not a
bug** — and equally, analytics cannot be marked verified while §3.10 is outstanding. Any testing
done before a real call would only confirm that the endpoints return empty result sets. This is
why §3.10 is sequenced first: one completed live call is what makes this section testable.

Note the two different timing paths — **realtime** metrics update as soon as the call record
closes, whereas the **daily summary and dashboard aggregates** only move after an aggregation run.
If the numbers look stale immediately after a call, check whether the aggregation has run before
filing it as a defect; `POST /analytics/aggregate` triggers it manually. See
[ANALYTICS_SCHEDULER_GUIDE.md](ANALYTICS_SCHEDULER_GUIDE.md) for the scheduled cadence.

#### To test — immediately after the live call in §3.10

1. `GET /analytics/realtime` — the just-finished call should be reflected right away.
2. Open the analytics dashboard — confirm total calls incremented by exactly one.
3. `GET /analytics/agent-metrics/{agent_id}` — call count and total/average duration must match
   the actual call you just made (compare against the duration shown on the call record).
4. `POST /analytics/aggregate`, then `GET /analytics/daily-summary` — today's bucket should
   include the call.
5. `GET /analytics/call-metrics` — verify the breakdown (inbound vs outbound, completed vs failed)
   attributes the call to the correct direction and outcome.
6. If an integration fired during the call, check `GET /analytics/integration-metrics/{id}`.

**Common failure to look for:** a call that shows correctly under §3.10 but never reaches
analytics indicates the metering step at call completion is not writing — that would be a
high-severity defect, since billing (§3.13) meters from the same data.

**Status:** ⏳ Pending — blocked on §3.10. Verify in the same session, immediately after the call,
while you still know the exact expected numbers.

---

### 3.13 Billing ⏳ **PENDING**

| | |
|---|---|
| **Endpoints** | `GET /billing/plans`, `GET /billing/config`, `GET/POST/PUT/DELETE /billing/subscription`, `GET /billing/usage`, `/usage/limits`, `/invoices`, `POST /billing/webhooks/stripe` |
| **Tests** | 🔁 [test_billing_api.py](../backend/tests/integration/test_billing_api.py), [test_billing_service.py](../backend/tests/unit/test_billing_service.py) |
| **Guide** | [STRIPE_BILLING_GUIDE.md](STRIPE_BILLING_GUIDE.md) |

**To test:** list plans → subscribe in Stripe test mode → confirm the webhook activates the
subscription → confirm call usage decrements the quota → confirm limits block usage at zero →
cancel and confirm downgrade.

**Status:** ⏳ Pending.

---

### 3.14 Marketplace / templates ⏳ **PENDING**

| | |
|---|---|
| **Frontend** | [marketplace](../frontend/src/app/dashboard/marketplace) |
| **Endpoints** | `GET /marketplace/templates/agents`, `/templates/agents/{slug}`, `/templates/workflows`, `/templates/agents/{slug}/reviews`, `/categories`, `GET /marketplace/my-installations`, plus install/review POSTs |
| **Guide** | [TEMPLATE_MARKETPLACE_GUIDE.md](TEMPLATE_MARKETPLACE_GUIDE.md) |

**To test:** browse templates → install an agent template → confirm it appears as a working agent
→ install a workflow template → leave a review → check `my-installations`.

**Status:** ⏳ Pending.

---

## 4. Test matrix

| # | Module | Manual | Automated | Status |
|---|---|---|---|---|
| 1 | Auth + email verification | ✅ 2026-08-03 | ✅ | Pass |
| 2 | Onboarding + default Twilio | ✅ 2026-08-03 | — | Pass |
| 3 | Team / workspaces / invitations | ✅ 2026-08-03 | ✅ | Pass (1 defect fixed) |
| 4 | Phone numbers | ✅ 2026-08-03 | ✅ | Pass |
| 5 | Agents | ✅ 2026-08-03 | ✅ | Pass |
| 6 | Tools | ✅ 2026-08-03 | ✅ | Pass |
| 7 | Knowledge base | ✅ 2026-08-03 | — | Pass |
| 8 | Integrations | ✅ 2026-08-03 | ✅ | Pass |
| 9 | Notifications | ✅ 2026-08-03 | — | Pass |
| 10 | Chat widget | ✅ 2026-08-03 | ✅ | Pass |
| 11 | API keys | ✅ 2026-08-03 | — | Pass |
| 12 | User settings | ✅ 2026-08-03 | ✅ | Pass |
| 13 | **Calls (inbound + outbound)** | ⏳ live call | ⚠️ partial (D-002) | **Implemented, unverified live** |
| 14 | **Workflows** | ⏳ runtime | ✅ 120/120 passed 2026-08-04 | **Implemented, engine verified** |
| 15 | **Analytics** | ⏳ | — | **Pending — blocked on #13** |
| 16 | **Billing** | ⏳ | ✅ | **Pending** |

**12 of 16 modules verified.** The five remaining are the runtime half of the product: a call
happening, a workflow firing from it, and the metering/reporting that follows. Calls (#13) and
workflows (#14) are both fully implemented — workflows with 120 passing engine tests — but no
live call has been placed, and #14's in-call steps plus #15's entire dataset depend on it. A
single live call unblocks three rows.

**Legend for automated column:** ✅ suite exists and is expected to run · ⚠️ suite exists but is
currently blocked · — no suite. Suites actually executed in this session (2026-08-04) are the
call suites (§3.10) and the workflow suites (§3.11); other ✅ marks indicate coverage exists,
not a fresh run.

---

## 5. Defect log

| ID | Module | Severity | Description | Status |
|---|---|---|---|---|
| D-001 | Invitations / email | High | Invitation emails linked to `http://localhost:3002/invite/{token}` while the frontend runs on port 3000, so **Accept invitation** landed on `ERR_CONNECTION_REFUSED`. Cause: stale `FRONTEND_URL` in `backend/.env`, used by [invitation_service.py:31](../backend/app/services/team/invitation_service.py#L31). The same value also backs the Google OAuth redirect. | ✅ Fixed 2026-08-03 (`FRONTEND_URL=http://localhost:3000`; backend restart required) |

| D-002 | Test harness | Medium | All DB-backed tests error at fixture setup, so the call API suite never executes (33 errors, 0 assertions run). Two causes: (a) `TEST_DATABASE_URL` in [conftest.py:26](../backend/tests/conftest.py#L26) defaults to `postgres:postgres@localhost:5432/voicecon_test`, but the dev Postgres runs on **5435** as `voicecon_user`; (b) once pointed at a reachable DB, the org fixture fails with `null value in column "owner_id" of relation "organizations" violates not-null constraint` — the fixture predates `owner_id` becoming NOT NULL. | 🔧 Open |

> D-001 is a good illustration of why this task exists: the invitation module passed every in-app
> check, and the failure only appeared once the flow crossed into email and back.
>
> D-002 matters for this task specifically: it means the "tests exist" column overstates real
> coverage for every DB-backed suite. Workaround for (a) is to export
> `TEST_DATABASE_URL=postgresql+asyncpg://voicecon_user:voicecon_password_dev@localhost:5435/voicecon_test`;
> (b) needs the org fixture updated to set `owner_id`. Neither is a product defect, but until
> both are fixed the call, agent, billing, and settings suites cannot be cited as evidence.

---

## 6. Q/A — review, triage and acceptance

Testing (§3) finds problems; Q/A is what happens to them afterwards. A module is not "done"
because it was tested — it is done when everything found has been triaged, fixed or consciously
accepted, retested, and signed off. This section defines that gate.

### 6.1 Severity scale

Every defect in §5 carries one of these. The severity decides whether it blocks the release, not
how annoying it feels.

| Severity | Definition | Action |
|---|---|---|
| **Critical** | Core flow is broken with no workaround — a call cannot be placed or answered, signup is impossible, data loss | Stop and fix now; blocks sign-off |
| **High** | A module's main path fails, or works in-app but breaks across a boundary (email, webhook, external system) | Fix before sign-off — D-001 was this class |
| **Medium** | Secondary path broken, or a problem with a viable workaround; test-harness defects | Fix or schedule with an owner and date — D-002 is this class |
| **Low** | Cosmetic, copy, or edge-case issue that does not affect the flow | Log and batch; must not silently disappear |

### 6.2 Defect lifecycle

```
found during testing
  -> logged in §5 with module, severity, reproduction, and cause
  -> triaged: fix now / schedule with owner / accept with written reason
  -> fixed
  -> RETESTED through the original failing path (not just the code diff)
  -> marked ✅ Fixed with the date
```

The retest step is the one that gets skipped. D-001 illustrates why it matters: the code fix was
one line in `.env`, but the fix is only proven by receiving a fresh invitation email and clicking
the button — the original failing path, end to end. A green test or a corrected value is not
evidence that the user-facing flow now works.

### 6.3 Regression checks after a fix

When a defect is fixed, re-verify the neighbours that share its cause — most defects sit on a
shared dependency, and fixing one place rarely fixes all of them:

| Fix | Also re-check |
|---|---|
| `FRONTEND_URL` (D-001) | Invitation email link, email verification link, password-reset link, Google OAuth redirect — all four are built from the same setting |
| Test fixtures (D-002) | The full DB-backed suite: call, agent, billing, settings, invitations, workspaces |
| Anything in the call path | Transcript, recording, analytics row, and billing usage — they all read from the same completed-call record |

### 6.4 Acceptance criteria — definition of done

- [ ] All 17 modules in §4 are marked verified, or carry a written reason for being deferred
- [ ] A live inbound **and** outbound call have been completed, with transcript and recording confirmed (§3.10)
- [ ] Analytics reflects those calls correctly (§3.12)
- [ ] Every Critical and High defect in §5 is fixed **and retested**
- [ ] Every Medium and Low defect has an owner and a date, or an accepted-as-is note
- [ ] Backend and frontend suites have been run, with results attached and D-002 resolved
- [ ] Screenshots attached per stage
- [ ] This document reviewed by a second person and the §8 sign-off completed

### 6.5 Current Q/A position

| | |
|---|---|
| Defects found | 2 (1 High, 1 Medium) |
| Fixed and retested | 1 — D-001 (retest = accept a fresh invitation email end to end) |
| Open | 1 — D-002, Medium, needs an owner |
| Blocking sign-off | The live-call verification (§3.10), not the defects |

The honest summary: the **setup half of the product is verified and the automation engine is
well-tested, but no real call has been carried end to end**. That single gap is what stands
between this task and sign-off — everything else is either done or sequenced behind it.


## 7. Remaining work

1. **Calls (§3.10)** — one inbound and one outbound live call, end to end, with transcript and
   recording. Implementation is complete; this is verification only. **Do this first** — steps 2
   and 3 both depend on it.
2. **Workflows (§3.11)** — engine is verified (120/120 tests). Do part A (build, validate,
   execute, webhook + schedule triggers) **now, in parallel** — it needs no live call. Part B
   (in-call `speak` / `ask` / `transfer` and the `call_completed` trigger) runs during step 1.
3. **Analytics (§3.12)** — confirm the call from step 1 surfaces correctly in the metrics.
   Cannot start before step 1: analytics only populates after a live call completes.
4. **Billing (§3.13)** — Stripe test-mode subscription, usage metering, limit enforcement.
---
