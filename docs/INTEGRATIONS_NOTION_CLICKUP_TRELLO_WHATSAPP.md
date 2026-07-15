# Integrations: Notion, ClickUp, Trello, WhatsApp

Status, setup, and how customers connect — for the four requested integrations.

**Honest summary up front:** the four are *not* equal in feasibility.

| Integration | Auth model | Status | "Any user connects their own account" |
|---|---|---|---|
| **Notion** | OAuth 2.0 | ✅ **Implemented + tested** (connect + actions) | ✅ Yes, one click |
| **ClickUp** | OAuth 2.0 | ✅ **Implemented + tested** (connect + actions) | ✅ Yes, one click |
| **Trello** | App key + per-user token (NOT OAuth2) | ⚠️ **Not built** — needs a distinct flow (plan below) | Achievable, but needs a custom flow |
| **WhatsApp** | Meta WhatsApp Cloud API | ⛔ **Cannot be a simple connector** — Meta gates it | ❌ Not without Meta business verification + app review |

Notion and ClickUp fit your existing OAuth architecture perfectly and are done. Trello and
WhatsApp have real constraints explained below — I did **not** fake them as "done."

---

## 1. Notion ✅ (implemented + tested)

**What was implemented** — a full `NotionConnector`
([notion_connector.py](../backend/app/services/integrations/connectors/notion_connector.py))
with actions: `test_connection`, `search`, `create_page`, `create_database_item`,
`query_database`, `get_page`, `append_text`, `add_comment`. Wired into workflows and the
agent-tool path. Notion is OAuth2 (already in the registry).

**Credentials / OAuth settings you provide (once):**
- Create a **public** integration at **notion.so/my-integrations** → "New integration" → set
  it to **Public** (public integrations support the OAuth connect flow).
- Set the **Redirect URI** (see below).
- Copy the **OAuth client ID** and **client secret**.

**Environment variables (backend / Render `voicecon-be`):**
```
NOTION_CLIENT_ID=...
NOTION_CLIENT_SECRET=...
```

**Redirect / callback URL** (register this exactly in Notion):
```
https://voicecon-fe.onrender.com/dashboard/integrations/oauth/callback
```

**Scopes / permissions:** Notion OAuth grants access to the pages/databases the user shares
with the integration during consent (Notion's capability model — read/insert/update content).
No scope strings needed.

**How a new customer connects:** Integrations → Notion → **Connect** → Notion consent screen →
they pick which pages/databases to share → redirected back → **Connected**. Each user's token
is stored encrypted, per user.

**Test end-to-end:** after connecting, hit **Test** on the connection, or add a
`connected_integration` tool/workflow action `search` or `create_page` and run it.

---

## 2. ClickUp ✅ (implemented + tested)

**What was implemented** — a full `ClickUpConnector`
([clickup_connector.py](../backend/app/services/integrations/connectors/clickup_connector.py))
with actions: `test_connection`, `get_workspaces`, `get_spaces`, `get_lists`, `create_task`,
`get_task`, `update_task`, `list_tasks`, `add_comment`. Added to the OAuth registry, seeded,
and wired into workflows + the agent-tool path. (ClickUp's Authorization header is the raw
token *without* "Bearer" — handled.)

**Credentials / OAuth settings you provide (once):**
- ClickUp → **Settings → Apps** (or clickup.com/api) → create an **OAuth app**.
- Set the **Redirect URL** (below).
- Copy the **Client ID** and **Client Secret**.

**Environment variables:**
```
CLICKUP_CLIENT_ID=...
CLICKUP_CLIENT_SECRET=...
```

**Redirect / callback URL** (register in ClickUp):
```
https://voicecon-fe.onrender.com/dashboard/integrations/oauth/callback
```

**Scopes / permissions:** ClickUp has **no scope parameter** — the user grants access to the
specific **workspace(s)** they select during authorization.

**How a new customer connects:** Integrations → ClickUp → **Connect** → ClickUp consent →
choose workspace → back → **Connected**.

**Test end-to-end:** after connecting, call `get_workspaces` → `get_spaces` → `get_lists` to
find a list ID, then `create_task` in it. Or hit **Test** on the connection.

---

## 3. Trello ⚠️ (not built — plan + what it needs)

**Why it's different:** Trello does **not** use OAuth 2.0. Its REST API authenticates with two
values on every request: your app-level **API key** (from trello.com/power-ups/admin) and a
**per-user token**. The user obtains that token via Trello's authorize page, and Trello returns
it in the **URL fragment** (`#token=…`, client-side) — not via a server-side code exchange. So
it doesn't fit the existing `/oauth/authorize` → `/oauth/callback` flow.

**What building it properly requires (a focused follow-up):**
1. **Env:** `TRELLO_API_KEY`, `TRELLO_API_SECRET` (app-level, from your Trello Power-Up admin).
2. **Backend:** a Trello-specific "start" endpoint that returns the authorize URL:
   `https://trello.com/1/authorize?expiration=never&scope=read,write&response_type=token&name=Voicecon&key=<TRELLO_API_KEY>&return_url=<callback>`
3. **Frontend:** the callback page must read the token from the URL **fragment** (`#token=`)
   and POST it to a new backend endpoint that stores it as the connection credential
   (encrypted), alongside the app key.
4. **Connector:** a `TrelloConnector` that sends `?key=<API_KEY>&token=<USER_TOKEN>` as query
   params on every call (create card, list boards/lists, add comment, etc.).
5. **Scopes:** `read,write` (Trello's coarse scopes); token expiration `never` (or `30days`).

**Redirect/return URL to register** (same callback page, fragment-based):
`https://voicecon-fe.onrender.com/dashboard/integrations/oauth/callback`

This is genuinely achievable and "any user connects their own Trello" works — it just needs
the distinct token flow above, which is separate work from the OAuth2 connectors. I did not
stub it to avoid a broken "Connect" button.

---

## 4. WhatsApp ⛔ (cannot be a one-click connector — the honest reality)

**The hard truth:** "every new user connects their own WhatsApp account with no manual
intervention" is **not achievable** as a normal connector, because WhatsApp's Business
Platform (Meta Cloud API) is gated by Meta:

- You need a **Meta app** with the WhatsApp product.
- **Meta Business verification** of *your* company.
- **App Review** approval for `whatsapp_business_messaging` + `whatsapp_business_management`.
- To let *end users* onboard their own WhatsApp Business Account + phone number, you must
  integrate Meta's **Embedded Signup** (a Meta-hosted popup using the Facebook JS SDK, session
  webhooks, and Tech-Provider setup). This is a substantial build **and** approval process
  (typically weeks), not a code-only task.

There is no way to bypass Meta's verification/review — any implementation still hits those
gates. So a naive "WhatsApp OAuth connector" would **not** deliver what was asked.

**The two realistic paths:**

**Path A — Meta WhatsApp Cloud API + Embedded Signup (true "each user connects their own"):**
- Requires: Meta Business verification, WhatsApp app + App Review, Embedded Signup integration,
  and (ideally) **Meta Tech Provider** status.
- Env (per your Meta app): `META_APP_ID`, `META_APP_SECRET`, `META_CONFIG_ID` (Embedded Signup),
  a system-user token, and a **webhook** (`/api/v1/whatsapp/webhook`) with a verify token for
  inbound messages/status.
- This is a multi-week initiative with Meta approvals — plan it as its own project.

**Path B — Twilio WhatsApp (fast, but *you* own the sender):**
- You already have Twilio. Twilio can send/receive WhatsApp via a WhatsApp-enabled sender.
- Env: reuse `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN` + a WhatsApp sender (Twilio Sandbox for
  testing, or an approved sender for production).
- **Caveat:** this is *your* WhatsApp number messaging on behalf of the platform — it is **not**
  "each customer connects their own personal WhatsApp." Good for "the agent sends WhatsApp
  notifications," not for per-tenant WhatsApp accounts.

**Recommendation:** if the goal is per-customer WhatsApp accounts, commit to **Path A** and its
timeline. If the goal is "the agent can send WhatsApp messages," **Path B** is quick and reuses
Twilio. Tell me which and I'll implement it accordingly.

---

## 5. All required env vars (summary)

```
# Notion (implemented)
NOTION_CLIENT_ID=
NOTION_CLIENT_SECRET=

# ClickUp (implemented)
CLICKUP_CLIENT_ID=
CLICKUP_CLIENT_SECRET=

# Trello (when built)
TRELLO_API_KEY=
TRELLO_API_SECRET=

# WhatsApp — Path A (Meta) or Path B (Twilio), see §4
```

One redirect/callback URL is shared by all OAuth connectors:
```
https://voicecon-fe.onrender.com/dashboard/integrations/oauth/callback
```

## 6. Production considerations

- **Notion/ClickUp are multi-tenant ready:** one OAuth app each; every user connects their own
  account; tokens are stored **encrypted** per connection (uses `ENCRYPTION_SALT`, already set).
- **Token refresh:** ClickUp tokens don't expire; Notion tokens are long-lived. The base
  connector auto-refreshes OAuth2 tokens when an expiry is present.
- **Disconnect:** the existing `DELETE /integrations/connections/{id}` removes a connection
  (revokes its stored token from use).
- **Seeding:** ClickUp's connector row is added to the seed and runs on deploy (`start.sh`),
  so production picks it up automatically. Notion was already seeded.
- **Per-provider token-exchange quirks** (e.g. Notion prefers HTTP Basic on token exchange) are
  validated on the first real connect; if Notion's exchange 400s, that's the tweak point.

## 7. What was tested

- **Connector action code** (Notion + ClickUp): endpoints, request bodies, response parsing,
  and the auth quirks (ClickUp raw-token header, Notion version header) — 18 unit tests pass.
- **OAuth authorize URLs** build correctly for Notion + ClickUp with env credentials; clear
  errors when unconfigured.
- **Wiring**: exports, workflow connector map, agent action registry, seed row — app imports
  clean, no regressions.
- **Not testable here** (same as all OAuth): the live consent round-trip needs your registered
  apps — that's your one-time setup.

---

# UPDATE — Trello & WhatsApp are now implemented

Both are built, wired, and unit-tested (16 connector tests + route registration verified).
The live provider round-trips still need your registered app / credentials, same as every
OAuth integration.

## Trello (implemented)

**Auth model:** app-level API key (yours, in env) + per-user token (obtained via Trello's
authorize page; returned in the callback **URL fragment**). Not OAuth2.

**What was built:**
- `TrelloConnector` — `test_connection`, `get_boards`, `get_lists`, `create_card`, `get_cards`,
  `add_comment`, `update_card` (key+token sent as query params on every request).
- Backend: `GET /api/v1/integrations/trello/authorize-url` (returns Trello's authorize URL),
  `POST /api/v1/integrations/trello/connect` (validates the token via the connector, stores it
  encrypted).
- Frontend: Connect → redirect to Trello authorize → callback reads `#token=` fragment →
  stores the connection. Card + detail page added.

**Credentials you provide (once):** create a Trello **Power-Up / API key** at
`https://trello.com/power-ups/admin` (or `https://trello.com/app-key`). Set env vars:
```
TRELLO_API_KEY=...
TRELLO_API_SECRET=...   # (kept for completeness; the token flow uses the key)
```
**Return/redirect URL to allow:** `https://voicecon-fe.onrender.com/dashboard/integrations/oauth/callback`
**Scopes:** `read,write` (token expiration `never`).

**How a customer connects:** Integrations → Trello → **Connect** → approve on Trello → back →
**Connected**. Each user's own token is stored (encrypted) per connection.

**Test:** after connecting, `get_boards` → `get_lists(board_id)` → `create_card(list_id, name)`.

## WhatsApp (implemented — bring-your-own Cloud API credentials)

**Auth model:** each customer supplies **their own** WhatsApp Business **access token** +
**phone_number_id** (from their Meta WhatsApp Business setup). This gives true per-customer
WhatsApp **without** you needing Meta Embedded Signup / Tech-Provider approval — the customer
does their own Meta setup and pastes two values.

**What was built:**
- `WhatsAppConnector` — `test_connection`, `send_message` (24h window), `send_template`
  (first-contact) via `graph.facebook.com/v18.0/<phone_number_id>/messages`.
- Backend: `POST /api/v1/integrations/whatsapp/connect` (validates token+phone_number_id via
  the connector, stores both encrypted — token as the credential, phone_number_id as an
  encrypted additional field).
- Frontend: two-field connect form (Access Token + Phone Number ID). Card + detail page added.

**Credentials the customer provides (their own, per connection):**
- **Access Token** — a permanent System-User token from their Meta app (WhatsApp product).
- **Phone Number ID** — from Meta → WhatsApp → API Setup.

No platform-owner env vars are required for the bring-your-own model. (For a fully
click-to-connect Embedded Signup instead — where the customer doesn't handle Meta setup —
that's the larger Meta Tech-Provider project described earlier; this implementation is the
pragmatic, working per-customer path.)

**How a customer connects:** Integrations → WhatsApp → paste Access Token + Phone Number ID →
**Connect** (validated live against Meta) → **Connected**.

**Test:** after connecting, `send_template` for a first message (templates are required
outside the 24-hour window), or `send_message` to a number that has messaged the business.

## Env vars summary (final)
```
NOTION_CLIENT_ID / NOTION_CLIENT_SECRET      # OAuth app (you)
CLICKUP_CLIENT_ID / CLICKUP_CLIENT_SECRET    # OAuth app (you)
TRELLO_API_KEY / TRELLO_API_SECRET           # Trello power-up key (you)
# WhatsApp: no platform env — each customer brings their own token + phone_number_id
```
Shared OAuth redirect URI (Notion, ClickUp) and Trello return URL:
`https://voicecon-fe.onrender.com/dashboard/integrations/oauth/callback`
