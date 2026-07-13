# Voicecon — Status Report

What has been fixed this session, what remains broken, and what is missing. Every item
was verified against the running code, not the UI. Grounded in the fixes made across the
session.

Legend:
- ✅ **Fixed & verified** — repaired and tested working end-to-end (no external creds needed)
- 🟡 **Fixed, gated** — code is complete and unit-tested, but a live end-to-end test needs
  external credentials (Twilio / paid ElevenLabs)
- ❌ **Still broken** — not yet fixed
- ⛔ **Missing** — never built

---

## Part 1 — Fixed this session

### 1.1 ✅ Create Tool → "Network Error"

**What it is.** Creating a tool (Tools → New Tool → Create).

**Why it failed.** The `ToolResponse` schema declared `id`, `user_id`, `organization_id`
as `str`, but the database returns `UUID` objects. Pydantic v2 refused to coerce them, so
the endpoint raised a `ResponseValidationError` → HTTP 500. FastAPI's CORS middleware does
not attach CORS headers to unhandled 500s, so the browser blocked the response and axios
reported it as the misleading "Network Error". The tool was actually being created in the
database each time — only the response failed.

**How it was fixed.** Changed those fields to `UUID` in `schemas/tool.py` (and the same in
`AgentToolAssignmentResponse`). Deleted the orphaned rows from the failed attempts.

**How to verify.** Create a tool → it returns 201 and appears in the list.

### 1.2 ✅ Live Test Call stuck / typed messages did nothing

**What it is.** The "Live Test Call" panel on the agent detail page.

**Why it failed.** Two bugs. (a) When Deepgram errored (bad/missing key), the socket
handler closed it *without* marking Deepgram unavailable, so the reconnect logic looped
forever. (b) The call state got stuck on "speaking", and `sendText` refuses to send while
speaking — so every typed message was silently dropped, with no error shown.

**How it was fixed.** The error handler now marks Deepgram unavailable and surfaces the
message as a toast instead of looping; the Web Speech fallback no longer leaves the call
stuck, dropping to text-only mode so typing still works.

**How to verify.** Start a call; if STT is unavailable you now see a toast and can still
type and get replies.

### 1.3 ✅ Agent saved with empty provider config (silent greeting / TTS 500)

**Why it failed.** `PATCH /agents/{id}` accepts provider settings only as **nested**
objects (`llm`, `voice`, `stt`). Flat fields like `tts_provider` are silently dropped —
the request returns 200 and changes nothing. The demo agent ended up with empty
`tts_provider`/`voice_id`/`llm_model`/`stt_model`, so `/speak` returned
`500 Unsupported TTS provider: ""`.

**How it was fixed.** Re-saved the agent with the correct nested shape (openai/gpt-4o-mini,
elevenlabs, deepgram/nova-2). **This is a UI trap to keep in mind**, not a code fix — after
editing an agent, reload to confirm the values persisted.

### 1.4 ✅ OpenRouter/OpenAI LLM key not working

**What it is.** The LLM behind all conversation.

**Why it failed.** The OpenAI client was built as `AsyncOpenAI(api_key=...)` with no
`base_url`, so it always hit `api.openai.com`. An OpenRouter key (`sk-or-v1-…`) is
meaningless there → 401, and the agent replied "I'm having a technical issue."

**How it was fixed.** Added an `OPENAI_BASE_URL` setting (`config.py`) passed through to the
client (`openai_llm.py`). Set it to OpenRouter in `.env` for testing. **Design note:** when
unset it defaults to `api.openai.com`, so switching to a real OpenAI key is config-only —
set the real key and blank `OPENAI_BASE_URL`. No code change.

**How to verify.** Conversation in the browser test returns real replies.

### 1.5 ✅ Integrations — connectors list + connection create (500s)

**Why it failed.** Two bugs blocked the whole integrations area: (a) `GET /connectors`
returned 500 from the same UUID-as-`str` schema bug as tools — invisible on the page
because the 29 cards are a hardcoded frontend list, but it made the real connector IDs
(needed to create any connection) unreachable. (b) Creating a connection read
`current_user.organization_id`, which does not exist on the `User` model (org membership
lives in `organization_members`) → 500.

**How it was fixed.** Changed the UUID fields in `schemas/integration.py`; added an
`_resolve_org_id` helper in the integrations endpoint. `/connectors` now returns 200 with
all 29; connection creation gets past the org lookup.

**Note.** This unblocked the *endpoints*, but API-key connections still can't complete —
see §2.3.

### 1.6 🟡 Phone call voice pipeline (STT + audio format)

**What it is.** The core "AI answers a real phone call" feature (Phase 3).

**Why it failed.** `voice_session._transcribe_audio()` was a stub that always returned
`None`, so the caller's audio was decoded and then thrown away — the LLM/TTS were never
reached. Separately, `_send_audio_to_twilio()` sent ElevenLabs MP3 bytes labelled as
mulaw, which Twilio can't play (a TODO for format conversion).

**How it was fixed.** Replaced the stub with a **persistent Deepgram streaming connection**
per call, configured for `encoding=mulaw&sample_rate=8000` (Twilio's native format — no
inbound conversion needed). For output, the code now requests `output_format=ulaw_8000`
from ElevenLabs, which returns Twilio-ready audio directly — **eliminating the MP3
conversion problem entirely** — and reframes it into 160-byte frames. Also fixed a
pre-existing bug where the welcome greeting was sent before Twilio's stream existed.

**How it was tested.** I streamed a real speech recording (converted to 8kHz mulaw, exactly
like Twilio) to Deepgram through the new code — it transcribed correctly. Outbound framing,
welcome timing, and teardown are unit-tested (11 tests pass). **Gated:** a real phone call
needs Twilio credentials + working ElevenLabs (see §2.1, §2.2).

### 1.7 🟡 Twilio webhook signature validation

**Why it failed.** The webhook validator was `return True` — it accepted any request,
letting anyone who knew the URL forge call events.

**How it was fixed.** Implemented real validation using Twilio's `RequestValidator`, wired
into the inbound and status webhooks. Guarded so it auto-skips when no auth token is
configured (dev is unaffected) and can be toggled with `TWILIO_VALIDATE_WEBHOOKS`.

**How it was tested.** 5 cases pass: valid accepted, tampered rejected, missing rejected,
no-token auto-skip, disabled-allows.

### 1.8 🟡 Telephony tool execution (transfer / hang-up / SMS / DTMF / voicemail)

**What it is.** An agent taking phone actions mid-call (Phase 4).

**Why it failed.** These tools returned `{"requires_telephony": true}` and **nothing
consumed it** — the agent would *say* "transferring you" and do nothing. Worse, the Twilio
service didn't even have the methods (`transfer_call`, `hang_up`, `send_sms`, …).

**How it was fixed.** Implemented the real methods on the Twilio service (using the Twilio
REST API), and wired the voice session to detect `requires_telephony` and execute against
the live call. Call-control actions are deferred until *after* the agent speaks its
confirmation (so "connecting you now" isn't cut off), while SMS sends immediately.
Direction-aware number resolution handles `{{caller_number}}`.

**How it was tested.** 22 dispatch/ordering tests + 8 Twilio-API-format tests pass.
**Gated:** needs Twilio credentials for a live transfer/SMS.

### 1.9 ✅ Function calling in the browser conversation (`/respond`)

**What it is.** Tools actually firing while you talk to the agent in the browser (Phase 1).

**Why it failed.** The `/respond` endpoint had **no function-calling loop** — it was a
plain LLM chat. Tools only ran in isolation (the Test button) or on the dead phone path.

**How it was fixed.** Added a tool-resolution loop to `/respond`: it loads the agent's
tools, and when the model calls one, executes it, feeds the result back, and repeats until
a final answer, then streams that answer through the existing sentence/TTS pipeline.
Agents with no tools keep the original streaming path unchanged.

**A deeper bug this uncovered.** OpenRouter (and modern OpenAI) reject the deprecated
`functions`/`function_call` API the provider used — so tool calling was broken on *both*
the browser and phone paths. I migrated the provider to the current `tools`/`tool_choice`
API, translating legacy message shapes on the wire so every caller keeps working. Verified
the exact request format matches OpenAI's tool-calling spec.

**How to verify.** Ask the agent "What's the price of Bitcoin?" → it calls the
`get_crypto_price` tool (live CoinGecko) and answers with the real price. Verified working:
returned "The current price of Bitcoin is 62,894 dollars."

### 1.10 ✅ ElevenLabs deprecated default model + misleading auth error

**Why it failed.** The provider defaulted to `eleven_monolingual_v1`, which ElevenLabs has
deprecated and rejects. Separately, every ElevenLabs error was flattened to "Invalid API
key", hiding the real cause (permissions / plan).

**How it was fixed.** Changed the default to `eleven_turbo_v2_5`; the 401 handler now
surfaces the provider's actual message.

---

## Part 2 — Still broken / needs work

### 2.1 🟡 Live phone call — gated on Twilio credentials

The pipeline (§1.6–1.8) is built and unit-tested, but **no real call can be placed** until
`TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` are real (currently placeholders) and a number is
provisioned. **Fix:** add real Twilio credentials, provision a number, assign it to the
agent. Outbound also rings before it can be tested, so test inbound first.

### 2.2 ❌ ElevenLabs voice output — free-tier / plan block

**Why it fails.** The account is free tier and the configured voice (Rachel,
`21m00Tcm4TlvDq8ikWAM`) is a shared *library* voice. Free API keys return
`402 paid_plan_required` for library voices — no key permission fixes this.

**Effect.** Blocks spoken output everywhere: the browser test greeting is silent, and phone
calls would have no agent audio. Text/transcript still works.

**How to fix.** Either upgrade the ElevenLabs plan, or add a voice your account *owns* (My
Voices) and point the agent at it, or use browser speech synthesis for the demo. STT
(Deepgram) is unaffected and works.

### 2.3 ❌ Integrations — API-key connections can't store credentials (Phase 2)

**Why it fails.** The manager writes/reads `IntegrationConnection.api_key_encrypted`, but
that column does not exist on the model or in the database → every API-key connect returns
`400 'api_key_encrypted' is an invalid keyword argument`.

**How to fix.** Add the `api_key_encrypted` column (model + migration). Small, contained;
unblocks all API-key connectors (Stripe, Langfuse, SendGrid, …) at once.

### 2.4 ❌ Integrations — OAuth connectors can't start (Phase 9)

**Why it fails.** No OAuth `client_id`/`client_secret`/`authorize_url` is seeded for any of
the 14 OAuth connectors, so the flow raises "Missing OAuth2 configuration". The on-screen
message telling you to set `GOOGLE_CALENDAR_CLIENT_ID` **env vars** is misleading — the
backend reads these from the connector's `auth_config` in the **database**, not env.

**How to fix.** Register an OAuth app with each provider (Google, HubSpot, Slack…), then
seed the credentials into that connector's `auth_config`. Per-provider external setup.

### 2.5 ❌ Knowledge base vector search (Phase 6)

**Why it fails.** The `query_knowledge_base` tool returns a stub dict — no search runs — so
the agent answers from the LLM's own training data while *appearing* to consult your
documents (plausible wrong answers, no error). A complete `rag_service.search()` exists and
is simply not called. Additionally, the embeddings code uses the bare `openai` module,
which bypasses the `OPENAI_BASE_URL` override and will fail with an OpenRouter key.

**How to fix.** Call `rag_service.search()` from the tool branch, and route the embeddings
client through the same `base_url`.

### 2.6 ❌ Workflow loop steps don't execute their body (Phase 7)

**Why it fails.** `LoopStepHandler` iterates, sets loop variables, and appends the item
unchanged — but never runs the sub-steps. It reports `{"success": true}` regardless, a
silent no-op.

**How to fix.** Make the loop recursively execute its sub-steps per iteration.
(Action/Condition/Transform/Delay steps already work.)

### 2.7 ❌ Settings stubs — API Keys & Team (Phase 8)

**Why they fail.** *API Keys* generates a fake `vcon_live_…` key in the browser and never
calls the backend — it authenticates nothing. *Team invites* runs `console.log` only — no
email, no record. Both show fake success.

**How to fix.** Implement real endpoints, or hide the pages until they exist.

### 2.8 ⚠️ Model name for real OpenAI

The no-tool browser path forces `gpt-5.4-nano` ([agents.py:583-584](../backend/app/api/v1/endpoints/agents.py#L583-L584)).
OpenRouter accepts it; confirm your OpenAI account can serve that exact name, or change the
fallback to a known model (e.g. `gpt-4o-mini`). The tool path already uses the agent's
configured model, so it's safe.

---

## Part 3 — Missing (never built)

| Feature | Notes |
|---|---|
| ⛔ Web chat widget (Phase 10) | Embeddable text-chat snippet + public `/chat` endpoint. Would reuse the Phase 1 function-calling loop. |
| ⛔ Outbound call scheduler / campaign dialer | No bulk/scheduled outbound dialing. |
| ⛔ Real-time call monitoring / listen-in | No live view of an in-progress call. |

---

## Part 4 — What works right now, no credentials needed

- **Browser conversation with real tool use** — ask for Bitcoin price / weather / log a
  callback; the agent calls live APIs and answers. (Voice output needs ElevenLabs; text
  works.)
- **Tools** — create, assign, and Test (executes real HTTP).
- **Agents, Calls, Phone Numbers, Analytics, Marketplace** — CRUD and real data.
- **Integrations catalog + connector list** — 29 connectors listed (connecting needs §2.3/§2.4).

## Part 5 — Suggested next order

1. **Phase 2** — add `api_key_encrypted` column → connect Stripe/Langfuse with a real key
   (contained, high value, no external OAuth setup).
2. **ElevenLabs** — resolve the plan/voice block so voice output works everywhere.
3. **Twilio credentials** — unlock the (already-built) live phone call.
4. Phase 6 (KB search), Phase 7 (loops), Phase 8 (settings), Phase 9 (OAuth), Phase 10 (widget).
