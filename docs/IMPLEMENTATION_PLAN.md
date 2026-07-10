# Voicecon — Incremental Implementation Plan

A phased plan to close the gaps identified in the state assessment. Designed for a
one-task-at-a-time workflow: implement → test → fix → verify no regression → move on.

Every file path and behaviour referenced here was verified against the codebase. Companion
to [VOICECON_PLATFORM_GUIDE.md](./VOICECON_PLATFORM_GUIDE.md),
[AGENT_BUILD_AND_TEST.md](./AGENT_BUILD_AND_TEST.md), and
[INTEGRATIONS_GUIDE.md](./INTEGRATIONS_GUIDE.md).

---

## Guiding principles

1. **One phase at a time.** Do not start a phase until the previous one passes its test and
   its regression check.
2. **Every phase is independently testable.** No phase requires a later phase to demonstrate
   value.
3. **Regression gate.** After each phase, re-run the Phase 0 smoke test. If anything that
   worked before now fails, stop and fix before proceeding.
4. **Branch per phase.** Each phase on its own git branch, merged only after it passes. This
   makes rollback trivial and pinpoints the source of any issue.
5. **Order chosen for safety, not just value.** The two highest-value items (function-calling,
   voice pipeline) are separated by a small, low-risk phase so you build confidence in the
   test loop before the risky telephony work.

### Why this order

| # | Phase | Value | Risk | External deps | Depends on |
|---|---|---|---|---|---|
| 1 | Function-calling loop in `/respond` | High | Low | none (LLM already works) | — |
| 2 | Integrations `api_key_encrypted` column | Medium | Low | a real API key to test | — |
| 3 | Voice pipeline (STT + audio convert) | High | High | Twilio creds + funded number | — |
| 4 | Telephony tool execution | Medium | Medium | Twilio | Phase 3 |
| 5 | Twilio signature validation | Low (security) | Low | Twilio | Phase 3 |
| 6 | KB vector search wiring | Medium | Medium | embeddings key | Phase 1 |
| 7 | Workflow loop body execution | Low | Low | none | — |
| 8 | Settings stubs (API Keys, Team) | Low | Low | none | — |
| 9 | OAuth integration seeding | Medium | Low | per-provider OAuth apps | Phase 2 pattern |
| 10 | Web chat widget | High | High | none | Phase 1 |

**Phase 1 is the recommended first task**: it is self-contained (one endpoint), needs no
telephony or external setup, is testable in the browser in minutes, and turns the already-
working conversation demo into a genuinely agentic one. It also has a working reference
implementation inside the same repo (see Phase 1).

> **Alternative first pick.** If the *only* goal is a live phone call for a specific demo,
> jump to Phase 3 — but it is the hardest, riskiest phase and needs paid Twilio setup, so
> it's a worse place to start building confidence.

---

## Phase 0 — Baseline & test harness (do this before any change)

**Goal:** capture what currently works so regressions are detectable.

**Steps:**
1. Confirm backend runs on 8001, frontend on 3002 (or 3000 per current setup), DB reachable.
2. Record a **smoke-test checklist** of currently-green behaviour. Re-run it after every phase:
   - Login works; dashboard counters load.
   - Agents: create, edit, list.
   - Tools: create a tool, run its **Test** button → 200.
   - Live Test Call: type a message → agent replies (LLM via OpenRouter).
   - Calls list, Analytics, Phone Numbers list all return without error.
   - `GET /api/v1/integrations/connectors` → 200 (29 rows).
3. Note current env state: `OPENAI_API_KEY` (OpenRouter, working), `DEEPGRAM_API_KEY`
   (working), `ELEVENLABS_API_KEY` (blocked — free tier), `OPENAI_BASE_URL` set to OpenRouter,
   Twilio creds are placeholders.

**Pass criteria:** every item above behaves as noted. This is your regression baseline.

---

## Phase 1 — Function-calling loop in `/respond`

**Goal:** make the agent actually call its assigned tools during a conversation.

**Why:** `POST /api/v1/agents/{id}/respond` (behind the Live Test Call and `/test` page) has
**no function-calling loop** — verified, zero tool references in the handler. Tools only run
in isolation today. This is the highest-value, lowest-risk unblock and needs no telephony.

**Key de-risk:** the loop is *already implemented* in
[voice_session.py](../backend/app/services/websocket/voice_session.py) — it builds tool
definitions ([436-440](../backend/app/services/websocket/voice_session.py#L436-L440)) and
executes them ([539-553](../backend/app/services/websocket/voice_session.py#L539-L553)) via
`function_executor`. Phase 1 is essentially porting that proven logic into `/respond`.

**Files:**
- `backend/app/api/v1/endpoints/agents.py` — the `agent_respond` handler (~line 522).
- `backend/app/services/function_executor.py` — reuse existing `get_agent_functions`,
  `get_agent_assigned_tools`, `get_function_definition`, `get_tool_function_definition`,
  `execute_function`, `execute_global_tool`, `format_for_llm`. **No changes needed here** —
  just call them.

**Implementation steps:**
1. In `agent_respond`, load the agent's assigned functions and global tools (mirror
   `voice_session._initialize` / lines 131-136).
2. Build the OpenAI `tools` parameter from those definitions.
3. Run the completion loop:
   - Call the LLM with `tools`.
   - If the model returns `tool_calls`, execute each via `function_executor`, append the
     results as `role: "tool"` messages, and call the LLM again.
   - Repeat until the model returns a normal message (cap at ~5 iterations to avoid loops).
   - Stream the final message as the existing `sentence`/`done` SSE events.
4. **Streaming caveat:** OpenAI streams tool calls as deltas that must be accumulated. Two
   options — (a) do a **non-streaming** first pass to detect/execute tool calls, then stream
   only the final answer (simpler, recommended for v1); or (b) accumulate tool-call deltas
   from the stream (lower latency, more code). Start with (a).
5. Emit a lightweight `tool_call` SSE event (name + status) so the UI can optionally show
   "looking that up…".

**Test process:**
1. Your agent `Demo Receptionist` already has `get_weather`, `get_crypto_price`, and
   `log_callback_request` assigned (created earlier this session).
2. Live Test Call → type: *"What's the current price of Bitcoin?"*
3. Watch the backend log for the tool execution and the outbound HTTP call.
4. Type: *"Please log a callback for John at 555-1234"* → check the postman-echo tool received
   the parameters.

**Expected result:** the agent answers with a **real** value ("Bitcoin is about $X") fetched
live, not an "I can't access live data" deflection. Tool execution appears in logs.

**Pass criteria:** at least one tool fires and its real result reaches the reply.

**Regression checks:** plain conversation with no tool need still streams normally;
`end_call_phrases` still end the call; an agent with zero tools still works (empty `tools`
array must not break the call).

**Rollback:** revert `agents.py`; nothing else touched.

---

## Phase 2 — Integrations `api_key_encrypted` column

**Goal:** let API-key connectors (Langfuse, Stripe, SendGrid, …) actually store a credential
and connect.

**Why:** the manager writes and reads `IntegrationConnection.api_key_encrypted`
([integration_manager.py:291](../backend/app/services/integrations/integration_manager.py#L291),
[connector_base.py:129](../backend/app/services/integrations/connector_base.py#L129)) but that
column does not exist on the model or in the DB. Result: every API-key connect returns
`400 'api_key_encrypted' is an invalid keyword argument`. Contained, independent, testable.

**Files:**
- `backend/app/models/integration.py` — add the column to `IntegrationConnection`.
- A new Alembic migration under `backend/alembic/versions/`.
- No manager changes needed — the code already expects the column.

**Implementation steps:**
1. Add `api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text)` beside the existing
   `access_token_encrypted` / `auth_data_encrypted` columns.
2. Generate and apply a migration (`alembic revision --autogenerate` then `upgrade head`), or
   for dev add the column with a reviewed SQL `ALTER TABLE`.
3. Confirm `connector_base` reads it via `credential_manager.decrypt`.

**Test process:**
1. Get a real API key for a simple service — **Langfuse** or **Stripe** (test key) are easiest.
2. Integrations → the connector → Connect → paste the key. Or `POST /integrations/connections`
   with `api_key_auth`.
3. Hit **Test** on the new connection.

**Expected result:** connection is created (no 400), and Test returns `success: true` /
HTTP 200 against the provider's `test_endpoint`.

**Pass criteria:** a real key connects and tests green; the key is stored encrypted (verify the
DB column holds ciphertext, not plaintext).

**Regression checks:** OAuth connection path (uses `access_token_encrypted`) unaffected;
`GET /connectors` still 200; existing connections still list.

**Rollback:** down-migration drops the column; revert model.

> Note the §4 caveat in the Integrations guide: a green Test proves auth, not that a later
> *action* works, and storage/webhook connectors (S3, Zapier, Make) won't pass a bearer-GET
> test regardless.

---

## Phase 3 — Voice pipeline: `_transcribe_audio()` + MP3→mulaw (ONE phase)

**Goal:** a real phone call where the agent hears the caller and the caller hears intelligible
speech.

**Why one phase:** fixing transcription alone yields a call that transcribes, thinks, and then
sends **MP3 bytes labelled as mulaw** to Twilio — the caller hears noise, not silence. Inbound
transcription and outbound audio conversion are two halves of one pipeline; neither is
independently testable over a real line. Treat them as a single deliverable.

**Prereqs:** real Twilio credentials, a funded/provisioned number, Deepgram working (it is),
and TTS — either fix ElevenLabs (owned voice + paid tier) or temporarily use a provider whose
output you can convert. **Do Phases 1–2 first** so your test loop is proven before this risky
work.

**Files:**
- `backend/app/services/websocket/voice_session.py` — `_transcribe_audio` (~348) and
  `_send_audio_to_twilio` (~614).
- Possibly `backend/app/services/voice/stt_service.py` (streaming interface) and
  `audio_utils.py` (resample/encode helpers already exist).

**Implementation steps:**
1. **Inbound STT.** Replace `return None` with real Deepgram streaming. **Critical structural
   point:** `_transcribe_audio` is called per ~20 ms / 160-byte chunk, but
   `stt_service.transcribe_stream` is a *streaming* interface. Do **not** open a new Deepgram
   socket per chunk. Instead, open **one persistent Deepgram stream per call session**, feed
   the audio buffer into it, and receive transcripts asynchronously (via a callback or queue)
   rather than returning a string per chunk. This is a restructure of the audio loop, not a
   one-line edit.
2. **Outbound audio conversion.** Before `_send_audio_to_twilio`, convert TTS output to
   **8 kHz mulaw**. Two routes: (a) request PCM/linear16 from the TTS provider and encode to
   mulaw with `audioop.lin2ulaw` + resample to 8 kHz; or (b) decode ElevenLabs MP3 (needs a
   decoder like ffmpeg/pydub) then encode. Route (a) is cleaner if the provider can emit PCM.
3. Handle barge-in/interruption and mark events already scaffolded in `voice_session`.

**Test process:**
1. Set real Twilio creds; provision a number; assign it to the agent.
2. **Inbound:** call the number, speak. **Outbound:** `POST /api/v1/calls` and answer.
3. Verify two-way audio: the agent responds to what you say, and you hear clear speech.
4. Check a Call record is created, `transcript` populated, recording saved and playable in the
   call detail page.

**Expected result:** a real, two-way spoken conversation on a phone line.

**Pass criteria:** you speak → agent responds relevantly → you hear intelligible (not garbled)
audio; call record + transcript + recording present.

**Regression checks:** the browser Live Test Call (separate `/respond` path) still works;
Phase 1 tool calls still fire (ideally test a tool over the phone too).

**Rollback:** revert `voice_session.py`; browser path is independent and unaffected.

---

## Phase 4 — Telephony tool execution

**Goal:** `transfer_call`, `hang_up`, `send_sms`, `dtmf`, `leave_voicemail` actually act on
the live call.

**Why & dependency:** these return `{"requires_telephony": true}`
([function_executor.py:567](../backend/app/services/function_executor.py#L567)) and nothing
consumes it — the agent *says* "transferring you" and does nothing. Only meaningful once
Phase 3 makes the voice session live.

**Files:** `backend/app/services/websocket/voice_session.py` — the function-call handler
(~539-557); `twilio_service.py` already has `transfer_call` / `hang_up` / `send_sms`.

**Implementation steps:**
1. In the handler, after `execute_global_tool`, check
   `result["result"].get("requires_telephony")`.
2. Branch on the action and call the matching `twilio_service` method with the **live**
   `call_sid` / stream context.
3. Return a natural confirmation to the LLM only after the action actually succeeds.

**Test process:** on a live call (Phase 3), ask the agent to transfer to another number, or to
hang up, or to text you. Verify Twilio actually performs it.

**Pass criteria:** transfer connects the caller to the target; hang_up ends the call; SMS
arrives.

**Regression checks:** non-telephony tools (Phase 1) still work; a call with no tool use is
unaffected.

---

## Phase 5 — Twilio webhook signature validation

**Goal:** reject forged webhook requests.

**Why:** the endpoint wrapper does `return True`
([telephony.py:55](../backend/app/api/v1/endpoints/telephony.py#L55)). The real validator
already exists (`twilio_service.validate_request`) — it just isn't called. Grouped here because
it's only meaningfully testable once real Twilio webhooks flow (Phase 3).

**Files:** `backend/app/api/v1/endpoints/telephony.py` — `validate_twilio_request`.

**Implementation steps:** read the raw form body (`await request.form()`), build the exact
public URL Twilio called, and call
`twilio_service.validate_request(url, post_vars, signature)`; return its boolean and reject on
false.

**Test process:** a real Twilio call passes; a hand-forged request (wrong signature) is
rejected with 403. Use Twilio's `RequestValidator` to generate a valid test signature.

**Pass criteria:** valid Twilio requests pass, forged/absent signatures are rejected.

**Regression checks:** real inbound/outbound calls (Phase 3) still connect.

---

## Phase 6 — Knowledge base vector search

**Goal:** `query_knowledge_base` returns real retrieved chunks instead of a stub.

**Why & dependency:** the tool returns `{"action": "query_kb"}`
([function_executor.py:573](../backend/app/services/function_executor.py#L573)), but a complete
search already exists at
[rag_service.search()](../backend/app/services/knowledge_base/rag_service.py#L448). Only useful
after Phase 1 (so the tool can fire in conversation).

**Embeddings wrinkle to resolve in this phase:** `rag_service` uses the bare `openai` module
with `openai.api_key` ([rag_service.py:163](../backend/app/services/knowledge_base/rag_service.py#L163)),
which bypasses the `OPENAI_BASE_URL` override and always calls `api.openai.com`. With an
OpenRouter key, embeddings will 401. Fix: route the embeddings client through the same
`base_url` (or supply a real OpenAI key for embeddings).

**Files:** `function_executor.py` (query branch → call `rag_service.search`), `rag_service.py`
(embeddings client).

**Test process:** create a knowledge base, upload a document with a distinctive fact, assign it
to the agent, then ask a question answerable only from that document (Phase 1 must be done so
the tool fires). Verify the answer uses the retrieved content.

**Pass criteria:** the agent answers from the document, and retrieval is visible in logs.

**Regression checks:** agents without a KB still work; embeddings/ingestion path unaffected for
existing docs.

---

## Phase 7 — Workflow loop body execution

**Goal:** loop steps run their sub-steps per iteration.

**Why:** `LoopStepHandler`
([step_handlers.py:427-429](../backend/app/services/workflows/step_handlers.py#L427-L429))
sets loop variables and appends the item unchanged, with a comment admitting the body isn't
executed. Reports `{"success": true}` regardless — a silent no-op.

**Files:** `backend/app/services/workflows/step_handlers.py` — `LoopStepHandler`; the engine's
step-dispatch so the loop can invoke sub-steps recursively.

**Test process:** build a workflow with a loop whose body performs an observable Action (e.g.
an HTTP call to a request bin) over a 3-item list; run it; confirm **3** calls arrive.

**Pass criteria:** N iterations produce N real sub-step executions.

**Regression checks:** Action/Condition/Transform/Delay steps still work.

---

## Phase 8 — Settings stubs (API Keys, Team)

**Goal:** stop the two stub pages from misleading users.

**Why:** Settings → API Keys generates a fake `vcon_live_…` key in the browser and never calls
the backend ([api-keys/page.tsx:30-34](../frontend/src/app/dashboard/settings/api-keys/page.tsx#L30-L34));
Settings → Team invites is `console.log` only
([team/page.tsx:20-24](../frontend/src/app/dashboard/settings/team/page.tsx#L20-L24)).

**Decision to make:** either **implement** real endpoints (API key issuance + persistence;
team invite email + membership rows) or **hide/disable** the pages with a "coming soon" state.
Hiding is minutes; implementing is a small feature each. Recommend hiding now, implementing
later.

**Test process (if implementing):** create a key, use it to authenticate a request; invite a
teammate, confirm the membership row and email.

**Pass criteria:** no page presents fake success. If implemented, the generated key
authenticates and the invite creates a real record.

---

## Phase 9 — OAuth integration seeding

**Goal:** let OAuth connectors (HubSpot, Google Calendar, Slack, …) connect.

**Why:** no `client_id`/`authorize_url`/`token_url`/`client_secret` is seeded in any OAuth
connector's `auth_config` ([integration_manager.py:100](../backend/app/services/integrations/integration_manager.py#L100)),
so the flow raises "Missing OAuth2 configuration". Also note the frontend error message tells
users to set `GOOGLE_CALENDAR_CLIENT_ID` **env vars**, which the backend never reads — fix that
message too.

**Per-provider external work (yours):** register an OAuth app with each provider, set the
redirect URI to `…/dashboard/integrations/oauth/callback`, and obtain client id/secret.

**Files:** seed `auth_config` per connector (DB); optionally a small admin UI/env→DB loader;
correct the misleading frontend copy in the `[slug]` page.

**Test process (per provider):** seed credentials → Connect → complete consent → land on
callback → connection created → Test green → run a workflow Action (e.g. HubSpot
`create_contact`).

**Pass criteria:** OAuth completes and an action runs against the real service.

**Regression checks:** API-key connectors (Phase 2) still work.

---

## Phase 10 — Web chat widget

**Goal:** an embeddable text-chat widget (Vapi-style), no phone needed.

**Why & dependency:** missing entirely. High value as a phone-free channel. Reuses Phase 1 —
a `/chat` endpoint can wrap the same function-calling conversation logic in text mode.

**Files:** new backend `/chat` endpoint (text-mode wrapper over the Phase 1 loop); a
self-contained embeddable JS snippet; a public/unauthenticated agent-scoped access path
(scoped token per agent).

**Test process:** embed the snippet on a test HTML page, send messages, confirm replies and
tool calls; verify the public access path is properly scoped (can't reach other agents/data).

**Pass criteria:** an external page can chat with a specific agent, tools fire, and access is
correctly sandboxed.

**Regression checks:** authenticated dashboard conversation unaffected; no auth bypass
introduced.

---

## After every phase — the regression gate

1. Re-run the Phase 0 smoke test in full.
2. If any previously-green item is now red, **stop** and fix within the current phase before
   merging.
3. Merge the phase branch only when both its own test **and** the full smoke test pass.
4. Tag/commit so each phase is a known-good checkpoint you can roll back to.

## Suggested sequencing summary

Start with **Phase 1** (best value-to-risk, no external setup). Then **Phase 2** (contained,
independent, unblocks a whole feature area). Then tackle the telephony block as a unit:
**Phase 3 → 4 → 5**. Then **Phase 6–7** (feature completeness), **Phase 8** (cleanup), and the
larger builds **Phase 9–10** last. Reorder only if a specific demo forces telephony earlier —
in which case do Phases 1–2 first anyway to establish the test loop, then jump to Phase 3.
