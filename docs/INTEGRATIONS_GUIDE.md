# Integrations — What They Are, How to Test, and What Actually Works

Companion to [VOICECON_PLATFORM_GUIDE.md](./VOICECON_PLATFORM_GUIDE.md). Every statement
here was verified against source and the running backend, not the UI.

---

## 1. What an integration is, in this system

An integration connects your agent to an outside service (a CRM, a calendar, Slack) so a
workflow — or, eventually, a tool — can read and write real business data instead of the
agent just talking.

There are **three distinct layers**, and they fail independently. This is the single most
important thing to understand, because the dashboard collapses them into one "Connect"
button.

```
Layer 1  CATALOG        29 cards on the Integrations page       ← what you see
Layer 2  CONNECTION     storing your credential for a service   ← "Connect" / OAuth
Layer 3  ACTION CODE    the Python that calls the service API   ← used by workflows
```

- **Layer 1 (catalog)** is a *hardcoded list in the frontend* — 29 cards with icons and
  descriptions ([integrations/page.tsx:33](../frontend/src/app/dashboard/integrations/page.tsx#L33)).
  The cards render whether or not the backend works. Seeing 29 cards proves nothing.
- **Layer 2 (connection)** stores your OAuth token or API key against a connector.
- **Layer 3 (action code)** is a real connector class (`create_contact`, `send_email`, …)
  that only **6** of the 29 have.

A card on the page does not imply a connection can be made, and a connection does not imply
any action code exists.

---

## 2. The honest coverage map

### Layer 3 — action code exists for 6 of 29

Real connector classes: **HubSpot, Salesforce, Slack, Stripe, SendGrid, Google Calendar**
([connectors/](../backend/app/services/integrations/connectors/)). HubSpot, for example, has
`create_contact`, `update_deal`, `search_contacts`, and more — genuinely implemented.

The other **23** (Airtable, Notion, Zendesk, AWS S3, Twilio, Telnyx, Monday, Pipedrive,
Intercom, Zapier, Make, …) are **catalog-only**. They have a card and a seeded DB row but no
action code. A workflow Action step against them raises `Unsupported connector: <slug>`
([step_handlers.py:235](../backend/app/services/workflows/step_handlers.py#L235)).

### Layers 1–2 — as of this writing, **no connection of any kind can be created**

Two independent blockers, both verified live:

**API-key connectors** (Langfuse, Stripe, SendGrid, AWS S3, GoHighLevel, Twilio, Telnyx,
Airtable, …) fail because the manager stores the key in a column that does not exist:

```
POST /integrations/connections  →  400
"'api_key_encrypted' is an invalid keyword argument for IntegrationConnection"
```

The `IntegrationConnection` model has `auth_data_encrypted`, `access_token_encrypted`,
`refresh_token_encrypted` — but the code writes and reads `api_key_encrypted`
([integration_manager.py:291](../backend/app/services/integrations/integration_manager.py#L291),
[connector_base.py:129](../backend/app/services/integrations/connector_base.py#L129)). The
column was never added. So the credential can't be stored, and the 6 real connectors can't
retrieve it either.

**OAuth connectors** (HubSpot, Salesforce, Slack, Google Calendar, Notion, …) fail because
**no `client_id` is seeded** for any of them:

```
POST /integrations/oauth/authorize  →  "Missing OAuth2 configuration"
```

The client id is read from `connector.auth_config.client_id` in the DB
([integration_manager.py:100](../backend/app/services/integrations/integration_manager.py#L100)),
and all 14 OAuth connectors have it empty. There is no UI or setting to enter one, so the
OAuth flow can't even start.

**Net:** the catalog is real, 6 connectors have real action code, but the connection layer
between them is non-functional. Nothing connects today without the fixes in §5.

### Bugs already fixed this session

Two blockers were fixed while investigating (in [schemas/integration.py](../backend/app/schemas/integration.py)
and [endpoints/integrations.py](../backend/app/api/v1/endpoints/integrations.py)):

- `GET /integrations/connectors` returned **500** — the response schema typed `id` as `str`
  while the ORM returns `UUID` (the same bug class as the Tools endpoint). The page's cards
  come from the frontend's hardcoded list, so this was invisible there, but the real
  connector UUIDs — needed to create any connection — were unreachable. Now returns 200.
- Creating any connection returned **500** — the endpoint read `current_user.organization_id`,
  which does not exist on the `User` model (org membership lives in `organization_members`).
  Now resolved via a helper. This uncovered the deeper `api_key_encrypted` bug above.

---

## 3. How the flow is *supposed* to work (from the user's side)

1. **Integrations page** → pick a service → **Connect**.
2. **API-key services:** a form asks for your key; it's encrypted and stored.
   **OAuth services:** you're redirected to the provider's consent screen, then back to
   `/dashboard/integrations/oauth/callback`, which exchanges the code for a token.
3. The card moves to **Connected** and the counter increments.
4. **Test** the connection: the backend makes one authenticated GET to the provider's
   `test_endpoint` and checks for `200`.
5. In a **Workflow**, add an **Action** step, choose the connection and an action
   (e.g. HubSpot → `create_contact`), and it runs the real connector code.

Steps 1 and the catalog work. Steps 2–5 are blocked by §2 until the fixes land.

---

## 4. How to test a connection, and how to read the result

The test is generic ([integration_manager.py:319](../backend/app/services/integrations/integration_manager.py#L319)):
it builds `base_url + test_endpoint`, attaches your credential, does a `GET`, and reports
`success` only if the status is exactly `200`.

| Result | Meaning |
|---|---|
| `success: true`, 200 | Credential is valid and the service answered. |
| `success: false`, 401/403 | Key/token is wrong, expired, or missing scopes. |
| `success: false`, 404 | `test_endpoint` seeded wrong for that connector. |
| `Connection test error: …` | Network/DNS problem, or a placeholder base_url (e.g. Supabase is seeded as `your-project.supabase.co`). |

**Caveats that will bite even after §5 is fixed:**

- The test uses one credential style: `Authorization: Bearer <token>` for OAuth, or a
  header named by `auth_config.api_key_name` for API keys. Services that need a different
  scheme won't pass. **Stripe** uses `Authorization: Bearer sk_...` — fine. **SendGrid**
  uses `Authorization: Bearer` — fine. But header-name assumptions vary per provider, so a
  `401` may mean "right key, wrong header," not "bad key."
- Storage-style connectors (**AWS S3, GCS, Azure Blob, Cloudflare R2**) and webhook targets
  (**Make, Zapier**) can't be meaningfully tested by a bearer-token GET. Expect failure
  there regardless of credential.
- `success: true` means HTTP 200 — it does **not** mean a later *action* will work, only
  that auth succeeded against the test endpoint.

---

## 5. What it takes to make integrations actually work

In priority order. None of these is large, but they are real code/data changes, not
configuration.

1. **Add the `api_key_encrypted` column** to `IntegrationConnection` (model + migration).
   Four code sites already expect it. This unblocks every API-key connector at once —
   Langfuse, Stripe, SendGrid, and the rest — and lets the 6 real connectors read their key.
   *This is the highest-value fix: it turns the whole API-key half of the catalog on.*
2. **Seed OAuth `client_id` / `authorize_url` / `token_url` / `scopes`** into each OAuth
   connector's `auth_config`, and store the `client_secret` for the callback. This requires
   you to register an OAuth app with each provider (HubSpot, Google, Slack, …) and paste the
   credentials — genuine per-provider setup work, not just code.
3. **Build action code for the 23 catalog-only connectors**, or hide them so they don't
   imply capability they don't have.
4. Fix per-provider **auth-scheme quirks** in the generic test (header name, query-param
   keys) so a valid credential isn't reported as a `401`.

After 1, a realistic first demo is: connect **Langfuse** or **Stripe** with a real API key,
hit **Test**, and get a green `200`. After 2, connect **HubSpot** via OAuth and run a
workflow that creates a contact.

---

## 6. Quick reference

| Symptom | Cause | Section |
|---|---|---|
| 29 cards show but nothing connects | Cards are a hardcoded frontend list | §1 |
| API-key "Connect" → 400 `api_key_encrypted` | Missing DB column | §2, §5.1 |
| OAuth "Connect" → "Missing OAuth2 configuration" | No `client_id` seeded | §2, §5.2 |
| Workflow action → `Unsupported connector` | One of the 23 with no code | §2 |
| Test says 200 but action fails | Test only checks auth, not the action | §4 |
| Test error on S3/Zapier/Make | Not testable by bearer GET | §4 |
| Test `error` on Supabase | base_url is a placeholder | §4 |
