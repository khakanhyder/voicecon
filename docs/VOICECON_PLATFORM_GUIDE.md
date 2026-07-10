# Voicecon Platform Guide

A page-by-page, feature-by-feature reference for the Voicecon dashboard: what each
feature does, why it exists, how to test it, and how to tell a real failure from an
unimplemented one.

Audience: a new team member who needs to understand the platform, test it, and
demonstrate it.

Every claim in this document was verified against the source, not against the UI.
Several pages render convincing interfaces over code that does nothing. Those are
marked explicitly.

---

## 0. Read this before you demo anything

The dashboard looks finished. Most of it is. But three of its most impressive-looking
surfaces are not wired to anything, and one of them — phone calls — is the feature the
product is named after.

**A live inbound or outbound phone call will not work today.** If you plan a demo around
"watch me call the agent," it will fail in front of your team lead. The reason is a
single stubbed function, explained in §1.

What *does* work end-to-end, and what you should build your demo on, is the **in-browser
agent test page**. It runs a complete speech → understanding → speech loop and is a
genuine demonstration of the platform's core value.

| Status | Meaning |
|---|---|
| ✅ **Works** | Verified real implementation, end-to-end |
| ⚠️ **Half-wired** | Real code exists but is bypassed or never called |
| ❌ **Stub** | Renders UI, does nothing |

| Feature | Status |
|---|---|
| Browser agent test (mic → STT → LLM → TTS) | ✅ Works |
| Agents CRUD, Calls, Phone Numbers, Workflows, Tools CRUD | ✅ Works |
| Analytics | ✅ Works (real SQL aggregation) |
| Phone number provisioning (Twilio) | ✅ Works (needs credentials) |
| Integrations / connectors | ✅ Works (needs OAuth) |
| Call recording playback | ✅ Works |
| API/webhook tool execution | ✅ Works |
| **Live phone calls (inbound + outbound)** | ❌ **Broken — see §1** |
| Telephony actions (transfer, hangup, SMS) | ⚠️ Returns intent, never executes |
| Knowledge base query tool | ⚠️ Search engine exists, tool doesn't call it |
| Twilio webhook signature validation | ⚠️ Real validator exists, endpoint bypasses it |
| Workflow loop sub-steps | ⚠️ Iterates, never runs the body |
| **Settings → API Keys** | ❌ **Stub — generates a fake key in the browser** |
| **Settings → Team invites** | ❌ **Stub — `console.log` only** |
| Web chat widget / text chat | ❌ Does not exist |

---

## 1. Architecture: why the browser test works and the phone doesn't

This is the single most important thing to understand about the codebase. **There are two
completely separate voice pipelines.** They share the STT, LLM, and TTS provider code but
nothing else. One is finished. One is not.

### Path A — Browser test (works)

```
Browser mic
  → WebSocket /api/v1/agents/{id}/stt   (backend proxies to Deepgram)
  → transcript back to browser
  → POST /api/v1/agents/{id}/respond    (backend runs the LLM)
  → browser speaks the reply
```

The backend proxies Deepgram, so **no API key is exposed to the browser** — good design.
There is also a Web Speech API fallback if Deepgram is unavailable
([test/page.tsx:456-459](../frontend/src/app/dashboard/agents/[id]/test/page.tsx#L456-L459)),
which means *the test page can appear to work even with a broken Deepgram key.* Watch the
`sttMode` indicator: if it says `webspeech`, you are testing the browser's recogniser,
not your platform.

### Path B — Real phone call (broken)

```
Twilio inbound call
  → POST /api/v1/telephony/twilio/voice/{agent_id}
  → returns TwiML pointing at
  → WebSocket /api/v1/voice/stream/{call_id}
  → voice_session.py
  → _transcribe_audio()  ←── returns None, always
  → nothing else ever runs
```

[`voice_session.py:348`](../backend/app/services/websocket/voice_session.py#L348) is
literally `return None`, with the real `transcribe_stream` call commented out directly
above it. Because `_process_audio_chunk` gates all downstream work on that return value,
the LLM is never invoked, no audio is ever generated, and the caller hears silence.

**Outbound calls are broken for the same reason.** `initiate_outbound_call`
([telephony.py:283](../backend/app/api/v1/endpoints/telephony.py#L283)) really does place
the call through Twilio — the phone genuinely rings — but the moment it connects, the
media stream lands in the same dead `voice_session`. This is the worst possible demo
failure mode: it looks like it's working right up until the person answers.

There is a **second, independent blocker** on the same path. `_send_audio_to_twilio`
([voice_session.py:624-628](../backend/app/services/websocket/voice_session.py#L624-L628))
base64-encodes whatever bytes it is handed and assumes they are 8kHz mulaw. ElevenLabs
returns MP3. So even after transcription is fixed, Twilio would receive MP3 bytes labelled
as mulaw and emit noise.

> **Consequence for planning:** fixing `_transcribe_audio()` alone does **not** restore
> phone calls. Inbound transcription and outbound audio conversion are two halves of one
> pipeline and neither is independently testable over a real line. Treat them as a single
> unit of work.

---

## 2. Page-by-page reference

### 2.1 Dashboard (`/dashboard`)

**Purpose.** Landing surface: greeting, four live counters (Active Agents, Total Calls,
Integrations, Workflows), quick actions, and a static "Platform features" panel.

**Why it exists.** Give a returning user an at-a-glance system state and a one-click path
into the most common task (create an agent).

**How it works.** The four counters are real queries against the user's organisation. The
"All systems operational" badge and the "Platform features" list on the right are static
marketing copy — they are not health checks and will read "operational" even if the
backend is on fire.

**Testing.** Load `/dashboard`. Create an agent in another tab, reload.

**Expected.** Active Agents increments. Counters match the corresponding list pages.

**Failure signs.** All counters stuck at `0` despite existing records; page renders but
numbers never populate.

**Likely causes.** Backend unreachable (check `NEXT_PUBLIC_API_URL`); expired JWT — the
counters fail silently rather than redirecting to login; the org has no records, which is
not a bug.

**Fix.** Open devtools → Network. A `401` means auth; a failed/CORS-blocked request means
`BACKEND_CORS_ORIGINS` or the API base URL is wrong.

> ⚠️ Note the fallback `http://localhost:8000` hardcoded in the frontend
> ([calls/[id]/page.tsx:258](../frontend/src/app/dashboard/calls/[id]/page.tsx#L258)).
> Per project convention this backend runs on **8001**. If `NEXT_PUBLIC_API_URL` is unset,
> recording playback will silently point at the wrong port.

---

### 2.2 Agents (`/dashboard/agents`)

The core object of the platform. An Agent bundles a system prompt, a first message, and a
provider triple (LLM / TTS+voice / STT).

Sub-pages: list, `new`, `[id]` (detail), `[id]/edit`, `[id]/builder`, `[id]/test`.

#### Feature: Agent CRUD ✅

**Purpose.** Define the personality, knowledge, and voice of a caller-facing assistant.

**Why developed.** Every downstream feature — calls, phone numbers, tools, workflows —
attaches to an agent. It is the root record.

**How it works.** `POST /api/v1/agents` persists `system_prompt`, `first_message`,
`llm_provider`, `tts_provider`, `voice_id`, `stt_provider`. Standard REST, real database
writes.

**Required config.** Authenticated session. No third-party keys needed to *create* an
agent — only to *run* one.

**Testing.**
1. Agents → **New Agent**.
2. Fill name, system prompt, first message. Pick providers.
3. Save. Return to the list. Open the record. Edit it. Save again.

**Expected.** Agent appears in the list; the detail page reflects your edits after reload;
Dashboard "Active Agents" increments.

**Failure signs.** Save spins forever; agent vanishes on reload; `422` on submit.

**Likely causes.** `422` = schema mismatch between the form and the Pydantic model (a
field renamed on one side only). Vanishing on reload = the write was never committed, or
you are reading a different organisation than you wrote to.

**Fix.** Compare the request body in devtools against `backend/app/schemas/agent.py`.

#### Feature: Browser Test Mode ✅ — **this is your demo**

**Purpose.** Hold a real spoken conversation with an agent in the browser, with no phone
number, no Twilio, and no telephony.

**Why developed.** Closing the loop on prompt-tuning without paying for a call, and — in
practice — the only working demonstration of the platform's core capability.

**How it works.** See §1, Path A. Mic audio streams to a backend WebSocket that proxies
Deepgram; transcripts return to the browser; the browser posts to `/respond` for the LLM
reply; the browser speaks it.

**Required config.** `DEEPGRAM_API_KEY` and `OPENAI_API_KEY` in the backend `.env`. Browser
mic permission. **Deepgram is not strictly required** — there is a Web Speech fallback,
which is exactly why you must verify which mode you're in.

**Testing.**
1. Open an agent → **Test**.
2. Grant mic permission.
3. **Confirm the STT mode indicator reads `deepgram`, not `webspeech`.** If it says
   `webspeech`, your Deepgram key is missing or rejected and you are testing Chrome, not
   Voicecon.
4. Speak. Watch the transcript. Listen for the reply.

**Expected.** Your speech appears as text within roughly a second; the agent replies in
character with its configured prompt; the first message plays on connect.

**Failure signs.** Transcript never appears; `{"type":"error","message":"Deepgram API key
not configured"}` on the socket; silence after a correct transcript.

**Likely causes.**
- No transcript + explicit socket error → `DEEPGRAM_API_KEY` unset
  ([agents.py:858](../backend/app/api/v1/endpoints/agents.py#L858)).
- Transcript fine, no reply → `/respond` failing; almost always a missing or
  rate-limited `OPENAI_API_KEY`.
- Socket closes `4001` → auth; the WS carries the JWT as a `?token=` query param, so an
  expired token fails here while REST calls still succeed.
- Nothing at all, no error → mic permission denied, or the page is served over plain
  HTTP on a non-localhost host (browsers block `getUserMedia` outside secure contexts).

**Fix.** Check the backend log for the Deepgram handshake. Verify the token in
`localStorage.access_token`. Serve over HTTPS or `localhost`.

---

### 2.3 Calls (`/dashboard/calls`)

**Purpose.** History of every call, with per-call detail, transcript, and recording
playback.

**Why developed.** Auditability and QA — reviewing what the agent actually said.

**How it works.** Real records, real aggregate tiles (Total, Completed, Active Now, Total
Minutes, Total Cost). The detail page `[id]` includes a working `<audio controls>` player
([calls/[id]/page.tsx:114](../frontend/src/app/dashboard/calls/[id]/page.tsx#L114)) gated
on `call.recording_url`.

**Testing.** You cannot generate a real call record today (§1). To exercise the page,
insert a `Call` row directly, or use the seed script. Then open its detail page.

**Expected.** Row appears; detail shows metadata and transcript; if `recording_url` is
set, the player renders and plays.

**Failure signs.** Player absent → `recording_url` is null, which is correct behaviour, not
a bug. Player present but silent → the URL is relative and `NEXT_PUBLIC_API_URL` is wrong
or unset (see the port-8000/8001 note in §2.1). Twilio recording URLs also require auth;
a bare `<audio src>` to a protected Twilio URL will 401.

---

### 2.4 Phone Numbers (`/dashboard/phone-numbers`)

Tabs: **My Numbers**, **Search & Purchase**.

**Purpose.** Search Twilio inventory, buy a number, attach it to an agent.

**Why developed.** A voice agent needs a PSTN address to receive calls.

**How it works.** Genuine Twilio API calls throughout. `search_phone_numbers`,
`provision_phone_number`, `release_phone_number`, and `update_phone_number_webhook` are all
real ([twilio_service.py](../backend/app/services/telephony/twilio_service.py)).
Provisioning also registers the inbound webhook.

**Required config.** `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`. A funded Twilio account —
purchase is a **real, billable action**.

**Testing.**
1. Search & Purchase → enter an area code → Search.
2. Purchase a number. Assign it to your test agent.

**Expected.** Real numbers list; purchase succeeds; the number appears under My Numbers and
in the Twilio console; Monthly Cost tile updates.

**Failure signs.** Empty search results; `TwilioRestException` in the backend log.

**Likely causes.** Missing/invalid credentials; trial account with insufficient balance;
the requested area code genuinely has no inventory; unverified account attempting purchase.

**Fix.** Confirm the credentials in the Twilio console. Note that provisioning succeeding
proves nothing about calls working — those are different code paths.

> **Do not conclude from a successful purchase that telephony works.** It doesn't (§1).

---

### 2.5 Tools (`/dashboard/tools`)

Filter tabs: **All**, **Phone Call Tools**, **Assistant Tools**, **Integration Tools**.

**Purpose.** Give agents capabilities: call an API, post to Slack, transfer a call, query
a knowledge base.

**Why developed.** A voice agent that can only talk is a demo; one that can act is a
product.

**How it works.** Tool definitions are passed to the LLM as function definitions
([voice_session.py:436-440](../backend/app/services/websocket/voice_session.py#L436-L440)).
When the model calls one, `function_executor.execute_global_tool` runs it.

**This is where the tool categories diverge sharply, and the UI does not tell you.**

| Tool type | Status | What actually happens |
|---|---|---|
| `api_request` | ✅ | Real `httpx` call, bearer/basic auth supported |
| `slack` webhook, `mcp`, `custom_tool` | ✅ | Really executes |
| `connected_integration` | ✅ | Dispatches to the real connector |
| `transfer_call`, `hang_up`, `send_sms`, `dtmf`, `leave_voicemail`, `sip_request` | ⚠️ | Returns `{"action": …, "requires_telephony": true}` and **nothing consumes it** |
| `query_knowledge_base` | ⚠️ | Returns `{"action": "query_kb"}` — no search runs |
| `google_sheets`, `google_calendar`, `gohighlevel` | ⚠️ | Returns a "configure OAuth" note |

#### The telephony-tool trap ⚠️

`function_executor.py:567` returns a *description of an intent*. The voice session
receives it and, at
[voice_session.py:554-557](../backend/app/services/websocket/voice_session.py#L554-L557),
simply JSON-dumps it back into the conversation as text for the LLM to read.

Nothing inspects `requires_telephony`. Nothing calls `twilio_service.transfer_call()`.

The observable result — *if the phone path worked at all* — would be an agent that says
**"I'm transferring you now"** and then does not transfer you. The LLM sees a
successful-looking tool result and narrates success. This is a silent failure by
construction: there is no error anywhere.

**Fix.** In `_handle_function_call`, branch on `result["result"].get("requires_telephony")`
and dispatch to the corresponding `twilio_service` method against the live `call_sid`.

#### The knowledge-base trap ⚠️

`query_knowledge_base` returns a stub dict. But a complete, working vector search already
exists at
[`rag_service.search()`](../backend/app/services/knowledge_base/rag_service.py#L448),
alongside a real chunker, embedder, and vector store.

The agent will confidently answer from the LLM's own training data, or hallucinate, while
appearing to consult your documents. **This is the most dangerous stub in the codebase**
because it produces plausible wrong answers rather than errors.

**Fix.** Call `rag_service.search()` from the tool branch and return the retrieved chunks.
Cheap — the hard part is already built.

---

### 2.6 Workflows (`/dashboard/workflows`)

**Purpose.** Visual automation: trigger → steps → actions.

**How it works.** `workflow_engine.py` + `step_handlers.py`. **Action, Condition, and
Transform steps execute real logic.** Triggers and the scheduler are real.

#### Loop steps ⚠️

`LoopStepHandler` ([step_handlers.py:405-437](../backend/app/services/workflows/step_handlers.py#L405-L437))
resolves the item list, respects `max_iterations`, sets `loop.item` and `loop.index` per
iteration — and then appends the item unchanged. The comment at line 427 admits sub-step
execution "would be handled by the main engine." It is not.

**Observable result.** The loop reports `{"success": true, "iterations": N}`. The step body
never ran. Another silent success.

**Testing.** Build a workflow with a loop whose body writes something observable (an HTTP
call to a request-bin). Run it.

**Expected if fixed.** N requests arrive. **Actual today.** Zero requests, and the run is
marked successful.

---

### 2.7 Integrations (`/dashboard/integrations`)

29 connectors across CRM, Calendar, Communication, Productivity, Phone Providers, Cloud
Storage, Analytics, Payment. Sub-pages: `[slug]`, `connected`, `oauth/callback`.

**Purpose.** Let agents read and write the systems a business already runs on.

**How it works.** HubSpot, Salesforce, Google Calendar, Slack, and SendGrid make **real HTTP
calls**. The connector code is genuine. What's missing is credentials, not logic. Cards are
marked `OAuth 2.0` or `API Key` accordingly.

**Required config.** Per-provider OAuth client ID/secret and a registered redirect URI
pointing at `/dashboard/integrations/oauth/callback`.

**Testing.** Connect → complete the provider consent screen → confirm the card moves to
Connected and the counter increments.

**Failure signs.** `redirect_uri_mismatch`; callback lands on an error page; card never
flips to Connected.

**Likely causes.** Redirect URI registered in the provider console does not byte-for-byte
match what the app sends (protocol, port, and trailing slash all matter). Missing client
secret. Insufficient scopes. Token stored but never refreshed → works for an hour, then
401s.

---

### 2.8 Analytics (`/dashboard/analytics`) ✅

**Purpose.** Call volume, duration, success rate, cost, sentiment, top agents, real-time
metrics. Date range picker and CSV export.

**How it works.** Genuinely real — `analytics_service.py` contains ~48 SQL aggregation
expressions against live call records. Nothing here is mocked.

**Testing.** With zero calls, every tile correctly reads `0` / `—` and Sentiment shows "No
sentiment data yet." That is success, not failure. To see non-zero values you need call
records (see §2.3).

**Failure signs.** Tiles show `0` while the Calls page lists calls; export produces an
empty file.

**Likely causes.** The date range excludes your records — the default window is the last 30
days and the screenshot shows `06/10/2026 – 07/10/2026`. Seeded records with old timestamps
will not appear. Check this before assuming the aggregation is broken.

---

### 2.9 Marketplace (`/dashboard/marketplace`)

Agent/workflow templates. Backed by real queries (19 `select(` calls). Browse and install
templates as starting points.

---

### 2.10 Settings (`/dashboard/settings`)

Sub-pages: `profile`, `billing`, `team`, `api-keys`.

- **Profile** — real.
- **Billing** — real Stripe integration (`stripe_service.py`), plan seeding, onboarding flow.

#### ❌ API Keys — **stub, and a dangerous one**

[`api-keys/page.tsx:30-34`](../frontend/src/app/dashboard/settings/api-keys/page.tsx#L30-L34):

```js
// TODO: Implement API call to create API key
const mockKey = `vcon_live_${Math.random().toString(36).substring(2, 15)}…`
```

The page generates a **random string in the browser**, displays it as `vcon_live_…`, and
never contacts the backend. Nothing is persisted. Nothing will ever authenticate with it.

The `vcon_live_` prefix makes it look like a production credential. A user will copy it into
their code and spend hours debugging 401s against an endpoint that never issued the key.
**Do not show this page in a demo.** Either hide it or label it clearly.

#### ❌ Team invites — stub

[`team/page.tsx:20-24`](../frontend/src/app/dashboard/settings/team/page.tsx#L20-L24):
`handleInvite` runs `console.log('Inviting:', email)` and clears the field. The form gives
positive feedback. No email is sent, no record is written.

---

### 2.11 Security: Twilio webhook signature validation ⚠️

Worth calling out because it is commonly misdiagnosed.

`TwilioService.validate_request()`
([twilio_service.py:85](../backend/app/services/telephony/twilio_service.py#L85)) is
**fully implemented** — it calls Twilio's real `RequestValidator.validate()`.

The gap is the endpoint wrapper
([telephony.py:30-55](../backend/app/api/v1/endpoints/telephony.py#L30-L55)), which reads
the `X-Twilio-Signature` header, rejects the request if it is *absent* (line 48), and then
returns `True` without verifying it:

```python
# In production, implement proper signature validation
return True  # Simplified for now
```

So the webhook is not wide open — it requires *a* signature — but it accepts **any** value.
Anyone who knows your webhook URL can forge a call event.

**Fix.** ~5 lines: `await request.form()` to get the POST vars, then call the existing
`twilio_service.validate_request(url, post_vars, signature)`. The validator is already
there; it just needs to be called.

---

## 3. Building the demo test agent

### 3.1 Honest scoping

I could not create this agent for you — it requires a running backend and an authenticated
session, neither of which I have from here. Below is the exact configuration to enter, and
what each field does.

More importantly: **scope the demo to Path A (browser test).** Do not promise a phone call.

### 3.2 Prerequisites

Backend `.env`:

```bash
OPENAI_API_KEY=sk-...        # required — LLM
DEEPGRAM_API_KEY=...         # required — else you silently fall back to Web Speech
ELEVENLABS_API_KEY=...       # optional for browser test
```

Twilio and Stripe keys are **not needed** for this demo.

Per project convention: backend on **8001**, frontend on **3002**. The screenshots show
`localhost:3000`, so confirm which ports you're actually on and set
`NEXT_PUBLIC_API_URL` to match — an unset value falls back to `:8000` and everything will
appear broken for a reason that has nothing to do with the code.

### 3.3 Create the agent

Agents → **New Agent**:

| Field | Value |
|---|---|
| Name | `Demo Receptionist` |
| System prompt | *(below)* |
| First message | `Thanks for calling Voicecon. How can I help you today?` |
| LLM provider | `openai` |
| STT provider | `deepgram` |
| TTS provider | `elevenlabs` (or browser TTS) |
| Voice ID | any configured voice |

System prompt:

```
You are a receptionist for Voicecon, a voice AI company.
Be warm, concise, and never invent facts about the company.
If you do not know something, say so plainly.
Keep replies under two sentences — this is a spoken conversation.
```

The two-sentence constraint matters. Left unconstrained, the LLM writes paragraphs, TTS
reads them aloud for forty seconds, and the demo dies of boredom.

### 3.4 Attach a tool that actually works

Skip `transfer_call` and `query_knowledge_base` — both are stubs (§2.5) and both fail
*silently*, which is worse on stage than failing loudly.

Use an **`api_request`** tool instead. It genuinely executes.

1. Tools → **New Tool** → type `api_request`.
2. Point it at a request-bin URL (e.g. `https://httpbin.org/post`), method `POST`.
3. Name it `log_customer_request`, describe it so the model knows when to call it.
4. Assign it to `Demo Receptionist`.

In the test conversation, say *"please log a request for a callback."* The model calls the
tool, the HTTP request really fires, and you can show the received payload. **That is a
genuine, defensible demonstration of agentic tool use.**

### 3.5 Run the demo

1. Agent → **Test**. Grant mic access.
2. **Verify the STT indicator reads `deepgram`.** If it reads `webspeech`, stop and fix the
   key — otherwise you are demoing Chrome's speech recogniser and calling it your platform.
3. The first message plays.
4. Speak. Transcript appears. Agent replies in character.
5. Ask it to log a callback. Show the tool firing.
6. Show Analytics and Calls to demonstrate the data layer.

### 3.6 What to say about phone calls

Do not quietly avoid the topic — your team lead will ask. Say this:

> "Telephony is provisioned and the Twilio integration is real — we can buy numbers and
> place calls today. The media pipeline has one unimplemented function, `_transcribe_audio`,
> plus an MP3-to-mulaw conversion on the return path. Together those are the remaining work
> to make a live call function. Everything upstream and downstream of them — STT, LLM, TTS,
> tools, analytics — is built and working, which is what you're seeing in this browser demo."

That is accurate, it is not a wall of excuses, and it correctly frames the remaining work
as one bounded task rather than a rewrite.

---

## 4. Failure triage

When something doesn't work, ask these in order.

**1. Is it a stub?** Check the table in §0 first. Do not debug `Settings → API Keys`; there
is nothing to debug. This is the single largest source of wasted time on this codebase,
because the stubs are the ones that *look* most finished.

**2. Silent success or loud failure?** Loud failure (500, exception, red toast) means real
code ran and hit a real problem — debug it normally. **Silent success** — the operation
reports success and nothing happens — is the signature of a stub. Loop steps, telephony
actions, and KB queries all fail this way.

**3. Environment.**
- Frontend can't reach backend → `NEXT_PUBLIC_API_URL`; remember 8001, not 8000.
- CORS errors → `BACKEND_CORS_ORIGINS`.
- `401` on REST → expired JWT.
- `4001` WS close → same JWT, passed as `?token=`. REST can work while WS fails.

**4. Third-party keys.** `OPENAI_API_KEY` (LLM), `DEEPGRAM_API_KEY` (STT — *fails over
silently*), `ELEVENLABS_API_KEY` (TTS), Twilio pair, Stripe. A missing Deepgram key does
not throw; it degrades. Always check the mode indicator.

**5. Database.** Migrations applied? Right organisation? Analytics honours the date range —
seeded records with stale timestamps will not appear, and that is not a bug.

**6. Third-party console.** OAuth redirect URIs must match byte-for-byte. Twilio purchases
need a funded account.

### Quick reference

| Symptom | Most likely cause |
|---|---|
| Caller hears silence | `_transcribe_audio()` returns `None` (§1) |
| Caller hears noise/static | MP3 sent where mulaw expected (§1) |
| Agent says "transferring you" then doesn't | `requires_telephony` never consumed (§2.5) |
| Agent answers from thin air, ignores documents | `query_knowledge_base` stub (§2.5) |
| Loop reports success, body never ran | `LoopStepHandler` (§2.6) |
| Generated API key doesn't authenticate | The key is fake (§2.10) |
| Team invite sends no email | `console.log` only (§2.10) |
| Test page works but transcript feels off | You're on `webspeech`, not Deepgram (§2.2) |
| Analytics zero but calls exist | Date range excludes them (§2.8) |
| Recording player silent | `NEXT_PUBLIC_API_URL` unset → wrong port (§2.3) |

---

## 5. Recommended fix order

1. **`_transcribe_audio()` + MP3→mulaw conversion, as one change.** Unblocks all phone
   calls. Neither half is independently testable. Note that `_transcribe_audio` is invoked
   per ~20ms chunk while `stt_service.transcribe_stream` is a *streaming* interface —
   naively uncommenting the existing lines opens a new Deepgram socket per 160-byte chunk.
   The surrounding call structure assumes batch semantics and must change too. This is more
   than deleting a `return None`.
2. **Telephony tool execution.** Consume `requires_telephony`, dispatch to `twilio_service`.
3. **`query_knowledge_base` → `rag_service.search()`.** Cheap; the search engine exists.
4. **Twilio signature validation.** ~5 lines; the validator exists.
5. **Label or hide the API Keys and Team stubs.** They actively mislead users.
6. Workflow loop sub-steps.
7. Web chat widget (genuine greenfield; no backend chat endpoint exists).
