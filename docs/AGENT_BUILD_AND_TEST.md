# Building and Testing a Full-Feature Agent

A step-by-step guide to building the most capable agent Voicecon can currently run,
testing every feature that actually executes, and knowing exactly which features cannot
be exercised yet and why.

Companion to [VOICECON_PLATFORM_GUIDE.md](./VOICECON_PLATFORM_GUIDE.md).

---

## 0. The honest scope

You asked for an agent that uses *every* feature. Here is what that means in practice,
verified against the source.

### The central constraint: tools do not run in conversation

`POST /api/v1/agents/{id}/respond` — the endpoint behind **both** the Live Test Call panel
and the `/test` page — contains **no function-calling loop**. Zero references to tools or
functions in the entire handler. It is a plain LLM chat with text-to-speech.

Tool execution exists in exactly one place: `voice_session.py`, the telephony path. That
path is dead, because `_transcribe_audio()` returns `None`.

```
Tool execution lives here ──→ voice_session.py  (phone)   ✗ dead: _transcribe_audio() → None
Conversation happens here ──→ /respond          (browser) ✗ no function calling
```

**There is currently no code path in which an agent calls a tool while talking to you.**

This is not a configuration problem and no amount of setup will fix it. It is a missing
function-calling loop in `/respond`. So the guide below tests conversation and tools
*separately* — which is the honest maximum today.

### What "all features" actually resolves to

| Feature | Exercisable? | How |
|---|---|---|
| Agent CRUD, prompt, first message | ✅ Yes | Dashboard |
| Voice/LLM/STT provider config | ✅ Yes | Dashboard (see §4 — the UI silently drops these) |
| **Tools — real API calls** | ✅ Yes, **in isolation** | Tools page → Test button |
| Tool assignment to agent | ✅ Yes | Persists correctly; just never fires in chat |
| Conversation (text + voice) | ⚠️ Needs `OPENAI_API_KEY` | Live Test Call |
| **Tools during conversation** | ❌ **No** | No function-calling loop in `/respond` |
| Webhooks (`slack` tool) | ✅ Yes, in isolation | Needs a webhook URL |
| Call transfer / hangup / SMS | ❌ No | Returns intent; nothing consumes it |
| Knowledge base query tool | ❌ No | Returns a stub; `rag_service.search()` unused |
| Workflows — Condition/Transform/Delay | ✅ Yes | Pure logic, keyless |
| Workflows — Action steps | ⚠️ Needs OAuth | Requires a `connection_id` from a connected integration |
| Workflows — Loop bodies | ❌ No | Iterates, never runs the body |
| Inbound / outbound phone calls | ❌ No | `_transcribe_audio()` + MP3→mulaw |

---

## 1. What is already built for you

I created and verified these in your account (`sajid.techzoid@gmail.com`) against the
running backend on port 8001.

**Agent `Demo Receptionist`** (`dbf41e83-39d9-40bf-bda3-58fc33d015a5`) — provider config
repaired. It had been saved with `tts_provider`, `tts_voice_id`, `llm_model`, and
`stt_model` all **empty strings**, which is why `/speak` was returning
`500 Unsupported TTS provider: ""`. Now:

```
llm_provider  openai          tts_provider  elevenlabs
llm_model     gpt-4o-mini     tts_voice_id  21m00Tcm4TlvDq8ikWAM
stt_provider  deepgram        stt_model     nova-2
```

**Three `api_request` tools**, all assigned to that agent, all executing successfully
against real public APIs with **no API keys required**:

| Tool | Endpoint | Verified |
|---|---|---|
| `get_weather` | `api.open-meteo.com` (Berlin, current temp) | `200`, 769 ms |
| `get_crypto_price` | `api.coingecko.com` (BTC/USD) | `200`, 494 ms — returned `{"bitcoin":{"usd":64589}}` |
| `log_callback_request` | `postman-echo.com/post` | `200` — parameters echoed back intact |

I originally pointed the third at `httpbin.org`, which returned a **503** while still
reporting `success: true` (see §3, the success trap). It now uses `postman-echo.com`.

There is also a leftover tool literally named `API Request` from your earlier click —
harmless, delete it when convenient.

---

## 2. Tier 0 — test everything that works with no API keys at all

Your `backend/.env` currently holds the placeholders shipped in `.env.example`:

```
OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...
ELEVENLABS_API_KEY=...
```

**Tool execution does not care.** It is plain HTTP from your backend to a public API — no
provider key is involved anywhere in the path. So you can test the entire tool subsystem
right now, before touching any credentials.

### 2.1 Test a tool from the dashboard

1. Go to **Tools**. You will see the three tools above.
2. Click **`get_crypto_price`** → **Test**.
3. Leave parameters empty (`{}`) and run it.

**Expected:** `success: true`, `status_code: 200`, body `{"bitcoin":{"usd":<price>}}`,
response time roughly 300–900 ms.

**If it fails:** the failure is network egress (can your backend reach the internet?) or a
rate limit from CoinGecko (`429`). It is *not* an API-key problem.

### 2.2 Test parameter passing

1. Open **`log_callback_request`** → **Test**.
2. Parameters:

```json
{ "name": "Sajid", "phone": "+15551234567" }
```

**Expected:** `200`, and the response body contains
`"data":{"name":"Sajid","phone":"+15551234567"}` — the echo service reflecting exactly what
the tool sent. This proves the parameter→body plumbing works end to end.

### 2.3 Create a fourth tool yourself

Tools → **New Tool** → type **API Request**:

| Field | Value |
|---|---|
| Tool Name | `get_country_info` |
| Description | `Look up information about a country. Use when the caller asks about a country.` |
| Server URL | `https://restcountries.com/v3.1/name/pakistan?fields=name,capital,population` |
| Method | `GET` |
| Timeout | `20` |

Save, then Test with `{}`. Expect `200` and JSON describing Pakistan.

Other keyless public APIs that work the same way:

```
https://api.open-meteo.com/v1/forecast?latitude=24.86&longitude=67.01&current=temperature_2m
https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd
https://api.zippopotam.us/us/90210
https://uselessfacts.jsph.pl/api/v2/facts/random
https://worldtimeapi.org/api/timezone/Asia/Karachi
```

---

## 3. How `api_request` actually works — read before designing tools

Two behaviours will otherwise waste your afternoon. Both verified in
[`function_executor.py:521-530`](../backend/app/services/function_executor.py#L521-L530).

```python
url    = cfg.get("url") or parameters.get("url")
method = cfg.get("method", "POST").upper()
body   = {**cfg.get("body", {}), **parameters}
resp   = await client.request(method, url, headers=headers, json=body)
```

### 3.1 Parameters go into the JSON **body**, never the query string

There is no URL templating and no query-parameter support. A parameter named `city` is sent
as `{"city": "Berlin"}` in the request body. A `GET` API reading `?city=` will **never see
it** — it will silently return its default response, and the tool will report success.

Two working patterns:

**Static URL (recommended).** Bake the query string into the Server URL, as all three tools
above do. Reliable, but the tool always returns data for the same city/coin.

**Dynamic URL.** Because of `cfg.get("url") or parameters.get("url")`, if you leave the
config URL **empty**, the caller supplies the whole URL as a `url` parameter. This is the
only way to get a dynamic `GET`. The dashboard marks Server URL as required, so you must
create such a tool through the API, not the form.

> A GET request carrying a JSON body is unusual but legal, and I confirmed both Open-Meteo
> and CoinGecko accept it and ignore the body. Some stricter APIs will reject it with `400`.

### 3.2 `success: true` does not mean the API succeeded

`_execute_tool` returns `success: true` whenever the **HTTP call completes**, regardless of
status code. It only reports `success: false` if an exception is raised — a DNS failure, a
timeout, a connection refusal.

This is exactly what bit the httpbin tool: a `503 Service Temporarily Unavailable` came back
as `success: true` with the error page in `body`. **Always read `status_code` inside
`response`, not the `success` flag.**

---

## 4. A trap when configuring the agent in the UI

`PATCH /api/v1/agents/{id}` accepts provider settings only as **nested objects**
(`llm`, `voice`, `stt`), per
[`AgentUpdate`](../backend/app/schemas/agent.py#L118). Flat fields like `tts_provider` are
**silently dropped** — the request returns `200 OK` and changes nothing. I hit this myself:
my first PATCH succeeded and updated zero fields.

This is almost certainly why your agent was saved with empty providers in the first place.
After editing an agent in the dashboard, **verify the values actually persisted** by
reloading the detail page. If TTS provider is blank, the greeting will fail with
`500 Unsupported TTS provider: ""`.

The correct body shape:

```json
{
  "llm":   { "provider": "openai",     "model": "gpt-4o-mini", "temperature": 0.7, "max_tokens": 300 },
  "voice": { "provider": "elevenlabs", "voice_id": "21m00Tcm4TlvDq8ikWAM", "speed": 1.0, "pitch": 1.0 },
  "stt":   { "provider": "deepgram",   "language": "en", "model": "nova-2" }
}
```

Note also that `LLMConfig`'s default model is `gpt-5.4-nano`, which is not a real model. Set
`model` explicitly.

---

## 5. Tier 1 — add `OPENAI_API_KEY` to unlock conversation

Conversation is the one thing no public API can substitute for.

1. Put a real key in `backend/.env`: `OPENAI_API_KEY=sk-proj-<real>`
2. **Restart the backend.** Uvicorn's `--reload` watches Python files, not `.env`.
3. Agent → **Start Call** → type `hello` in the text box → send.

**Expected:** the agent replies in character within a second or two, in text.

**Signs of failure and their causes:**

- Reply reads *"I'm having a technical issue right now. Please try again."* — this is the
  hardcoded fallback. The real error arrives on the same SSE stream as
  `{"type":"error", ...}`. Open devtools → Network → `/respond` → Response to read it. A
  placeholder key produces `401 Incorrect API key provided: sk-...`.
- Nothing at all happens when you press send — see §7.

You can now test the **system prompt** and **first message** properly. Change the prompt,
save, start a new call, and confirm the personality changes. Test `end_call_phrases` by
saying goodbye and watching the call auto-terminate.

## 6. Tier 2 — add Deepgram and ElevenLabs for voice

- `DEEPGRAM_API_KEY` → speech **in**. Verify the STT mode indicator reads `deepgram`. If it
  reads `webspeech`, the key is bad and you are silently testing Chrome's built-in
  recogniser, not your platform.
- `ELEVENLABS_API_KEY` → speech **out**. Without it, `/speak` 500s and the greeting is
  silent even though the text appears in the transcript.

Restart the backend after each change and confirm with a fresh call.

## 7. Tier 3 — what remains impossible

**Phone calls.** Inbound and outbound both die at `_transcribe_audio()`. Outbound is the
cruel one: Twilio genuinely rings the phone, then the media stream lands in the dead session
and the person who answered hears silence. Do not demo it.

**Tools in conversation.** Requires adding a function-calling loop to `/respond`.

**Call transfer, hangup, SMS.** Even with the loop, these return
`{"requires_telephony": true}` and nothing consumes it — the agent would *say* "transferring
you now" and do nothing.

**Knowledge base.** The `query_knowledge_base` tool returns a stub. A complete vector search
sits unused at [`rag_service.search()`](../backend/app/services/knowledge_base/rag_service.py#L448).
The agent will answer from the LLM's own training data while appearing to consult your
documents — plausible wrong answers, no error.

**Workflow Action steps.** Require a `connection_id` from an OAuth-connected integration
([`step_handlers.py:186`](../backend/app/services/workflows/step_handlers.py#L186)), so they
cannot be tested keylessly. Condition, Transform, and Delay steps are pure logic and do run.
Loop steps iterate but never execute their body, reporting `{"success": true}` regardless.

---

## 8. Demo script for the team lead

Lead with the tool subsystem. It is real, it hits live third-party APIs over the network,
and it needs no credentials — which makes it the most defensible thing to show.

1. **Tools page** → Test `get_crypto_price` → show a live Bitcoin price fetched from
   CoinGecko in ~500 ms.
2. Test `log_callback_request` with a name and phone → show the echo service returning
   exactly what the agent's tool sent. This is the "agent takes an action in the outside
   world" story.
3. **Agent detail** → show the three tools assigned, the system prompt, the voice config.
4. **Live Test Call** (needs `OPENAI_API_KEY`) → hold a real spoken or typed conversation.
5. **Analytics / Calls** → show the data layer is real SQL aggregation, not mocks.

Then say the honest thing, because it will be asked:

> "Tools execute for real — you just watched them hit live APIs. The agent can hold a real
> conversation. What isn't connected yet is the loop that lets the model *choose* a tool
> mid-conversation — that's a function-calling loop in one endpoint. And telephony needs the
> transcription function plus an audio-format conversion. Everything on either side of those
> two gaps is built and working."

That frames two bounded pieces of work rather than a rewrite, and every claim survives
someone opening the code.

---

## 9. Recommended order to close the gaps

1. **Function-calling loop in `/respond`.** Pass assigned tools as OpenAI function
   definitions, execute via `function_executor.execute_global_tool`, feed results back,
   stream the final reply. Unlocks the entire demo you originally wanted, and needs no
   telephony work.
2. `_transcribe_audio()` + MP3→mulaw conversion, **as one change**. Unlocks phone calls.
3. Telephony tool execution — consume `requires_telephony`, dispatch to `twilio_service`.
4. `query_knowledge_base` → call `rag_service.search()`. Cheap; the engine exists.
5. Query-parameter and URL-templating support in `api_request` (§3.1).
6. Report non-2xx as a failure in `_execute_tool` (§3.2).
