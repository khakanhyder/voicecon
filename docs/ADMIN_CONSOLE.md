# Platform Admin Console

`/admin` in the frontend is the operator console for Voicecon staff. It works
across every workspace and manages the platform's own provider keys. It is
separate from workspace roles: a workspace owner is not a platform admin.

## Creating the first admin

1. Sign up normally.
2. Do one of these:
   - Set `PLATFORM_ADMIN_EMAILS=you@company.com` in the backend environment and
     restart. The API promotes that address when it starts. This setting only
     ever promotes accounts. Removing an address from it does not demote anyone.
   - Run `python -m scripts.make_platform_admin you@company.com` from `backend/`.
3. Sign in again. The app sidebar now shows **Admin Console**.

Once you have one admin, grant or revoke others from **Users** in the console.
The console refuses to demote the last admin. It also stops you disabling or
demoting yourself.

## What each section does

| Section | Use it to |
|---|---|
| Overview | See revenue, sign-ups, the call chart, the subscription mix, and anything that needs attention |
| API Keys & Providers | Set or rotate provider keys (OpenAI, Anthropic, Deepgram, ElevenLabs, Twilio, Stripe, email, S3, Google/Apple sign-in, integration OAuth apps), rate limits and public URLs. Each provider has a **Test connection** button |
| Plans & Pricing | Edit prices, trial length, features, limits and pricing-page copy |
| Organizations | Search every workspace. Suspend or reactivate it, extend a trial, give a plan for free, set per-organization feature and limit overrides, reset usage |
| Users | Verify, disable, sign out everywhere, clear a login lockout, grant or revoke admin |
| Billing | Work the payment-failure queue, read the subscription ledger, run the reconciler on demand |
| Calls / Phone Numbers | Look at any tenant's calls, transcripts, recordings and numbers, for support |
| Integrations & Workflows | Find expired or failing connections and failed workflow runs |
| System Health | Check DB, Redis, schedulers, server secrets and provider status |
| Audit Log | See every change made in the console: who, what, when, and from which IP |

## How dashboard keys work

- **Precedence:** dashboard value, then the server environment, then the
  built-in default. Removing a dashboard value brings back the environment value.
- **Propagation:** the value applies immediately on the server that saved it.
  Every other API process and Celery worker picks it up within about 15 seconds.
  No redeploy is needed. Live AI, voice and Twilio clients build a new client
  when their key changes.
- **Storage:** secrets are encrypted with `ENCRYPTION_SECRET_KEY` and
  `ENCRYPTION_SALT`, the same key used for integration credentials. The API
  never returns a stored secret. It only returns the last four characters.
  `scripts/reencrypt_credentials.py` also re-encrypts dashboard secrets when
  that key rotates.
- **Environment only:** these can never be set from the dashboard:
  `SECRET_KEY`, `ENCRYPTION_SECRET_KEY`, `ENCRYPTION_SALT`, `DATABASE_URL`,
  `REDIS_URL`, `ENVIRONMENT`, `DEBUG`, `BACKEND_CORS_ORIGINS` and
  `EGRESS_ALLOW_PRIVATE`. They protect the database, or they have to exist
  before the database can be read.
- **Frontend `NEXT_PUBLIC_*` values** are compiled into the frontend at build
  time. They still need a rebuild to change.

## Free trial length

**Plans & Pricing → Free trial length** sets how many days a new card-free
trial lasts. It applies to every plan, because a trial runs on whichever
trialable plan it starts on. The public pricing API and onboarding read the new
value straight away, and a restart does not reset it. Trials that have already
started keep their end date; use **Extend trial** on an organization to change
one. Marketing copy on the landing page and in the terms still says 30 days and
has to be edited by hand.

## Billing actions: how each one behaves

- **Extend trial** adds days to the trial end. If the trial has already
  lapsed, the days count from today. It can revive an expired trial. Workflows
  that were paused when the trial expired stay paused.
- **Grant plan** creates a free "manual" subscription. Its usage counters reset
  every month, and it lasts until you click **End comp**. You cannot grant a
  plan while the organization pays through Stripe; change that subscription in
  Stripe instead.
- **Entitlement override** turns individual features on or off and changes
  individual limits on top of the plan, with an optional expiry date.
- **Plan edits** apply to every subscriber straight away. An edited plan is
  flagged `admin_managed`, so the startup plan seeding no longer resets it.
  When you change a price, a new Stripe price is created for new sign-ups and
  plan changes. Existing subscribers keep their current price.

## Security model

- Every `/api/v1/admin/*` route needs a signed-in user with
  `users.is_platform_admin = true`. API keys are rejected, even when an admin
  owns the key.
- Every change is written to `admin_audit_logs` in the same database
  transaction as the change itself.
- Login lockouts are held in each server process's memory, so **Unlock** clears
  the lockout only on the server that handled the request.
