# QA Automation

End-to-end test suite for Voicecon, built on Playwright.

## What this app actually is

Worth stating up front, because it drives the whole test strategy:

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), React Query, Zustand, axios |
| Backend | **Python / FastAPI** — not Node/Express |
| Database | **PostgreSQL** via SQLAlchemy + Alembic — not MongoDB |
| Auth | JWT access + refresh tokens in `localStorage`, email-OTP signup |
| Tenancy | Workspace-scoped; `permissions[]` from `/workspaces/current` gates the UI |
| Billing | Plan entitlements gate writes; blocked actions return **402**, not 403 |

## Layout

```
tests/
├── auth.setup.ts          # one-time login → playwright/.auth/user.json
├── support/               # shared helpers, no tests
│   ├── api.ts             #   real-backend: account creation, login, trials
│   ├── data.ts            #   response fixtures mirroring real API schemas
│   ├── mocks.ts           #   ApiMock fixture + app-shell stubbing
│   ├── routes.ts          #   RegExp matchers for every endpoint used
│   └── session.ts         #   browser session seeding, enterDashboard()
├── ui/                    # mocked backend — fast, hermetic, 3 browsers
│   ├── landing.spec.ts    ├── dashboard.spec.ts   ├── errors.spec.ts
│   ├── login.spec.ts      ├── agents.spec.ts      ├── guard.spec.ts
│   ├── register.spec.ts   ├── logout.spec.ts      └── smoke.spec.ts
├── api/                   # real backend, no browser — contract tests
│   ├── health.spec.ts     └── auth.spec.ts        └── agents.spec.ts
└── e2e/                   # real backend + real browser — critical paths
    ├── auth.spec.ts       └── agents.spec.ts
```

### Three layers, three jobs

**`tests/ui` — mocked.** Every `/api/v1/**` call is intercepted. Runs on
Chromium, Firefox and WebKit with no database and no Python. This is the layer
that covers rendering, form logic, permission gating and error handling, and
it is the one that runs on every push.

**`tests/api` — contract.** Drives FastAPI directly, no browser. Its job is to
catch the API drifting away from what the mocks above assume. **When this layer
goes red, the mocked layer's green is worthless.**

**`tests/e2e` — full stack.** Real browser against a real backend and Postgres.
Deliberately small: these are slow and write real rows, so they cover only the
paths where an integration bug would be invisible to the other two layers.

## Running

```bash
npm test                  # mocked UI, all three browsers (no infra needed)
npm run test:ui           # mocked UI, Chromium only — the fast inner loop
npm run test:api          # backend contract tests      (needs backend + DB)
npm run test:e2e          # full-stack browser tests    (needs backend + DB)
npm run test:full         # everything
npm run test:report       # open the last HTML report
npm run typecheck         # type-check the suite itself
```

`api` and `e2e` are gated behind `E2E=1`, so a plain `npm test` on a fresh
clone can never fail for want of a database.

> **Node 20+ is required.** Playwright 1.62 refuses to start on Node 18.

### Local infrastructure

```bash
# Postgres (already provisioned as voicecon_postgres on :5435)
docker start voicecon_postgres

# Backend — note the EMAIL_PROVIDER override, explained below
cd backend
EMAIL_PROVIDER=console ./venv/bin/python -m uvicorn app.main:app --port 8001

# Frontend
npm run dev --prefix frontend        # :3000
```

Then `E2E=1 API_URL=http://localhost:8001 npm run test:full`.

Ports are overridable: `PORT` (frontend), `API_URL` (backend),
`PLAYWRIGHT_BASE_URL` (full base URL).

### ⚠️ `EMAIL_PROVIDER=console` is not optional

Tests create their own accounts, which needs the email verification code.
The backend only returns it as `debug_code` when `DEBUG=true` **and** no real
mail transport is configured (`backend/app/api/v1/endpoints/auth.py:87`).

`backend/.env` ships **live Gmail SMTP credentials**. Starting the test backend
without the override means:

1. every account-creating test fails, because `debug_code` is `null`; and
2. the suite sends real email from that account on every run.

`EMAIL_PROVIDER=console` fixes both. CI sets it explicitly.

### Test accounts use `@example.com`

`example.com` is IANA-reserved and can never receive mail, yet still passes the
backend's `email-validator`. `.test`, `.invalid` and `.localhost` look safer but
are special-use names the validator **rejects with a 422**.

## Failure artifacts

On failure Playwright captures, into `test-results/<test-name>/`:

- `test-failed-1.png` — screenshot at the moment of failure
- `video.webm` — full video of the test
- `trace.zip` — DOM snapshots, network log, console, per-step timeline
- `error-context.md` — accessibility snapshot of the page

```bash
npx playwright show-trace test-results/<test-name>/trace.zip
```

The trace is almost always the fastest route to a diagnosis: it shows every
request the app made and what each mock returned.

## Writing tests

### Use `ROUTES`, never a raw glob

```ts
await api.on(ROUTES.agents, { body: agentListResponse([agent()]) })
```

Playwright's glob syntax treats `?` as a single-character wildcard, so
`**/api/v1/agents` never matches the app's real `/api/v1/agents?limit=500`.
The call then falls through to the catch-all `{}` and **the test passes while
asserting nothing**. `tests/support/routes.ts` uses anchored RegExp instead.

Note that agent sub-resources are not nested under `/agents` — knowledge bases
live at `/api/v1/knowledge/agents/{id}/knowledge-bases` and tools at
`/api/v1/tools/agents/{id}/tools`.

### Entering the dashboard

```ts
await enterDashboard(page, api, '/dashboard/agents')
```

This stubs `/users/me`, `/workspaces/current` and `/billing/entitlements`
*before* navigating, then seeds the session. Skipping it means
`workspace.permissions.includes(...)` throws on the catch-all's `{}` and the
page renders blank — so the test is really exercising the error path.

Override the shell to test other roles:

```ts
await enterDashboard(page, api, '/dashboard/agents', {
  workspace: { permissions: VIEWER_PERMISSIONS, role: 'viewer' },
})
```

### Scope by verb, not by sequence

React's dev StrictMode double-fires effects, so a response *sequence* silently
loses its first entry. When one URL must answer differently per verb:

```ts
await api.on(ROUTES.agent, { body: agentDetail() })
await api.on(ROUTES.agent, { status: 500, body: apiError('nope') }, { method: 'PATCH' })
```

### Match the real error envelope

A 402 only opens the upgrade dialog when the body carries
`code: 'entitlement_required'` (`frontend/src/lib/api.ts:66`). Use the
`entitlementError()` fixture — a bare `{detail}` 402 tests nothing.

### Status codes mean different things here

| Code | Meaning | Expected UI |
|---|---|---|
| 401 | token expired | refresh, retry once, then `/login` |
| 402 | plan doesn't cover it | upgrade dialog |
| 403 | signed in, not allowed | error message, stay put |
| 5xx | server broke | error message, shell survives |

Conflating 402/403 with 401 — logging the user out — is a common regression the
`errors.spec.ts` suite exists to catch.

### Cross-browser notes

The mocked suite runs on Chromium, Firefox and WebKit, and the differences are
real rather than cosmetic:

- **WebKit is the slowest engine here**, which is what surfaced the login
  screen firing several navigations while hydrating. `signIn()` now waits for
  an interactive control before seeding the session, and `gotoStable()` retries
  a navigation once — but *only* when it was interrupted by the app's own
  routing, never on a genuine failure.
- **Firefox surfaced the tokenless-refresh bug** (below) because its request
  ordering produced two concurrent refresh attempts. The bug was never
  Firefox-specific; the engine just made the race reliable.

Treat a failure on one engine as a real defect until proven otherwise.

## Systematic QA: how the sweep is being run

The application is worked through one feature area at a time. For each area:

1. **Read** the backend endpoint and the frontend page together, looking for
   validation that exists on one side but not the other.
2. **Reproduce** each suspected defect against the running stack with `curl` or
   a throwaway spec, so a finding is a fact before it is a fix.
3. **Fix** it, then **re-reproduce** to prove the fix.
4. **Write the regression test** in the layer that would have caught it —
   contract bugs in `tests/api`, rendering and gating in `tests/ui`,
   integration in `tests/e2e`.
5. **Re-run the whole suite** before moving on, because a fix in shared code
   (auth, workspace scoping, entitlements) reaches everything.

Progress:

| Area | State |
|---|---|
| Authentication | **Done** — 4 defects found and fixed, 17 regression tests added |
| Onboarding (company → pricing → billing) | **API done** — 2 defects fixed, 11 tests added. UI layer not yet covered |
| Agents CRUD / clone / functions / test | **Done** — clone was broken outright; 10 tests added |
| Agent Flow Builder | **Blocked** — the feature does not persist at all, see below |
| *Cross-cutting* | Two whole-API defects fixed: validator errors returning 500, and blank names accepted everywhere |
| Calls, phone numbers, telephony | **Done** (read/scoping paths; no live provider) |
| Workflows + executions | **Done** — scoping proven, 5 tests |
| Knowledge base, tools, integrations | **Done** — 1 defect fixed, scoping proven |
| Settings: team, invitations, workspace, profile | **Done** — 3 defects fixed, 13 tests |
| Billing + analytics + marketplace | **Done** — 2 defects fixed, 6 tests |

### What the authentication pass found

All four reproduced against a running backend before being fixed.

1. **Mixed-case addresses could not sign in.** Registration stored the address
   normalized; login compared the raw input. Signing up as `Sam@Example.com`
   and then typing that same address returned 401 — and every phone keyboard
   autocapitalises the first letter. (`endpoints/auth.py`)
2. **Sign-up 500'd on a duplicate email local part.** The personal workspace's
   slug came from the part before the `@`, and `Organization.slug` is UNIQUE,
   so once `info@one.com` existed, `info@two.com` could not create an account
   at all. The social sign-up path had always handled this; the email path did
   not. Both now share `services/auth/workspaces.py`.
3. **No rate limiting anywhere.** `middleware/rate_limit.py` was fully written
   but never installed — nothing called it. 50 consecutive failed logins were
   answered 401 fifty times as fast as they could be sent. Wiring it up
   required fixing four bugs inside it; see that module's docstring.
4. **A refresh token with a non-UUID subject raised, rather than being
   rejected** — a 500 where a 401 belonged.

### What the onboarding pass found

5. **A company name of only whitespace was accepted.** `min_length=1` counts
   characters, so a single space passed. The form trimmed before checking, so
   only a direct API call or a pasted value reached it — but the endpoint
   copies that name onto the Organization, so a spacebar renamed the workspace
   to nothing and blanked the switcher and every page header. Optional fields
   now also store NULL rather than `""` when left untouched.
6. **Every custom field validator returned 500 instead of 422.** Pydantic v2
   puts the raised exception *object* under `ctx["error"]`, and `JSONResponse`
   could not serialize it — so `validation_exception_handler` blew up while
   reporting the error, and the client was told "an unexpected error occurred"
   when it had simply sent a bad value. This was **pre-existing and not
   specific to onboarding**: posting an agent with an unknown `type` returned
   500 too, as did the equivalent validators on workflows and integrations.
   Fixed in `main.py` by encoding the detail with a str fallback for
   exceptions, which keeps the message — the useful half — while guaranteeing
   the body encodes.

7. **Every user-visible name accepted pure whitespace.** The same
   `Field(..., min_length=1)` declaration — which counts characters, so one
   space passes — was used for agents, workflows, tools, workspaces and
   integrations, not just company names. What it produced was a row in the
   list with no label and nothing to distinguish it from the next one. Fixed
   once, in `app/schemas/_types.py`: `NonBlankName` trims before applying
   `min_length`, so blank input is rejected *and* padded input is stored tidy.

### What the agents pass found

8. **Cloning an agent failed with a 500 — every time the UI asked for it.**
   `include_functions` defaults to true, and that branch iterated
   `source.functions`, a lazy relationship, *after* the session had been
   committed. SQLAlchemy's async engine cannot issue IO from attribute access,
   so it raised `greenlet_spawn has not been called`. Passing
   `include_functions: false` explicitly was the only way to get a clone, which
   is not a request the product ever sends. The source is now eager-loaded and
   the whole clone happens in one transaction — previously the agent was
   committed *before* its functions were copied, so a failure left a
   half-cloned agent behind.
9. **The clone endpoint had no name constraint at all** — not even the
   `min_length=1` the other schemas carried — so it was a way round the
   non-blank rule.

Workspace isolation was probed across every agent sub-resource — read, update,
delete, clone, list/attach functions, and the test endpoint — from a second
account. All returned 404. Attaching a function to someone else's agent is the
sharpest of these, since a `webhook_url` on another tenant's agent would send
their callers' conversations to an address the attacker controls; it is
covered by a test now.

### What phases 4-8 found

10. **The billing page was unusable on any deployment without Stripe.**
    `GET /billing/usage` injected the Stripe service as a FastAPI dependency,
    and that dependency raises 503 when no API key is configured — so the
    request was rejected before the handler ran. The handler only reads local
    subscription rows and does arithmetic; it never calls Stripe. Settings →
    Billing fetches it, so the page failed outright for trial users on exactly
    the deployment the free trial is meant to serve. `/usage/limits` had the
    same problem. Both now use `get_usage_reader`, which carries no credentials
    and deliberately does not configure the SDK — `stripe.api_key` is
    process-global, so a blank instance could otherwise clobber a live key
    under a concurrent paid request.
11. **A trial did not count as a subscription.** `check_usage_limits` filtered
    on `status == "active"`, while every other query in the codebase uses
    `LIVE_STATUSES` (which includes `trialing`). Every trial user was reported
    as having no subscription and as being outside their limits.
12. **Three more blank-name holes**, all the same shape as the earlier ones and
    all found by posting a single space: knowledge bases, the profile name
    (`PATCH /users/me`), and the workspace rename (`PATCH /workspaces/current`,
    which also backs workspace *creation*). The workspace one was the worst —
    the handler `.strip()`ped before saving, so `" "` was stored as `""` and
    the switcher rendered an unnamed workspace.

Everything else swept clean. A breadth-first probe of ~45 endpoints across
calls, phone numbers, workflows, knowledge, tools, integrations, team, billing,
analytics and marketplace returned exactly one 5xx (the billing one above).

**Tenancy was the main event.** Every resource one workspace can create was
probed from a second workspace — read, update, delete, execute, and the
list endpoints — across agents, agent functions, workflows, workflow
executions, knowledge bases, tools, calls, phone numbers and invitations.
**Zero leaks.** The sharp cases now carry tests: executing another tenant's
workflow (spends their quota, fires their integrations), running their tool
(borrows their credentials), attaching a webhook to their agent (exfiltrates
their callers' conversations), and reading their pending invitations (real
people's addresses).

### Not covered, and why

Buying a phone number, placing a call and the Twilio/Telnyx callbacks need live
provider credentials. Those are exercised only as far as scoping and validation
go — the suite must never spend money or dial a real number. `POST /api-keys`
is gated at 402 on the trial plan, so key management is covered by scope listing
and tenancy rather than by minting a key.

### Sign-up validation

Registration accepted almost anything. Confirmed against the running API before
the fix: an account could be created with **no name at all**, with a name of
`""`, `" "`, `"a"` or `"123"`, with the password `password`, `12345678` or the
user's own email address, with a 400-character password, and with
`not-a-phone!!` as a phone number. A 500-character name overflowed the
255-char column and surfaced as a **500**.

`full_name` is now required — it was `Optional` on the API *and* unmarked on
the form, so a nameless account was reachable straight from the product, then
rendered as a blank row in the team list and in every invitation it sent.

The password policy (`app/core/passwords.py`) follows NIST SP 800-63B rather
than the older "one upper, one digit, one symbol" recipe: a length floor, a
blocklist of the passwords that top every credential dump, a check that the
password is not simply the user's own name or address, and a ceiling at **72
bytes** — which is all bcrypt reads, so anything longer was being silently
truncated and two different long passwords could authenticate each other.
Composition rules are deliberately off; `_COMPOSITION_RULES` is the hook if a
compliance regime ever demands them.

The same policy guards `/auth/password/reset` and the change-password
endpoint, so neither is a way round the sign-up rules.

Two supporting fixes were needed for any of this to reach the user:

- `getErrorMessage` (`frontend/src/lib/api.ts`) never looked at `details[]`, so
  every field rejection surfaced as the generic "Request validation failed" —
  a user told to pick a different password saw nothing about passwords. It now
  reads `details[0].msg` and strips Pydantic's `"Value error, "` prefix.
- The phone check is a function rather than a `pattern`, because Pydantic
  reports a failed pattern by printing the regex, and
  `String should match pattern '^\+?[0-9]...'` is not something to show someone
  filling in a form.

`company_url` accepts any string, including `javascript:…`. It is never
rendered as a link today, so it is not exploitable — but it is stored, and it
would become an XSS the day someone renders it as an `href`. Noted rather than
fixed, because tightening it is a product decision about what counts as a valid
company URL.

### Rate limiting, and why the numbers are what they are

Two different mechanisms, deliberately:

- **Per-account lockout** (`services/auth/login_throttle.py`) — 5 failed
  attempts for one address, then 429 for 15 minutes. This is the control that
  stops password guessing, because an attacker must keep naming the address
  they are targeting no matter how many IPs they come from. A successful
  sign-in clears the count, so ordinary typos never lock anyone out. Failures
  are counted for unregistered addresses too, so the lockout cannot be used to
  discover which addresses have accounts.
- **Per-IP/user ceiling** (`middleware/rate_limit.py`) — coarse, and set
  coarse on purpose. One IP is an office, a campus, a carrier NAT or a CI
  runner, so a tight per-IP rule mostly punishes bystanders. Tuning it down
  is how the first attempt broke the suite: at 120/min the e2e project's own
  logins were being throttled from `127.0.0.1`, which is exactly what a
  200-person company signing in at 9am would have hit.

Everything is settings-driven (`RATE_LIMIT_*` in `core/config.py`), and
`RATE_LIMIT_ENABLED=false` turns the middleware off entirely.

Provider webhooks are exempt — Twilio's voice and status callbacks, Stripe's
webhook, and inbound workflow webhooks. They are unauthenticated, so the
limiter could only key them by the provider's egress IP, shared by every
customer; a 60/min write ceiling there is not a safety net but a cap on
concurrent calls, and exceeding it drops live ones. Each of those endpoints
authenticates itself (signature validation, or an unguessable key in the URL).

> **Deployment requirement, not a code setting.** Uvicorn rewrites
> `request.client` from `X-Forwarded-For` before the application runs, trusting
> the header from any peer in `--forwarded-allow-ips` (default `127.0.0.1`).
> That is correct behind a reverse proxy on the same host. If this app is ever
> exposed **directly**, that default lets any client name its own address, get
> a fresh rate-limit bucket per request, and walk past every IP-keyed limit —
> so a direct deployment must pass `--forwarded-allow-ips=""`. No application
> setting can compensate, because the rewrite happens upstream of the app; this
> was confirmed by observing `request.client.host` equal to a spoofed
> `X-Forwarded-For` value.

## Known gaps

- **The Agent Flow Builder persists nothing.** `/dashboard/agents/{id}/builder`
  renders `<FlowBuilder agentId={agentId} />` with **no `onSave` prop**, so its
  auto-save calls no handler; the only other write is
  `localStorage.setItem('flow_<id>')`, and **nothing in the codebase ever reads
  that key back**. There is an `agent_flows` table and an `AgentFlow` model, but
  no API endpoint references either, and the table holds 0 rows. The builder
  also sets a "last saved" timestamp on every auto-save, so it actively tells
  the user their work is safe. Anything built there is lost on reload, and it
  never reaches the agent at runtime. This is a missing feature — persistence
  endpoint, schema, service and a load path — rather than a defect to patch, so
  it is reported rather than fixed.
- **Agent search is unreachable.** `dashboard/agents/page.tsx` has a full
  `search` filter with an empty state and a result counter, but no search input
  is ever rendered, and the header's "Search… ⌘K" button has no handler. There
  is no test because there is nothing a user can drive.
- **Concurrent refreshes are not de-duplicated.** Several simultaneous 401s
  each fire their own `POST /auth/refresh` (`frontend/src/lib/api.ts:40` guards
  per-request, not globally). The tokenless-response hole this opened is now
  closed, but a single-flight refresh would still be the better design.
- **Not yet covered:** onboarding (company → pricing → billing), calls, phone
  numbers, workflows/builder, integrations OAuth, knowledge base, team
  invitations, API keys. See the progress table above.
- **The login lockout counts in-process.** Behind several replicas an attacker
  gets the five attempts once per replica. Moving the counter to Redis or a
  column on `users` would make it exact; the current form still raises the
  cost of guessing by orders of magnitude over having nothing.
- The suite runs against `next dev`, which compiles routes on demand; timeouts
  are set generously to absorb that. Running against a production build would
  let them come back down.
- **The suite is sensitive to machine load, and fails in a misleading way.**
  A full `E2E=1` run with default workers puts three browser engines and a
  Next dev server on the box at once; on a machine already at load average
  ~20 that produced ten failures — six on Firefox, one on WebKit, three in
  `e2e` — every one of them a timeout on a test that passes on its own. Re-run
  at `--workers=2` before believing a failure of this shape: the tell is a
  duration far above the test's usual one (35s–1.1m for work that normally
  takes 10s) and a clean pass in isolation.
- **Only ever run one Next dev server.** If Playwright's `webServer` starts a
  second one because your own is on a different port, both write to
  `frontend/.next` and corrupt it. The symptom is
  `Cannot find module './vendor-chunks/*.js'` and a spray of unrelated UI
  failures; the fix is to kill every `next dev`, `rm -rf frontend/.next`, and
  start exactly one.
