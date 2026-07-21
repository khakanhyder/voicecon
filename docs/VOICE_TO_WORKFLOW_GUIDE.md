# Voice → Tool → Workflow → API → Speech

How the end-to-end system works, and how to build and test it.

A working demo is already seeded. To recreate or reset it:

```bash
cd backend
./venv/bin/python -m scripts.seed_demo_agent          # create / update
./venv/bin/python -m scripts.seed_demo_agent --clean  # remove
```

It creates the agent **[demo] Aria** with two workflow-backed tools using free,
keyless APIs (open-meteo, CoinGecko).

---

## 1. The end-to-end path

```
Caller speaks
   │  Deepgram STT
   ▼
Transcript ──► OpenAI (with tool schemas attached)
   │
   │  model decides: call `get_weather` with {"city": "Tokyo"}
   ▼
Agent speaks a filler line   "Let me check the weather for you."
   │
   ▼
Tool (type: workflow) ──► WorkflowEngine.execute_workflow(
                              workflow_id,
                              trigger_data = {"city": "Tokyo"},
                              channel = VoiceChannel(session))
   │
   ▼
Workflow runs node by node
   geocode ──► forecast ──► branch ──► set fields
   │
   ▼
Result returned  {"variables": {"location": "Tokyo", "temperature_c": "24.4", …}}
   │
   ▼
Appended to the conversation as a tool message
   │
   ▼
OpenAI turn 2 ──► "It's twenty four degrees in Tokyo, a jacket would be sensible."
   │  ElevenLabs TTS
   ▼
Caller hears the answer
```

Two OpenAI calls per tool use: one to decide, one to answer from the result.

---

## 2. Creating the agent

Dashboard → Agents → New, or use the seed script.

Settings that matter:

| Setting | Value | Why |
|---|---|---|
| LLM provider | **openai** | Tool calling is OpenAI-only today. Anthropic agents get no tools. |
| Model | `gpt-4o-mini` or better | Must support function calling |
| System prompt | see below | Drives tool-calling accuracy |
| First message | a short greeting | Sets expectations about what the agent can do |

---

## 3. Writing the system prompt

The prompt does two jobs: control **how it speaks**, and control **when it calls
tools**. The demo prompt (in `scripts/seed_demo_agent.py`) is a working
template. The parts that matter:

**Speech rules.** Everything is heard, not read.

```
- Keep replies to one or two short sentences.
- No bullet points, markdown, emoji, or symbols.
- Say numbers as a person would: "twenty two degrees", not "22C".
- Never read out raw data, JSON, field names, or URLs.
```

Without this the model produces text shaped for a screen, which sounds wrong
read aloud.

**Tool rules.** These four lines do most of the work:

```
1. When the caller asks for something a tool covers, call that tool.
   Do not guess or answer from memory — live data changes.
2. Work out the parameters from what the caller said.
3. If a required detail is missing, ask one short question, then call the tool.
   Do not invent a value.
4. Call one tool at a time and wait for the result.
```

Rule 1 stops the model answering weather questions from training data. Rule 3
prevents the most common failure — hallucinating a city because the caller
didn't name one.

**After-tool rules.**

```
- Answer using the data the tool returned, in your own words.
- If the tool reports an error, apologise briefly and offer to try again.
  Never invent a result.
```

---

## 4. How the agent picks a tool

There is no separate intent classifier, and none is needed. **The tool
description IS the intent definition.** OpenAI matches the caller's phrasing
against the descriptions of the tools attached to the agent.

This makes the description the single highest-leverage field you write.

```
Bad:   "Weather workflow"
Good:  "Get the current weather and temperature for a city. Use this whenever
        the caller asks about weather, temperature, or what it is like outside
        somewhere."
```

Name the trigger phrases the caller would actually use. If two tools overlap,
say explicitly in each description when *not* to use it.

---

## 5. Defining a tool

A tool becomes callable by an agent when it is:

1. Created with `tool_type: "workflow"`
2. Configured with the workflow it runs
3. Assigned to the agent

```json
{
  "name": "Get weather",
  "description": "Get the current weather and temperature for a city…",
  "tool_type": "workflow",
  "config": {
    "workflow_id": "e6c5c45d-dead-4c71-b846-149f8a8eb719",
    "filler_message": "Let me check the weather for you."
  }
}
```

`filler_message` is spoken *before* the workflow runs. A workflow doing two API
calls takes a couple of seconds; without a filler the caller hears silence and
usually starts talking again, which derails the turn.

The tool's **parameters are not written by hand** — they are derived from the
workflow's declared inputs (next section).

---

## 6. Declaring workflow inputs

Open the workflow in the builder, click the **trigger node**, and add inputs.

| Field | Purpose |
|---|---|
| name | The key. Referenced in nodes as `{{trigger.city}}` |
| type | string / number / boolean |
| description | **What the model uses to extract the value from speech** |
| required | Whether the model must supply it |

These become the tool's JSON Schema automatically:

```json
{
  "type": "object",
  "properties": {
    "city": {"type": "string", "description": "The city to get the weather for, e.g. Tokyo"}
  },
  "required": ["city"]
}
```

Write the description as an instruction to the model. `"CoinGecko coin id,
lowercase. Examples: bitcoin, ethereum, dogecoin"` is why the demo works when a
caller says "what's doge at" — the model maps the spoken word to `dogecoin`.

---

## 7. Workflow architecture — the weather demo

```
      ┌─────────────────────┐
      │ Trigger             │  inputs: city
      │ (city)              │  out → geocode
      └──────────┬──────────┘
                 │
      ┌──────────▼──────────┐
      │ Webhook: geocode    │  GET geocoding-api.open-meteo.com/v1/search
      │                     │      ?name={{trigger.city}}&count=1
      │                     │  returns → body.results[0].{latitude,longitude,name}
      └──────────┬──────────┘
                 │
      ┌──────────▼──────────┐
      │ Webhook: forecast   │  GET api.open-meteo.com/v1/forecast
      │                     │      ?latitude={{steps.geocode.body.results[0].latitude}}
      │                     │      &longitude={{steps.geocode.body.results[0].longitude}}
      │                     │  returns → body.current.temperature_2m
      └──────────┬──────────┘
                 │
      ┌──────────▼──────────┐
      │ Branch: is it hot?  │  steps.forecast.body.current.temperature_2m > 25
      └────┬───────────┬────┘
      true │           │ false
    ┌──────▼────┐ ┌────▼──────┐
    │ Set Fields│ │ Set Fields│  location, temperature_c, advice
    │ hot       │ │ mild      │
    └───────────┘ └───────────┘
```

**Node by node:**

| Node | Receives | Does | Returns |
|---|---|---|---|
| Trigger | `{"city": "Tokyo"}` from the LLM | Publishes it as `trigger.*` | — |
| geocode | `{{trigger.city}}` in the URL | Turns a city name into coordinates | `body.results[0].{latitude,longitude,name}` |
| forecast | coordinates from geocode | Fetches current conditions | `body.current.temperature_2m` |
| Branch | temperature | Routes on `> 25` | fires `true` **or** `false` |
| Set Fields | everything above | Names the values for the agent | `location`, `temperature_c`, `advice` |

The **forecast node reading geocode's output** is the important part — that is
data flowing between nodes, and it is what makes this a workflow rather than a
single API call.

---

## 8. How data flows

Every node's output is stored under `steps.<node_id>`, so any later node can
read it:

| Reference | Resolves to |
|---|---|
| `{{trigger.city}}` | An input the LLM supplied |
| `{{steps.geocode.body.results[0].latitude}}` | Array element from an API response |
| `{{steps.forecast.body.current.temperature_2m}}` | Nested object field |
| `{{location}}` | A field published by a Set Fields node |
| `{{loop.item}}` | Current item inside a Loop Over Items body |

Typing `{{` in any text field in the builder opens autocomplete listing
everything available at that node.

**Set Fields is what the agent actually reads.** Its fields come back in the
tool result as `variables`, with plain names. Without it the agent receives raw
API JSON and has to guess which field matters. With it:

```json
{"location": "Tokyo", "temperature_c": "24.4", "advice": "It's on the cooler side…"}
```

---

## 9. How the result gets spoken

The tool returns:

```json
{
  "success": true,
  "status": "completed",
  "output": { …last successful step's result… },
  "variables": { "location": "Tokyo", "temperature_c": "24.4", … },
  "error": null
}
```

This is appended to the conversation as a tool message, and the model is called
again. It sees the data and phrases it naturally. You never write the sentence
— the system prompt's speech rules shape it.

If the workflow fails, `success` is `false` and `error` explains why; the
prompt's "never invent a result" rule makes the agent apologise instead.

---

## 10. Testing

**Browser (fastest):** `/dashboard/agents/<agent-id>/test`

Try:

- *"What's the weather in Tokyo?"* → calls the weather tool
- *"How much is bitcoin right now?"* → calls the crypto tool
- *"What's the weather?"* → should **ask which city**, not invent one
- *"Tell me a joke"* → no tool covers it; should answer normally

**Workflow alone:** open it in the builder and hit **Test run**. The results
panel shows each node's status, timing, output, and errors. This isolates
workflow problems from agent problems.

**Phone call:** point a phone number at the agent and call it. Same path, plus
real STT/TTS latency.

### If something doesn't work

| Symptom | Cause |
|---|---|
| Agent answers without calling the tool | Description too vague, or provider isn't OpenAI |
| "The workflow could not be started" | Workflow is **inactive** — activate it |
| Wrong / missing parameters | Input `description` isn't specific enough |
| Node fails in Test run | Check its output in the results panel |
| Long silence before the answer | Add or shorten `filler_message` |

---

## 11. Best practices

**Tools**
- One tool per user intent. Don't build a "do everything" tool with a mode flag.
- Write descriptions as trigger phrases, not titles.
- Always set a `filler_message` for anything touching a network.

**Workflow inputs**
- Only mark something required if the workflow genuinely cannot run without it —
  required inputs force the agent to interrogate the caller.
- Put format hints in the description (`lowercase coin id`, `ISO date`). This is
  where you control the model's extraction.

**Workflow structure**
- Always end with a **Set Fields** node. It is the workflow's public contract:
  rename messy API fields into names the agent can speak.
- Keep the shape stable — the agent's phrasing depends on it.
- Set a **timeout** on every webhook node (Settings tab) so one slow API can't
  hang a call.
- Use **Branch** for logic the workflow owns; leave conversational judgement to
  the agent.

**Reuse**
- Build workflows around a capability ("look up a customer"), not a phrasing
  ("check if John is a customer"). One workflow can back several tools.
- A workflow used as a tool should be self-contained: inputs in, data out, no
  assumptions about who called it.

---

## 12. Current limits

- **OpenAI only.** Anthropic agents are given no tools at all.
- **One tool per turn**, up to 5 sequential tool calls per user utterance.
- **Workflows block the conversation** while running. The filler line covers a
  couple of seconds; anything longer will feel wrong on a call.
- **No durable waits.** A workflow that needs to pause for minutes isn't
  supported yet — it would hold the call open.
- Interpolation supports dot paths and array indexing, but not expressions
  (no arithmetic, no function calls inside `{{ }}`).
