# Voicecon — Dokploy Deployment Guide

Step-by-step deployment of the full stack (**Postgres + FastAPI backend + Next.js
frontend**) onto Dokploy **v0.29.x**, from the `khakanhyder/voicecon` GitHub repo.

Every field name below matches the Dokploy v0.29 UI. Where a label differs slightly in
your build, the *function* is described so you can find the equivalent.

---

## 0. Architecture — what gets deployed

| Service | Type in Dokploy | Source | Internal port |
|---|---|---|---|
| `voicecon-db` | Database → PostgreSQL | `postgres:16-alpine` | 5432 |
| `voicecon-backend` | Application | `backend/Dockerfile` | 8000 |
| `voicecon-frontend` | Application | `frontend/Dockerfile` | 3000 |

Three services, one project. That's the whole stack.

### What you deliberately do NOT deploy

- **Celery worker / beat.** `backend/app/workers/` exists, but nothing in the codebase
  ever calls `.delay()` or `.apply_async()`. All background work runs as in-process
  asyncio schedulers started in `app/main.py`'s lifespan handler. Deploying Celery
  workers would consume resources and process nothing.
- **Redis.** Optional. Only `/api/v1/health/detailed` touches it — the rate-limit
  middleware that would use it is never registered in `main.py`. Add it later if you
  wire up rate limiting.
- `backend/nixpacks.toml` and `backend/railway.toml` are **Railway leftovers — ignore
  them.** The Nixpacks start command bypasses `start.sh` and therefore skips the
  connector/plan seeding, which silently breaks the Integrations page.

### Hard constraint: one replica

`app/main.py` starts three in-process schedulers (analytics, workflow, billing) and
reaps stranded workflow executions at startup. Workflow runs execute **inside the API
process**. Two replicas means scheduled workflows firing twice, billing expiry running
twice, and each replica reaping the other's in-flight executions. Keep replicas at **1**
until that work moves to a leader-elected or queue-backed worker. Scale vertically (more
CPU/RAM) if you need throughput.

---

## 1. Pre-flight (do this before opening Dokploy)

### 1.1 Fix the `RECORDINGS_PATH` crash

`app/services/call/recording_service.py:38` reads `settings.RECORDINGS_PATH`, but that
field is **not declared** in `app/core/config.py`. Pydantic's `extra="allow"` only
creates the attribute when the env var is actually present. Verified behaviour:

```
AttributeError: 'Settings' object has no attribute 'RECORDINGS_PATH'
```

Every call that attempts recording will return 500 until this is handled.

- **Env-var fix (required):** set `RECORDINGS_PATH=/app/recordings` on the backend.
- **Code fix (also do this):** add to `app/core/config.py` beside the other fields:
  ```python
  RECORDINGS_PATH: Optional[str] = None
  ```

### 1.2 Generate your two secrets — once, permanently

```bash
openssl rand -hex 32   # → SECRET_KEY
openssl rand -hex 16   # → ENCRYPTION_SALT   (must be valid hex)
```

> ### ⚠️ Save these in a password manager before pasting them anywhere
> The credential-encryption key is derived from `SECRET_KEY` **+** `ENCRYPTION_SALT`
> (`app/core/security_fixed.py:192`). If you ever change **either one** after users have
> connected integrations, **every stored OAuth token and API credential becomes
> permanently undecryptable.** There is no recovery — users must reconnect everything.
> Rotating `SECRET_KEY` alone also invalidates every live login session.

### 1.3 Decide your domains

You need two hostnames. Two options:

**Option A — your own domain (use this for production).** Create two `A` records
pointing at your Dokploy server, **before deploying** — Let's Encrypt validates over
HTTP and fails on unresolved records. DNS propagation can take up to an hour.

```
A    app.yourdomain.com   →   15.204.116.11
A    api.yourdomain.com   →   15.204.116.11
```

**Option B — Dokploy's generated domain (testing only).** The Domains tab has a
**Generate Domain** button producing a `*.traefik.me` host that resolves to your server
with no DNS setup. Fine for a first smoke test. Not for production: you don't control
it, and Google/Apple/Stripe callbacks are painful to re-register later.

**Use two subdomains, never a path prefix.** `app/main.py` sets
`redirect_slashes=False`, and the frontend derives its WebSocket base by string-swapping
`http`→`ws` on the API URL (`src/hooks/useWorkflowRun.ts:40`). A path-rewriting proxy
(`yourdomain.com/api` → backend) breaks both.

Throughout this guide, substitute your real hostnames for `app.yourdomain.com` and
`api.yourdomain.com`.

### 1.4 Add `.dockerignore` files (recommended)

Neither directory has one. Git-based deploys are mostly safe (`venv/`, `node_modules/`,
`.next/`, `.env`, `*.log` are gitignored so Dokploy's clone won't contain them), but the
backend's `COPY . .` still pulls in `tests/`, `docs/`, and `__pycache__`.

```bash
# backend/.dockerignore
venv/
__pycache__/
*.pyc
.pytest_cache/
tests/
docs/
recordings/
*.log
.env
.env.*
!.env.example

# frontend/.dockerignore
node_modules/
.next/
e2e/
.env.local
.env.*.local
*.tsbuildinfo
```

### 1.5 Connect GitHub to Dokploy

Left sidebar → **Git** → connect your GitHub account (or add an SSH deploy key for
`git@github.com:khakanhyder/voicecon.git`). Do this once; both apps reuse it.

---

## 2. Step 1 — Create the project

Sidebar → **Projects** → **Create Project**.

| Field | Value |
|---|---|
| Name | `voicecon` |
| Description | `Voice AI platform` |

Open it. You'll use the **Create Service** dropdown three times.

---

## 3. Step 2 — PostgreSQL

**Create Service → Database → PostgreSQL.**

| Field | Value |
|---|---|
| Name | `voicecon-db` |
| Database Name | `voicecon` |
| Database User | `voicecon` |
| Database Password | *(generate a strong one — save it)* |
| Docker Image | `postgres:16-alpine` |

Click **Create**, then **Deploy**. Wait for the status dot to turn green.

### Get the internal connection string

Open `voicecon-db` → **General** tab → the **Internal Credentials** / connection URL
box. **Copy the hostname Dokploy shows — do not guess it.** Dokploy appends a generated
suffix to container names (e.g. `voicecon-db-a1b2c3`), and all services share the
`dokploy-network`, so the backend reaches it by that internal name on port **5432** —
not the external mapped port.

```
DATABASE_URL=postgresql://voicecon:<password>@<internal-host-from-dokploy>:5432/voicecon
```

If Dokploy hands you a `postgres://` URL, that's fine — `app/database.py:19` normalises
it to `postgresql+asyncpg://` automatically. **Do not add a driver suffix yourself.**

### Why Postgres and not MySQL

The code supports both (`app/database.py:14-21`), and `backend/.env.example` still shows
a stale Railway **MySQL** URL. Ignore that — your dev `.env` is Postgres and the 17
migrations are exercised against Postgres. Deploy on what you actually test against.
Plain Postgres is enough; nothing in the codebase uses pgvector.

### Two settings to get right

- **Leave the external port unset.** Don't expose Postgres to the internet. If you need
  `psql`, tunnel over SSH to the host.
- **Enable scheduled backups** on this service (Backups tab; needs an S3 Destination
  configured in the sidebar). This is your only copy of everything.

---

## 4. Step 3 — Backend application

**Create Service → Application.** Name it `voicecon-backend`, then work through the tabs.

### General tab

| Field | Value |
|---|---|
| Provider | **GitHub** |
| Repository | `khakanhyder/voicecon` |
| Branch | `main` |
| Build Type | **Dockerfile** |
| Docker File | `backend/Dockerfile` |
| Docker Context Path | `backend` |
| Docker Build Stage | *(leave empty)* |

> The context path is what trips people up: the Dockerfile does `COPY requirements.txt .`
> relative to its context. Set the context to `backend`, not the repo root, or the build
> fails on a missing file.

### Environment tab

Paste the backend block from **§6**. Click **Save**.

### Domains tab

**Add Domain:**

| Field | Value |
|---|---|
| Host | `api.yourdomain.com` |
| Path | `/` |
| Container Port | **8000** |
| HTTPS | **on** |
| Certificate Provider | **Let's Encrypt** |

Traefik proxies WebSockets transparently — no extra configuration is needed for
`/api/v1/agents/{id}/stt`, `/api/v1/voice/stream/{call_id}`, or the workflow execution
stream.

### Advanced tab

**Volumes → Add Mount** (required — call recordings are written to local disk and
`app/main.py:320` serves them as static files; without this they vanish on every
redeploy):

| Field | Value |
|---|---|
| Mount Type | **Volume Mount** |
| Volume Name | `voicecon-recordings` |
| Mount Path | `/app/recordings` |

**Cluster Settings → Replicas: `1`.** Not optional — see §0.

**Health check** (Swarm settings, optional): path `/health`. Note that `/health` doesn't
touch the database, so it stays green during DB outages. Use `/api/v1/health/ready` if
you want the check to actually gate on database reachability.

### Deploy

**Deployments tab → Deploy.** Watch the logs. A successful boot shows, in order:

```
INFO  [alembic] Running upgrade ... -> 0016_backfill_call_timing
Mounted N API routes at /api/v1
Analytics scheduler started
Workflow scheduler started
Billing scheduler started
Uvicorn running on http://0.0.0.0:8000
```

### What happens on every boot

`backend/start.sh` runs automatically:

1. **`alembic upgrade head`** — migrations. **Exits non-zero on failure**, so a bad
   migration fails the deploy loudly and Dokploy keeps the previous container serving,
   instead of running on a stale schema and 500-ing every request. Currently a single
   head (`0016_backfill_call_timing`), so no merge is needed.
2. **`python -m scripts.seed_data`** — idempotent seed of integration connectors and
   subscription plans. Non-fatal on failure. **If this is skipped, the
   `integration_connectors` table stays empty and every integration in the UI shows
   "Requires Server Config".**
3. **`uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`**

You never run migrations by hand. They're part of the deploy.

---

## 5. Step 4 — Frontend application

**Create Service → Application.** Name it `voicecon-frontend`.

### General tab

| Field | Value |
|---|---|
| Provider | **GitHub** |
| Repository | `khakanhyder/voicecon` |
| Branch | `main` |
| Build Type | **Dockerfile** |
| Docker File | `frontend/Dockerfile` |
| Docker Context Path | `frontend` |

### 🚨 The single most common way this deploy fails

**`NEXT_PUBLIC_*` values are compiled into the JavaScript bundle at build time — they
are not read at runtime.** `next.config.js` inlines them through its `env` block.

If you set them only as runtime environment variables, the container starts fine, the
page loads fine, and **every API call in the browser goes to `http://localhost:8000`**
and fails. There is no error in the container logs — it looks like a backend problem
when it isn't.

`frontend/Dockerfile` already declares the matching `ARG`s, so they must arrive as
**build arguments**.

**Option A — Dokploy build args (do this first).** Environment tab → the **Build-time
Variables** / **Build Arguments** box, which is *separate* from the runtime Environment
box. Paste the build-args block from §7.

**Option B — commit `frontend/.env.production` (bulletproof fallback).** If you can't
find the build-args field, Next.js loads `.env.production` automatically during
`next build`. Every one of these values is public by definition — they ship inside the
browser bundle regardless — so committing them leaks nothing.

```bash
# frontend/.env.production
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_xxx
NEXT_PUBLIC_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
NEXT_PUBLIC_APPLE_CLIENT_ID=com.yourcompany.web
NEXT_PUBLIC_APPLE_REDIRECT_URI=https://app.yourdomain.com/login
```

Note `.env.production` is currently in `.gitignore` — remove that line, or
`git add -f frontend/.env.production`. Real environment variables take precedence over
`.env` files in Next.js, so doing both is safe: the build arg wins when present.

**Never put a secret in a `NEXT_PUBLIC_*` variable.** Only the Stripe *publishable* key
belongs here, never `sk_live_…`.

### Environment tab (runtime)

Also paste the same `NEXT_PUBLIC_*` values into the **runtime** Environment box. The
`src/app/api/integrations/oauth/callback/route.ts` route handler runs server-side inside
the container and reads `NEXT_PUBLIC_API_URL` at request time.

### Domains tab

| Field | Value |
|---|---|
| Host | `app.yourdomain.com` |
| Path | `/` |
| Container Port | **3000** |
| HTTPS | **on** |
| Certificate Provider | **Let's Encrypt** |

No volume needed — the frontend is stateless. Replicas may exceed 1, though there's
little reason to.

### Deploy — but only after the backend is live

The frontend bakes the backend URL into its bundle, so the backend domain must exist and
resolve first.

---

## 6. Backend environment variables — every one explained

Paste into the backend's **Environment** box. Substitute your real values.

### Core — required

```bash
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<your openssl rand -hex 32>
ENCRYPTION_SALT=<your openssl rand -hex 16>
DATABASE_URL=postgresql://voicecon:<password>@<internal-host>:5432/voicecon
RECORDINGS_PATH=/app/recordings
```

| Variable | What it does |
|---|---|
| `ENVIRONMENT` | `production` enables `is_production`, which suppresses raw exception text in error responses. |
| `DEBUG` | **Must be `false`.** `true` exposes `/docs`, `/redoc` and the OpenAPI JSON publicly, echoes exception details to clients, and runs `init_db()` at startup (Alembic owns the schema — you don't want both). |
| `SECRET_KEY` | Signs JWTs **and** seeds credential encryption. Changing it logs everyone out *and* breaks stored credentials. |
| `ENCRYPTION_SALT` | Hex string; combined with `SECRET_KEY` to derive the Fernet key for stored integration credentials. Must be valid hex or startup fails. |
| `DATABASE_URL` | Plain `postgresql://` — the app adds the async driver itself. |
| `RECORDINGS_PATH` | Works around the bug in §1.1. Must match the volume mount path. |

### URLs and CORS — required

```bash
BACKEND_CORS_ORIGINS=https://app.yourdomain.com
FRONTEND_URL=https://app.yourdomain.com
API_BASE_URL=https://api.yourdomain.com
WEBSOCKET_URL=wss://api.yourdomain.com
TWILIO_PUBLIC_BASE_URL=https://api.yourdomain.com
```

| Variable | What it does |
|---|---|
| `BACKEND_CORS_ORIGINS` | Browser origins allowed to call the API. Accepts comma-separated **or** a JSON array. **Exact match — scheme included, no trailing slash.** If you serve apex *and* `www`, list both. Get this wrong and every browser request fails CORS while `curl` works fine. |
| `FRONTEND_URL` | Base for team-invitation Accept/Reject links and the OAuth origin. Wrong value → invitation emails link to the wrong host. |
| `API_BASE_URL` | Builds Twilio webhook URLs for purchased numbers. **Buying a phone number is refused outright while this is unset** (`app/services/telephony/number_provisioning.py:52-60`). |
| `WEBSOCKET_URL` | Twilio Media Streams target. Falls back to the request `Host` header, which is usually right behind Traefik — set it explicitly anyway. |
| `TWILIO_PUBLIC_BASE_URL` | The public base Twilio signs its webhooks against. Required for signature validation to pass behind a TLS-terminating proxy. |

### AI providers — required for the product to work at all

```bash
OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...
ELEVENLABS_API_KEY=...
# OPENAI_BASE_URL=https://openrouter.ai/api/v1    # only if routing through a gateway
# ANTHROPIC_API_KEY=...                            # only if using Claude models
```

OpenAI drives the LLM, Deepgram does speech-to-text, ElevenLabs does text-to-speech.
Without these the agents cannot hold a conversation.

### Email — required, and a hard gate on launch

Production sends from the `noreply@voicecon.ai` cPanel mailbox
(`server.vconekthost.com`):

```bash
EMAIL_PROVIDER=auto
EMAIL_FROM=noreply@voicecon.ai
EMAIL_FROM_NAME=Voicecon
SMTP_HOST=mail.voicecon.ai
SMTP_PORT=465
SMTP_USERNAME=noreply@voicecon.ai   # full address, not just "noreply"
SMTP_PASSWORD=...                   # cPanel > Email Accounts > Manage
SMTP_USE_TLS=false
SMTP_USE_SSL=true
REQUIRE_EMAIL_VERIFICATION=true
```

Port 465 (implicit SSL) is the safest choice: many hosts block outbound 587 from
containers. If 465 is unreachable, fall back to `SMTP_PORT=587` with
`SMTP_USE_TLS=true` / `SMTP_USE_SSL=false`.

Exim rejects a `From` that isn't a mailbox on the authenticated account, so
`EMAIL_FROM` must stay equal to `SMTP_USERNAME`. For inbox placement, confirm
cPanel's SPF and DKIM records for `voicecon.ai` are published in DNS
(cPanel > Email Deliverability).

Verify after deploy with `python scripts/test_smtp.py you@example.com`.

> **Test email delivery before you announce the deploy.** With
> `REQUIRE_EMAIL_VERIFICATION=true` and no working SMTP transport, `EMAIL_PROVIDER=auto`
> silently falls back to a **console** provider that *logs* the verification code instead
> of sending it. Because `DEBUG=false`, the code isn't returned in the API response
> either. Result: **nobody can register an account or reset a password**, and no error is
> shown anywhere in the UI.

Port **587** → `SMTP_USE_TLS=true`, `SMTP_USE_SSL=false` (STARTTLS).
Port **465** → `SMTP_USE_TLS=false`, `SMTP_USE_SSL=true` (implicit TLS).
SendGrid instead of SMTP: set `SENDGRID_API_KEY` + `SENDGRID_FROM_EMAIL`, leave SMTP blank.

### Stripe — required for billing

```bash
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

`stripe_configured` requires a key starting with `sk_` and containing no `...`
placeholder — otherwise billing degrades silently. `STRIPE_WEBHOOK_SECRET` comes from
the webhook endpoint you create in §8; without it every subscription event is rejected,
so checkouts succeed but plans never activate.

### Telephony — optional

```bash
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...
TWILIO_VALIDATE_WEBHOOKS=true
```

This is Voicecon's **shared** Twilio account — the default users buy numbers on when
they haven't connected their own. Set both `SID` and `TOKEN` and "Twilio · Voicecon
shared account" appears in the Purchase Number picker for everyone, billed to you. Leave
blank and users must connect their own Twilio under Integrations first.

Keep `TWILIO_VALIDATE_WEBHOOKS=true`. Signatures are validated against whichever account
owns the called number, so bring-your-own-Twilio users still work correctly.

### Social login — optional

```bash
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=...
APPLE_CLIENT_ID=com.yourcompany.web
APPLE_TEAM_ID=...
APPLE_KEY_ID=...
APPLE_PRIVATE_KEY=...
```

Google sign-in activates only when **both** ID and secret are set; Apple needs only
`APPLE_CLIENT_ID` for pure sign-in (the Team/Key/Private-key trio is for authorization-code
exchange). **`GOOGLE_CLIENT_ID` here must exactly match `NEXT_PUBLIC_GOOGLE_CLIENT_ID` on
the frontend** — the frontend sends the token, the backend verifies its *audience*
against its own value, and a mismatch fails every login.

### Everything else — optional

```bash
LOG_LEVEL=INFO
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
# SENTRY_DSN=https://...                    # error tracking
# REDIS_URL=redis://<host>:6379/0           # only /health/detailed uses it today
# MAILCHIMP_API_KEY=...-us21                # launching-soon waitlist
# MAILCHIMP_AUDIENCE_ID=...
# AWS_ACCESS_KEY_ID= / AWS_SECRET_ACCESS_KEY= / AWS_S3_BUCKET=   # future S3 recordings
```

---

## 7. Frontend environment variables — every one explained

**All five go in BOTH places: the Build Args box and the runtime Environment box.**

```bash
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_xxx
NEXT_PUBLIC_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
NEXT_PUBLIC_APPLE_CLIENT_ID=com.yourcompany.web
NEXT_PUBLIC_APPLE_REDIRECT_URI=https://app.yourdomain.com/login
```

| Variable | What it does | Rules |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL for every API call **and** the source of the WebSocket URL. | **No trailing slash** (it's concatenated directly with paths). **Must be `https://`** — WS URLs are made by swapping the scheme, so `http` silently yields `ws://`, which browsers block as mixed content on an HTTPS page. |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Mounts Stripe Elements in the browser. | `pk_live_…` in production. Publishable key only — **never** the secret key. |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Renders the Google sign-in button. | Must equal the backend's `GOOGLE_CLIENT_ID`. |
| `NEXT_PUBLIC_APPLE_CLIENT_ID` | Apple Services ID for the Apple sign-in button. | Must equal the backend's `APPLE_CLIENT_ID`. |
| `NEXT_PUBLIC_APPLE_REDIRECT_URI` | Apple's return URL. | Must exactly match the return URL registered in the Apple Developer portal, HTTPS only. |

**`NEXT_PUBLIC_WS_URL` is vestigial** — despite being in `.env.local.example` and the
Dockerfile, nothing in `src/` reads it. WebSocket URLs are derived from
`NEXT_PUBLIC_API_URL`. Setting it is harmless; omitting it changes nothing.

**Any change to a `NEXT_PUBLIC_*` value requires a full rebuild, not a restart.**

### One build-safety warning

`next.config.js` sets `ignoreBuildErrors: true` and `ignoreDuringBuilds: true`, so
**TypeScript and ESLint errors will not fail your Dokploy build** — broken code deploys
successfully and breaks at runtime. Run `npm run type-check` locally before pushing.

---

## 8. External service configuration

Do these **after** both apps are live on their real domains.

### Stripe

Dashboard → Developers → Webhooks → **Add endpoint**:

```
https://api.yourdomain.com/api/v1/billing/webhooks/stripe
```

Subscribe to the checkout and subscription lifecycle events, copy the signing secret
into `STRIPE_WEBHOOK_SECRET`, and redeploy the backend.

### Twilio

Numbers purchased **through the app** get their webhooks configured automatically from
`API_BASE_URL`. For manually configured numbers:

| Purpose | URL |
|---|---|
| Voice (incoming) | `https://api.yourdomain.com/api/v1/telephony/twilio/voice/{agent_id}` |
| Status callback | `https://api.yourdomain.com/api/v1/telephony/twilio/status` |
| Media stream | `wss://api.yourdomain.com/api/v1/voice/stream/{call_id}` |

### Google OAuth

Cloud Console → APIs & Services → Credentials → your Web client:

- Authorised JavaScript origins: `https://app.yourdomain.com`
- Authorised redirect URIs: `https://app.yourdomain.com/login`

### Apple Sign In

Services ID → return URL `https://app.yourdomain.com/login`. Apple **rejects non-HTTPS
and rejects localhost**, so this can only be tested on the real domain.

---

## 9. Deploy order and verification

**Order matters.** The frontend bakes the backend URL into its bundle:

1. **Postgres** → wait for green
2. **Backend** → watch logs for the Alembic upgrade and `Mounted N API routes at /api/v1`
3. **Frontend**

### Command-line checks

```bash
# Backend alive
curl https://api.yourdomain.com/health
# → {"status":"healthy","version":"0.1.0","environment":"production"}

# Database actually reachable (this one queries)
curl https://api.yourdomain.com/api/v1/health/ready

# Routes mounted — expect 401 or 422, NOT 404.
# A 404 here means the API router failed to import.
curl -i https://api.yourdomain.com/api/v1/agents

# CORS preflight — response must echo your frontend origin
curl -i -X OPTIONS https://api.yourdomain.com/api/v1/auth/login \
  -H "Origin: https://app.yourdomain.com" \
  -H "Access-Control-Request-Method: POST"

# Frontend alive
curl -I https://app.yourdomain.com
```

### Browser checks at `https://app.yourdomain.com`

- **DevTools → Network:** confirm XHRs go to `https://api.yourdomain.com`, **not**
  `localhost:8000`. If they hit localhost, your `NEXT_PUBLIC_API_URL` was set as a
  runtime variable instead of a build arg — fix it and **rebuild**.
- **Register an account** → confirm the verification email actually arrives.
- **Dashboard → Integrations** → connectors are listed and do **not** all read
  "Requires Server Config" (proves `seed_data` ran).
- **Open an agent → Test page → mic** → confirms the `wss://` STT socket connects.
- **Billing page** → plans are listed (proves plan seeding and Stripe config).

---

## 10. Operations

**Redeploys.** Deployments tab → copy the **Webhook URL** and add it to GitHub (Settings
→ Webhooks) to auto-deploy on push to `main`. Migrations run automatically on every
boot. A failed migration fails the deploy and leaves the previous container serving.

**Changing a `NEXT_PUBLIC_*` value** requires a frontend **rebuild**, not a restart.

**Never change `SECRET_KEY` or `ENCRYPTION_SALT`** after go-live — see §1.2.

**Backups.** Configure an S3 Destination in the Dokploy sidebar, then enable scheduled
backups on `voicecon-db`. Verify a restore works *before* you have real users. Also back
up the `voicecon-recordings` volume, or migrate recordings to S3 (the `AWS_S3_BUCKET`
settings already exist) — a volume doesn't survive moving to another host.

**Scaling.** Replicas stay at 1 until the schedulers move out of the API process.

**Secure the Dokploy panel itself.** It's currently reachable over plain HTTP at
`http://15.204.116.11:3000`, which means your Dokploy password and every secret you
paste into these forms travel unencrypted. Put the panel behind a domain with HTTPS
(Settings → Web Server → Domain) before pasting production credentials.
