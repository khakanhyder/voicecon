# OAuth Integrations — Setup & How Users Connect

How to make the OAuth integrations (HubSpot, Salesforce, Slack, Google Calendar/Sheets/
Drive, Notion) connectable, and how an end user connects once they are.

---

## The model in one picture

OAuth has **two levels**, and this is the key to understanding it:

```
YOU (platform owner) — ONE TIME per provider:
    register an OAuth app with the provider → get client_id + client_secret
    → put them in the server environment

EACH END USER — every time:
    click "Connect" → provider's consent screen → approve → done
    (the user never sees or needs any credentials)
```

So **the credentials are yours, set once.** Your users connect with a single click and
never touch a client_id or secret. This is how every "Connect your Google/Slack/HubSpot"
button on every SaaS works.

---

## What Phase 9 changed (the code side — done)

Before, no OAuth connector could even start — the flow raised "Missing OAuth2 configuration"
because nothing supplied the client credentials or endpoints. Now:

- A **provider registry** ([oauth_providers.py](../backend/app/services/integrations/oauth_providers.py))
  holds each provider's public endpoints (authorize/token URLs, default scopes) and which
  env vars carry its client credentials.
- The flow reads **client_id/secret from environment variables** and endpoints from the
  registry — the standard multi-tenant pattern.
- Fixed a latent crash (the OAuth connection creation used the reserved `metadata` field).
- Errors are now clear ("HubSpot is not configured for OAuth on this server…") instead of
  cryptic, and Google requests refresh tokens correctly (`access_type=offline`).

Verified: authorize URLs build correctly per provider; a clear error shows when credentials
aren't set. **What remains is providing the credentials — which only you can do**, because
registering an OAuth app requires signing into each provider.

---

## Step 1 — Register an OAuth app with each provider (you, once)

Do this only for the providers you actually want. The four with working *action* code —
**HubSpot, Salesforce, Slack, Google Calendar** — are the highest value.

For each provider, the one required setting is the **redirect URI** (a.k.a. callback URL).
Use your deployed frontend's callback:

```
https://voicecon-fe.onrender.com/dashboard/integrations/oauth/callback
```

| Provider | Where to register | Env vars to set |
|---|---|---|
| **Google** (Calendar/Sheets/Drive) | Google Cloud Console → APIs & Services → Credentials → OAuth client ID (Web application). Enable the relevant API (e.g. Google Calendar API). | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| **HubSpot** | HubSpot Developer account → Apps → Create app → Auth tab | `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET` |
| **Slack** | api.slack.com/apps → Create New App → OAuth & Permissions | `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET` |
| **Salesforce** | Setup → App Manager → New Connected App → Enable OAuth | `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET` |
| **Notion** | notion.so/my-integrations → New integration (public) | `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET` |

Notes:
- The **three Google connectors share one app** — set `GOOGLE_CLIENT_ID`/`SECRET` once and
  Calendar, Sheets, and Drive all work.
- Add the exact redirect URI above to each provider's allowed redirect list — it must match
  byte-for-byte (scheme, host, path, no trailing slash).

## Step 2 — Put the credentials in the server environment (you)

On Render → your **backend** service (`voicecon-be`) → **Environment** → add the vars from the
table above. Example:

```
GOOGLE_CLIENT_ID=1234-abc.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxx
HUBSPOT_CLIENT_ID=...
HUBSPOT_CLIENT_SECRET=...
```

Save → Render redeploys. Only set the providers you registered; the rest stay disabled and
show the "not configured on this server" message, which is correct.

## Step 3 — How an end user connects (them, one click)

Once you've done Steps 1–2 for a provider, any user of your platform connects like this:

1. **Integrations** page → pick the app (e.g. HubSpot) → **Connect**.
2. They're redirected to the provider's **consent screen** (HubSpot/Google/Slack login).
3. They approve the requested permissions.
4. Provider redirects back to `…/integrations/oauth/callback`; the backend exchanges the code
   for a token, encrypts it, and stores the connection.
5. The card flips to **Connected**. Their agent/workflows can now use it.

The user needs **no credentials** — they just log into their own account and approve. Each
user's own token is stored separately, so different users connect their own accounts.

---

## How to verify it works

**Without credentials (now):** click Connect on an OAuth app → you get a clear message that
the admin must configure it. That's expected until Step 2 is done.

**After configuring a provider:** click Connect → you should be redirected to the real
provider consent screen (not an error). Approve → you land back on the Integrations page with
the card Connected. Then hit **Test** on the connection, or run a workflow action (e.g.
HubSpot `create_contact`) to confirm the token works.

> Full end-to-end (redirect → consent → callback → token) can only be verified with a real
> registered app, because the provider's login is involved. The URL generation, credential
> resolution, error handling, and token-storage path are done and tested.

---

## Which integrations are worth connecting

| Connector | OAuth configured | Has action code | Worth it |
|---|---|---|---|
| HubSpot | ✅ | ✅ | Yes — connect + real CRM actions |
| Salesforce | ✅ | ✅ | Yes |
| Slack | ✅ | ✅ | Yes |
| Google Calendar | ✅ | ✅ | Yes |
| Google Sheets / Drive | ✅ | ⚠️ no action code yet | Connect works; actions need building |
| Notion | ✅ | ⚠️ no action code yet | Connect works; actions need building |
| Others (Zendesk, Monday, Pipedrive, Intercom, Calendly, MS Teams, Zapier) | not in registry | no action code | Add to the registry when needed |

**API-key integrations** (Stripe, SendGrid, Langfuse, Twilio, Airtable, etc.) don't use OAuth
— users just paste their key (that path was fixed in Phase 2, no admin setup needed).

---

## Summary

- **Code: done.** The OAuth mechanism works and is tested; the blocking bugs are fixed.
- **Credentials: yours to provide.** Register an app per provider (Step 1), set the env vars
  (Step 2). One-time, per provider.
- **Users: one click.** After that, any user connects their own account with a single Connect
  → approve, no credentials required.

---

# Appendix — Detailed per-provider registration walkthrough

Three things you'll copy for every provider:

- **Redirect URI** (paste this exactly, everywhere it's asked for):
  `https://voicecon-fe.onrender.com/dashboard/integrations/oauth/callback`
- **Client ID** and **Client Secret** — each provider gives you these; you paste them into
  the Render backend env.
- It must match **byte-for-byte** — `https`, the host, the path, no trailing slash.

After registering each one, go to **Render → `voicecon-be` service → Environment**, add the
two variables, and Save (Render redeploys).

---

## A. Google (Calendar, Sheets, Drive) → `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`

One app covers all three Google connectors.

1. Go to **console.cloud.google.com** and sign in.
2. Create a project (top bar → project dropdown → **New Project**), name it e.g. "Voicecon",
   then select it.
3. **Enable the APIs** you'll use: left menu → **APIs & Services → Library** → search and
   **Enable** each: "Google Calendar API" (and "Google Sheets API" / "Google Drive API" if
   you want those).
4. **Configure the consent screen:** APIs & Services → **OAuth consent screen**:
   - User type: **External** → Create.
   - Fill App name, user support email, developer email → Save and continue.
   - **Scopes:** you can leave this and let the app request scopes at runtime, or add
     `.../auth/calendar` → Save.
   - **Test users:** while the app is in "Testing" mode, add the Google accounts that are
     allowed to connect (add your own email and any client emails). Save.
5. **Create the credential:** APIs & Services → **Credentials** → **Create Credentials** →
   **OAuth client ID**:
   - Application type: **Web application**.
   - Name: "Voicecon Web".
   - **Authorized redirect URIs → Add URI:** paste the redirect URI above.
   - **Create**.
6. A dialog shows your **Client ID** and **Client Secret** — copy both.
7. In Render backend env: `GOOGLE_CLIENT_ID=<client id>`, `GOOGLE_CLIENT_SECRET=<secret>`.

Notes:
- In **Testing** mode only your added test users can connect. To open it to anyone, submit
  for verification (Publishing status → Publish) — needed only for public/production use.
- Our flow already sends `access_type=offline` so Google returns a refresh token.

---

## B. HubSpot → `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET`

HubSpot disabled public-app creation in the developer UI (Legacy Apps → **Public** is
greyed out: "New legacy public app creation is disabled"). Public apps — the only kind
that does the OAuth flow this connector uses — are now created with the CLI. A **private**
app is not an alternative: it issues a static token and has no authorize step.

The app definition lives in the repo at `integrations/hubspot-app/`.

1. `npm install -g @hubspot/cli@latest` (needs v7.6.0+).
2. `hs account auth` — opens a browser; pick the **developer** account.
3. `cd integrations/hubspot-app && hs project upload`.
4. `hs project open` → the app's **Auth** tab → **Client credentials** → copy the
   **Client ID** and **Client Secret**.
5. Set `HUBSPOT_CLIENT_ID` / `HUBSPOT_CLIENT_SECRET` (Dokploy env, or /admin →
   Integration OAuth apps, which overrides env).

`redirectUrls` and `requiredScopes` in `src/app/app-hsmeta.json` are the app's side of the
contract; the backend's side is `auth_config.scopes` on the `hubspot` connector row,
seeded from `backend/scripts/seed_data.py`. They must match — HubSpot fails the authorize
step on any scope the app does not have, and rejects any `redirect_uri` not listed
verbatim. Both currently carry `oauth`, `crm.objects.contacts.read`,
`crm.objects.contacts.write`, `crm.objects.deals.read`, `crm.objects.deals.write`.

Do not use the old broad `contacts` scope: it is being sunset, and HubSpot has already
migrated existing app configs to the granular scopes.

To connect, a user opens their own HubSpot account's consent screen and approves.

---

## C. Slack → `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`

1. Go to **api.slack.com/apps** → **Create New App** → **From scratch** → name it, pick a
   workspace for development.
2. **OAuth & Permissions** (left menu):
   - **Redirect URLs → Add** the redirect URI above → Save URLs.
   - **Scopes → Bot Token Scopes:** add `chat:write` and `channels:read`.
3. **Basic Information** (left menu): copy **Client ID** and **Client Secret** under "App
   Credentials".
4. Render backend env: `SLACK_CLIENT_ID=...`, `SLACK_CLIENT_SECRET=...`.

Note: Slack scopes are workspace-installed; a user connecting picks their workspace and
approves.

---

## D. Salesforce → `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET`

Salesforce disabled creation of classic **Connected Apps** — Winter '26 for new orgs,
Spring '26 for all orgs. The only app type you can create now is an **External Client
App (ECA)**, and that changes what works.

1. Salesforce → **Setup** → Quick Find **External Client App Manager** → **New External
   Client App**.
2. Name, contact email. **Distribution State** is set here and **cannot be changed
   afterwards**:
   - **Local** — usable only by users of this org. Fine for connecting Voicecon's own
     Salesforce org. Requires `SALESFORCE_LOGIN_URL` (step 5).
   - **Packaged** — required for customers on their own orgs. Needs the app shipped in a
     2GP managed package that each customer installs; see "Cross-org" below.
3. **OAuth Settings** → Enable OAuth:
   - **Callback URL:** paste the redirect URI above.
   - **OAuth Scopes:** "Manage user data via APIs (api)" and "Perform requests at any time
     (refresh_token, offline_access)".
   - PKCE either way is fine — the backend always sends a code challenge and
     verifier.
   - Under **Flow Enablement**, tick **Enable Authorization Code and Credentials Flow**.
   - Under **Policies** (after saving), set **Permitted Users** so users can self-authorize.
4. **Consumer Key and Secret** → `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET`.
5. **`SALESFORCE_LOGIN_URL`** — the login host. Empty means `https://login.salesforce.com`.
   - Local ECA: set it to the owning org's **My Domain**, e.g.
     `https://orgfarm-1234.my.salesforce.com`. Without this the callback fails with
     `OAUTH_AUTHORIZATION_BLOCKED` / "Cross-org OAuth flows are not supported for this
     external client app", because `login.salesforce.com` is a cross-org entry point and a
     Local app refuses it.
   - Sandbox: `https://test.salesforce.com`.

### Cross-org: letting customers connect their own Salesforce orgs

A Local ECA can never do this, and no Voicecon-side setting changes that — the block is in
Salesforce. The supported route is to distribute the app:

1. Create the ECA with **Distribution State = Packaged** in a stable org that will outlive
   every release (not a trial or scratch org). OAuth consumer credentials are *global
   settings* and stay in that org rather than travelling in the package.
2. Package it as a 2GP managed package (Salesforce DX / `sf` CLI + a Dev Hub).
3. Give each customer admin the package install link; they install it and grant access in
   their org.
4. Their users can then complete the normal Voicecon connect flow.

Salesforce Support can also grant an exception to re-enable classic Connected App creation
for an org, which restores the old cross-org-by-default behaviour without packaging. Worth
asking for if the packaging route is too heavy for now.

## E. Notion → `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`

1. **notion.so/my-integrations** → **New integration** → choose **Public** (public integrations
   support OAuth; internal ones don't).
2. Set the **Redirect URI** to the one above.
3. Copy **OAuth client ID** and **OAuth client secret**.
4. Render backend env: `NOTION_CLIENT_ID=...`, `NOTION_CLIENT_SECRET=...`.

---

## After setting the env vars — verify

1. Render redeploys the backend automatically after you save env vars. Wait for it to go live.
2. In the app: **Integrations → the provider → Connect**.
3. Expected: you're redirected to the **real provider consent screen** (not the "not
   configured" message). Approve → you land back on Integrations with the card **Connected**.
4. If you get "redirect_uri_mismatch": the URI in the provider console doesn't exactly match
   `https://voicecon-fe.onrender.com/dashboard/integrations/oauth/callback` — fix the trailing
   slash / scheme / host.
5. If you get "not configured on this server": the env var isn't set (or the backend hasn't
   redeployed yet).

## Common gotcha checklist

- Redirect URI must be **identical** in the provider console and the app (no trailing slash).
- Set env vars on the **backend** (`voicecon-be`) service, not the frontend.
- Google: add yourself as a **test user** while the app is in Testing mode, or you'll be
  blocked at consent.
- After adding env vars, wait for the **redeploy** to finish before testing.
