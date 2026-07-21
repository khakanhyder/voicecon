# Workflow Builder — Implementation Plan

**Goal:** transform the current linear step-list into a production-grade visual workflow builder comparable to n8n / Zapier / Make.

**Status:** planning only. No code has been changed.

---

## 1. Current Implementation Review

### 1.1 What exists today

**Backend** (`backend/app/services/workflows/`, `backend/app/api/v1/endpoints/workflows.py`)

| Piece | File | Reality |
|---|---|---|
| Storage | `app/models/integration.py:153` | One JSON column `workflow_steps` holding `{"steps": [...]}` |
| Step shape | `app/schemas/workflow.py:59-110` | `{id, name, type, description, config, next_step_id}` |
| Engine | `app/services/workflows/workflow_engine.py:203-423` | Single-cursor `while` loop, in-process asyncio, no queue |
| Step types | `app/services/workflows/step_handlers.py:1102-1145` | 12: `action, condition, loop, transform, delay, speak, ask, transfer, end, tool, webhook, ai` |
| Triggers | `app/services/workflows/trigger_handlers.py:441-472` | `manual, webhook, call_completed, call_started, integration_event` + a 30s-poll `schedule` loop |
| Executions | `app/models/integration.py:189-227` | One row per run; step logs live in memory and are flushed once at the end (`workflow_engine.py:376`) |
| Data mapping | `step_handlers.py:126-161` | Regex `{{a.b.c}}` interpolation, dot paths only, no array indexing |
| Rich mapping | `data_mapper.py` | 36 transformations, array indexing, formulas — used **only** by `transform` steps |

**Frontend** (`frontend/src/app/dashboard/workflows/[id]/builder/page.tsx`)

A 920-line page rendering a centered **vertical list of cards** with 1px divs drawn as connector lines. No canvas library. Add → appends to end. Reorder → hover-hidden up/down chevrons. Edit → right-hand 384px panel. Save → manual `PATCH`.

A **second, unrelated** graph editor exists at `frontend/src/components/agents/FlowBuilder.tsx` for agent call flows, built on `react-flow-renderer` v10. Its node vocabulary (`start, message, question, decision, function, transfer, end`) does not overlap with the workflow vocabulary at all.

### 1.2 Limitations — structural

1. **No graph model.** `next_step_id` gives each step exactly one forward pointer (`schemas/workflow.py:110`). There are no edges, no node positions, no ports/handles anywhere in the backend. A canvas cannot round-trip its own layout.
2. **Branching is invisible.** `condition` steps store jump targets as step-ID strings in `config.on_true`/`config.on_false`. The UI always draws a straight top-to-bottom chain regardless (`builder/page.tsx:801-815`), so a condition jumping backwards to step 2 looks identical to a linear flow.
3. **No parallelism, no fan-out, no join.** `workflow_engine.py:252-358` is strictly one step at a time.
4. **`on_true`/`on_false` are typed `List[str]`** (`schemas/workflow.py:79-80`) but consumed as a scalar and used as a dict key (`step_handlers.py:367` → `workflow_engine.py:253`). The schema-valid shape `on_true: ["s2"]` raises `TypeError: unhashable type: 'list'`.
5. **`LoopStepConfig.steps: List[str]`** (`schemas/workflow.py:86`) contradicts the handler, which expects inline step *objects* (`step_handlers.py:546`). Schema-conformant loops fail.
6. **Templates are unexecutable.** All 10 templates in `workflow_templates.py` use a different vocabulary (`contains_intent`, `salesforce_create_lead`, `notify`, `wait`, …) with no entry in `StepHandlerFactory` and no converter. Installing a template cannot produce a runnable workflow.

### 1.3 Limitations — reliability

7. **`or_` is not imported.** `workflows.py:12` imports `select, and_, func, desc`; `:159` calls `or_(...)`. Any `GET /workflows?search=foo` → `NameError` → 500. *(Ship a fix immediately, independent of this plan.)*
8. **Scheduler passes a closing session into a detached task** (`scheduler.py:110`) — exactly the bug `workflow_engine.py:112-115` documents and avoids. The task is also unreferenced and may be GC'd.
9. **Duplicate scheduled runs.** `_check_cron_schedule` treats "fired within 60s" as due (`scheduler.py:136-142`) while polling every 30s (`:69`), and `last_executed_at` is written only after the run starts (`:244`).
10. **Cancellation is cosmetic.** `cancel_execution` flips the DB row (`workflow_engine.py:449`); the running task never polls it and overwrites the status at `:370`. No endpoint exposes it anyway.
11. **No timeouts.** `ActionStepConfig.timeout_seconds` (`schemas/workflow.py:73`) is never read by `ActionStepHandler`. There is no wall-clock ceiling on an execution.
12. **`delay` blocks a resident coroutine** (`step_handlers.py:754`). A 24h delay = a 24h asyncio task that dies on deploy.
13. **Stranded `running` executions.** No reaper, no checkpoint, no resume. Process death loses every step result collected so far.
14. **Cycle detection is fake.** `visited` is populated (`workflow_engine.py:258`) and never read; only `max_steps` (`:250`) guards — a tight 2-step cycle burns 100 executions *plus their side effects*.
15. **Retries are fixed-delay, not exponential**, and only apply to `action`/`tool`/`webhook` (`workflow_engine.py:276, 323`).

### 1.4 Limitations — security *(treat as pre-work, not roadmap)*

16. **Cross-tenant trigger execution.** `TriggerManager.process_event` selects **every** active workflow of a trigger type across all organizations (`trigger_handlers.py:506-509`). Combined with an unauthenticated `POST /workflows/webhook/{key}` (`workflows.py:837`) whose key-length validator is never wired up, and `/trigger/voice-event` + `/trigger/integration-event` accepting arbitrary dicts from any authenticated user without filtering by `current_user` — any logged-in user can fire another tenant's workflows with attacker-chosen data.
17. **`eval()` on interpolated data.** `data_mapper.py:628` evaluates a formula string *after* substituting source values into it (`:610-622`). `__builtins__` is emptied, but the substituted values (e.g. a call transcript field) are attacker-influenced.
18. **Executions authorized by `user_id` only** (`workflows.py:507`) while workflows are owned by an organization (`models/integration.py:141`). Org-level access control does not exist.

### 1.5 Limitations — UX

19. "Add step" between two cards **always appends to the end** — every picker is wired to the same `addStep` (`builder/page.tsx:682`). No insert-at-index exists.
20. Deleting a step **leaves dangling branch targets** — `deleteStep` (`:693`) never scans other steps' `on_true`/`on_false`.
21. Changing step type **destroys config silently** (`:872`) with no undo.
22. No undo/redo, no unsaved-changes guard, no autosave, no validation, no duplicate/copy/paste/multi-select/search.
23. `step_${Date.now()}` IDs (`:677`) can collide, and collisions corrupt branch targeting.
24. Dead "View Execution History" link → 404 (`[id]/page.tsx:485`); permanently disabled "Test Workflow" button (`:488`) above a working test panel.
25. Agent dropdown is **hardcoded** to literal `agent1`/`agent2` (`new/page.tsx:124`, `edit/page.tsx:184`).

### 1.6 The agent FlowBuilder is broken in three ways

Relevant because it is the obvious reuse candidate:

- **(a) Nodes cannot be dropped onto the canvas.** `NodeToolbar` sets drag data (`NodeToolbar.tsx:104`) but `FlowBuilder` has no `onDrop`/`onDragOver` (`:379-400`), no `ReactFlowProvider`, no instance capture. Only templates can populate the canvas.
- **(b) Undo/redo throws.** `useFlowHistory.ts:38,83` call `addSnapshot`/`initialize`; `FlowHistory` exposes only `push/undo/redo/canUndo/canRedo/clear` (`flowHistory.ts:17-51`). Uncaught async `TypeError` 500ms after any node change; both buttons permanently disabled.
- **(c) Validation panel is dead.** `validateFlow` returns `{valid, errors, warnings}` but is assigned into `useState<string[]>` (`FlowBuilder.tsx:119`), so `.length` is `undefined` and the panel never renders.

Root cause: `flowValidation.ts` and `flowHistory.ts` were written against `reactflow` v11 while their consumers run `react-flow-renderer` v10. Both libraries are in `package.json`; v11 is **type-only imports in 2 files** and contributes nothing at runtime.

---

## 2. Comparison With Modern Workflow Builders

| Capability | n8n | Zapier | Make | **Voicecon today** |
|---|---|---|---|---|
| Visual canvas, pan/zoom | ✅ | ⚠️ linear | ✅ | ❌ card list |
| Drag nodes, free positioning | ✅ | ❌ | ✅ | ❌ |
| Explicit edges w/ multiple outputs | ✅ | ❌ | ✅ | ❌ single `next_step_id` |
| Branch / router / switch | ✅ | ✅ Paths | ✅ Router | ⚠️ 2-way, invisible |
| Merge / join | ✅ | ❌ | ✅ | ❌ |
| Parallel branches | ✅ | ❌ | ✅ | ❌ |
| Loop / iterator over array | ✅ | ⚠️ | ✅ | ⚠️ inline sub-steps only |
| Sub-workflows | ✅ | ❌ | ✅ | ❌ |
| Per-node error output / catch | ✅ | ⚠️ | ✅ | ⚠️ global stop/continue |
| Retry w/ exponential backoff | ✅ | ✅ | ✅ | ⚠️ fixed delay |
| Durable long delays (days) | ✅ | ✅ | ✅ | ❌ in-process sleep |
| Live per-node execution status | ✅ | ⚠️ | ✅ | ❌ |
| Run a single node in isolation | ✅ | ✅ | ✅ | ❌ |
| Pinned/mock data for testing | ✅ | ❌ | ⚠️ | ❌ |
| Execution history + replay | ✅ | ✅ | ✅ | ⚠️ list only, no replay |
| Expression editor w/ autocomplete | ✅ | ⚠️ | ✅ | ❌ raw `{{}}` in textareas |
| Data picker from upstream output | ✅ | ✅ | ✅ | ❌ |
| Versioning / rollback | ✅ | ✅ | ⚠️ | ⚠️ int counter only |
| Node search palette | ✅ | ✅ | ✅ | ⚠️ 8-item popover |
| Undo/redo | ✅ | ✅ | ✅ | ❌ |
| Copy/paste, multi-select | ✅ | ⚠️ | ✅ | ❌ |
| Auto-layout | ✅ | n/a | ✅ | ❌ |
| Minimap | ✅ | n/a | ✅ | ❌ |
| Notes / sticky annotations | ✅ | ❌ | ✅ | ❌ |
| Credential separation | ✅ | ✅ | ✅ | ✅ via `IntegrationConnection` |
| Webhook trigger w/ test URL | ✅ | ✅ | ✅ | ⚠️ exists, insecure |
| Concurrency / rate limiting | ✅ | ✅ | ✅ | ❌ |

**The three defining gaps:** (1) there is no graph — only a list; (2) there is no durable execution — only an in-process loop; (3) there is no feedback loop — you cannot see, test, or debug a run node-by-node.

---

## 3. Target Architecture

### 3.1 Graph data model

Replace the flat `{"steps": [...]}` blob with an explicit graph. Keep the JSON column for the *draft* definition, add tables for what needs querying.

```jsonc
// workflows.graph (JSON)
{
  "schema_version": 2,
  "nodes": [
    {
      "id": "n_a1b2c3",              // nanoid, generated client-side, stable forever
      "type": "http.request",         // namespaced type key, see §8
      "typeVersion": 1,               // per-node-type schema version
      "name": "Fetch CRM record",
      "position": { "x": 240, "y": 120 },
      "parameters": { "url": "={{ $json.crmUrl }}", "method": "GET" },
      "credentials": { "connectionId": "uuid" },
      "disabled": false,
      "notes": "",
      "onError": "stop",             // stop | continue | continueErrorOutput
      "retry": { "enabled": true, "maxTries": 3, "backoff": "exponential", "waitMs": 1000 },
      "timeoutMs": 30000,
      "pinnedData": null              // dev-time mock, see §7.3
    }
  ],
  "edges": [
    {
      "id": "e_x1",
      "source": "n_a1b2c3",
      "sourceHandle": "main",         // main | true | false | error | branch-<k>
      "target": "n_d4e5f6",
      "targetHandle": "main",
      "label": null
    }
  ],
  "groups":  [ { "id": "g_1", "name": "Enrichment", "nodeIds": [...] } ],
  "stickies":[ { "id": "s_1", "text": "...", "position": {...}, "size": {...}, "color": "yellow" } ],
  "settings": {
    "errorWorkflowId": null,
    "executionTimeoutMs": 900000,
    "maxConcurrentRuns": 5,
    "saveSuccessfulExecutionData": true
  }
}
```

Design decisions:

- **Node IDs are client-generated nanoids**, never `Date.now()` — fixes limitation #23 and makes edges stable across renames and reorders.
- **Position lives in the node**, so the canvas round-trips. This is the single change that unblocks everything visual.
- **Handles carry the semantics.** A condition node has `true`/`false` output handles; a switch has `branch-0..n`; every node optionally has an `error` handle. Branching stops being config strings and becomes real edges — fixes #2, #4, #20.
- **`typeVersion`** lets a node's parameter schema evolve without breaking saved workflows (n8n's approach). Migrations are per-node-type functions, not global.
- **Order is derived, never stored.** The `order` field disappears entirely.

### 3.2 New tables

```
workflow_versions       (id, workflow_id, version, graph JSON, created_by, created_at, note)
                        -- immutable snapshot per publish; enables diff + rollback

workflow_executions     -- extend existing
  + version_id FK, + mode (manual|trigger|retry|test), + parent_execution_id
  + status: queued|running|waiting|succeeded|failed|cancelled|timed_out
  + resume_state JSON (cursor + queue for durable wait/resume)
  + heartbeat_at (for reaping stranded runs — fixes #13)

workflow_node_executions (id, execution_id, node_id, node_type, run_index,
                          status, started_at, finished_at, duration_ms,
                          input_json, output_json, error_json, attempt)
                        -- one row PER NODE RUN, written as it happens (fixes #13, #20)

workflow_waits          (id, execution_id, node_id, resume_at, resume_token, payload)
                        -- durable timers for delay/wait-for-webhook (fixes #12)
```

Retention: `input_json`/`output_json` are the volume risk. Cap at ~256 KB per row with an overflow pointer to object storage, and add a per-org retention policy (default 30 days) enforced by a nightly job.

### 3.3 Execution engine

Rewrite `workflow_engine.py` as a **DAG scheduler with a durable work queue**, not a linear walker.

```
Trigger → enqueue Execution (status=queued)
             ↓
        Celery worker picks up
             ↓
   ┌──── Scheduler loop ─────────────────────┐
   │  ready = nodes whose inbound deps are   │
   │          satisfied and not yet run      │
   │  dispatch ready nodes CONCURRENTLY      │
   │    (asyncio.gather, bounded semaphore)  │
   │  each node: run → persist node_execution│
   │             → resolve outbound edges    │
   │  on wait: persist resume_state, exit    │
   └─────────────────────────────────────────┘
```

Key properties:

- **Concurrency by construction.** Two edges leaving the same handle = parallel branches. A node with multiple inbound edges is a join; its run mode (`waitForAll` vs `firstToArrive`) is a node setting.
- **Item-based data flow (Make/n8n model).** Every node receives and emits a **list of items** `[{json: {...}, binary?: {...}}]`, not a single object. This makes iteration implicit — an HTTP node fed 50 items runs 50 times unless it declares itself an aggregator. It is the single most important modeling choice for matching n8n's ergonomics, and it removes the need for most explicit loop nodes.
- **Cycles are rejected at save time**, not survived at runtime. Loop-back is expressed by a `loop` node with an explicit `done` output — fixes #14.
- **Suspend/resume is first-class.** `delay`, `wait-for-webhook`, and `wait-for-approval` persist `resume_state` and release the worker. A separate beat schedules resumption from `workflow_waits` — fixes #12.
- **Cooperative cancellation.** The scheduler checks execution status between node dispatches and honours a Redis cancel flag — fixes #10.
- **Timeouts at three levels:** per-node (`timeoutMs`), per-execution (`settings.executionTimeoutMs`), and a stranded-run reaper on `heartbeat_at` — fixes #11, #13.
- **Retries** move to per-node config with exponential backoff + jitter, applicable to any node type — fixes #15.

### 3.4 Why Celery, and what to watch

Celery is already a dependency and already running (`app/workers/celery_app.py`), so it is the pragmatic choice — but workflows never touch it today. Two constraints to design around:

- Celery's visibility timeout must exceed the longest node timeout, or tasks get redelivered mid-run. Set the node timeout ceiling *below* the visibility timeout and enforce it in validation.
- Idempotency: a redelivered task must not re-run side-effecting nodes. Persist node completion **before** acking, and key node execution on `(execution_id, node_id, run_index)` so a replay is a no-op.

If workflows later need durable multi-day waits at high volume, revisit Temporal — but not in this scope; the `workflow_waits` table covers the near-term need at a fraction of the operational cost.

---

## 4. Node Connection System, Validation & Data Flow

### 4.1 Connection rules (enforced in UI and on save)

| Rule | Enforcement |
|---|---|
| Trigger nodes have no input handle | Node type descriptor |
| Exactly one trigger node per workflow | Save-time validation |
| No cycles except through a `loop` node's back edge | DFS on save |
| An output handle may fan out to N targets | Allowed |
| An input handle may accept N sources (join) | Allowed; node declares merge mode |
| Type-compatibility of handles | v2 — start permissive, warn only |
| No edge to/from a disabled node's dependents | Warn, allow |

### 4.2 Validation tiers

1. **Live (as you edit)** — orphan nodes, missing required parameters, unreachable subgraphs, unresolved expression references, dangling credentials. Rendered as per-node badges plus a dockable issues panel.
2. **On save** — structural: single trigger, acyclic, all edge endpoints exist, node types resolvable at declared `typeVersion`.
3. **On activate** — everything above, plus credentials present and valid, trigger config valid (**wire up `TriggerValidator`, which is currently never called** — fixes #6), webhook path unique.

### 4.3 Expressions and data flow

Adopt an n8n-style expression syntax, evaluated in a sandbox:

```
={{ $json.customer.email }}                    // current item
={{ $node["Fetch CRM record"].json.id }}       // named upstream node
={{ $items("Split")[0].json.name }}            // indexed access
={{ $trigger.json.call_id }}
={{ $env.REGION }}   $now  $execution.id  $workflow.id
```

Implementation:

- **Do not extend the current regex interpolation** (`step_handlers.py:126-161`) — it has no array indexing, no functions, and silently leaves unresolved refs as literal `{{x}}` text.
- **Do not use `eval()`.** Replace `data_mapper.py:628` outright. Use a restricted AST-walking evaluator (Python: parse with `ast`, whitelist node types and a function registry; reject attribute access outside a safe allowlist) with a hard step/time budget. This closes #17.
- **`data_mapper.py`'s 36 transformations become the function library** exposed to expressions (`.upper()`, `.toDate()`, `.jsonParse()`, …) rather than being reachable only from `transform` steps. This is high-value reuse of existing, working code.
- **Frontend and backend must share the grammar.** Write the evaluator once as a spec + test corpus, implement in both, and run the same fixture suite against each in CI. Divergence here is the classic source of "works in preview, fails at runtime".

### 4.4 Data picker UX

The config panel shows a live tree of upstream node outputs (from the last run or pinned data). Clicking a leaf inserts the correct expression. Every expression field shows a resolved preview against real data. This is the single highest-leverage UX feature — it is what makes expressions usable by non-developers.

---

## 5. UI/UX Design

### 5.1 Canvas

- **React Flow v12** (`@xyflow/react`). Migrate all 11 `react-flow-renderer` v10 files and drop both old packages — resolves the v10/v11 split that causes defects (a)–(c) in §1.6.
- Infinite pan/zoom, `snapToGrid` 16px, minimap, zoom controls, fit-view, background dots.
- **Selection:** click, shift-click, marquee (drag on empty canvas), `Cmd+A`.
- **Multi-select operations:** move, delete, duplicate, group into a frame, align/distribute.
- **Copy/paste** via clipboard JSON — including *across browser tabs and workflows*, which is how power users actually compose flows.
- **Auto-layout** with ELK.js (layered, left-to-right) on a "Tidy up" command.
- **Sticky notes** as a first-class node type for documentation.

### 5.2 Node interactions

- Drag from the palette **or** drag off an output handle onto empty canvas → opens the node picker pre-wired to that handle. (This is n8n's core interaction and worth getting exactly right.)
- Drop a node **onto an existing edge** → splices it inline.
- Hover toolbar per node: run-from-here, disable, duplicate, delete, pin data.
- Double-click → config panel. `Enter` on selection → config panel.
- Right-click context menus for canvas, node, edge, and selection.
- Edge hover → `+` to insert a node, `×` to delete.

### 5.3 Keyboard map

`Cmd+Z`/`Cmd+Shift+Z` undo/redo · `Cmd+C/V/D` copy/paste/duplicate · `Del` delete · `Cmd+A` select all · `Cmd+S` save · `Cmd+K` node search · `Cmd+Enter` execute · `Space+drag` pan · `Cmd+0/1` reset/fit zoom · `Tab` open picker from selection · `D` disable · `P` pin data

### 5.4 Panels

- **Left:** searchable node palette, grouped by category, with recents and favourites.
- **Right (config):** tabs — *Parameters* / *Settings* (retry, timeout, error handling, notes) / *Docs*. Split view showing **Input | Parameters | Output** side by side, which is what makes the data picker work.
- **Bottom (dockable):** execution log, issues list, expression console.
- **Top bar:** name, breadcrumb, version selector, save state, active toggle, Execute, Test, History.

### 5.5 Accessibility & non-negotiables

- Every canvas action reachable by keyboard; nodes focusable and traversable via arrow keys.
- Never destroy user work silently: **changing a node type warns and preserves the old config for undo** (fixes #21); every mutation goes through the history stack; `beforeunload` guard plus 2s-debounced autosave to a local draft (fixes #22).
- Deleting a node cleanly removes its edges — impossible to leave a dangling reference by construction (fixes #20).

---

## 6. Node Types & Extensibility

### 6.1 Node descriptor contract

Every node type is a declarative descriptor — the same object drives the palette entry, the config form, validation, and the docs tab. Adding a node type means adding a descriptor plus an executor; **no UI code changes**.

```ts
{
  type: 'http.request',
  version: 1,
  category: 'Core',
  displayName: 'HTTP Request',
  icon: 'globe',
  color: '#2563eb',
  inputs:  [{ name: 'main', type: 'main' }],
  outputs: [{ name: 'main', type: 'main' }, { name: 'error', type: 'main', optional: true }],
  credentials: [{ type: 'httpAuth', required: false }],
  properties: [
    { name: 'url', displayName: 'URL', type: 'string', required: true, supportsExpression: true },
    { name: 'method', type: 'options', default: 'GET', options: [...] },
    { name: 'body', type: 'json', displayOptions: { show: { method: ['POST','PUT','PATCH'] } } }
  ]
}
```

`displayOptions` (conditional field visibility) is essential — it is how a single descriptor supports a node with 40 parameters that only ever shows 6 at a time.

**Descriptors are generated from a single source of truth** (a shared JSON schema per node type, checked into `shared/nodes/`), with the TypeScript descriptor and the Python executor signature both derived from it. Hand-maintaining two parallel definitions is how the current `on_true: List[str]` / scalar mismatch (#4) happened.

### 6.2 Node catalogue

**Triggers** — Manual, Schedule (cron/interval), Webhook, Call Started, Call Ended, Integration Event, Form Submission, Sub-workflow Called, Error Trigger

**Core** — HTTP Request, Code (sandboxed JS/Python), Set/Edit Fields, Filter, IF, Switch (n-way), Merge, Loop Over Items, Split Out, Aggregate, Sort, Limit, Remove Duplicates, Wait (duration/until/webhook), No-Op, Sticky Note, Sub-workflow, Stop and Error

**Voice** *(the domain differentiator — these are why this is not just an n8n clone)* — Speak, Ask, Transfer, Play Audio, Record, DTMF Gather, Hang Up, Start Call (outbound), Send SMS

**AI** — LLM Completion, Extract Structured Data, Classify, Summarize, Sentiment, Embed & Search, AI Agent (tool-calling)

**Integrations** — generated from the 22 existing connectors in `step_handlers.py:259-282`, one node type per connector with per-operation sub-types. **This dict is the current bottleneck: adding a connector requires editing engine code.** Replace it with a registry that connectors self-register into.

### 6.3 Migration of existing step types

| Old | New | Note |
|---|---|---|
| `speak, ask, transfer, end` | `voice.*` | direct, 1:1 |
| `condition` | `core.if` | `on_true`/`on_false` config → `true`/`false` **edges** |
| `loop` | `core.loop` | inline sub-steps → real sub-graph via `loop`/`done` handles |
| `transform` | `core.set` + expressions | `data_mapper` becomes the expression function library |
| `delay` | `core.wait` | now durable |
| `webhook, tool, ai, action` | `http.request`, `tool.call`, `ai.completion`, `<connector>.<op>` | |

A `migrate_v1_to_v2(steps) -> graph` function walks the ordered array, emits one node per step, and creates edges from `next_step_id` / `on_true` / `on_false` / array order. Positions are assigned by auto-layout. **Round-trip fidelity must be proven against every existing production workflow before cutover** — write the migration, run it against a prod snapshot, execute both old and new engines on the same inputs, and diff outputs.

The 10 broken templates (#6) are rewritten by hand as v2 graphs. They are currently non-functional, so there is nothing to preserve.

---

## 7. Execution, Debugging & Observability

### 7.1 Live execution view

WebSocket stream (`/ws/executions/{id}`, reusing the existing WS infrastructure) pushing node-level events. The canvas animates: running nodes pulse, succeeded go green, failed go red with an error badge, skipped dim out. Edges animate as data flows. Clicking any node opens its actual input/output for that run.

Cap the event rate server-side (batch at ~10 Hz) — a 500-node run streaming per-item events will otherwise saturate the socket.

### 7.2 Execution history

Replaces the 404 link at `[id]/page.tsx:485`. Filterable list (status, trigger, date, duration), each row opening a **read-only canvas replay** with full per-node data. Actions: retry from start, retry from failed node, copy input, open in editor at that version.

### 7.3 Debugging tools

- **Run single node** — executes one node with upstream data from the last run.
- **Run from here** — partial execution of a subgraph.
- **Pin data** — freeze a node's output for development so downstream work doesn't re-hit live APIs. Pinned nodes are visually marked and **pinning is ignored in production runs**.
- **Expression console** — evaluate an expression against the current run's data.
- **Step-through mode** — pause before each node.
- **Diff view** between two versions.

### 7.4 Production observability

Structured logs with `execution_id`/`node_id` correlation; OpenTelemetry spans per node execution; metrics for `executions_total{status}`, `node_duration_seconds{type}`, `queue_depth`, `wait_backlog`. Alerting on failure-rate spikes and queue depth. **Populate `WorkflowExecution.cost`** — it is summed at `workflows.py:701` and never assigned, so every stats page reads 0 today.

---

## 8. Performance & Scale

**Frontend**

| Concern | Approach |
|---|---|
| >200 nodes | `onlyRenderVisibleElements`, virtualized rendering |
| Re-render storms | Zustand with fine-grained selectors; node components `memo`'d on data identity |
| Drag lag | Position updates local during drag, committed on drag-end |
| Large payload display | Virtualized JSON tree, truncate >1 MB with "load full" |
| Bundle | Canvas route lazy-loaded; node config forms code-split per category |

Set explicit targets and hold them in CI: 60fps pan/zoom at 200 nodes, <100ms node-add, <2s load for a 500-node workflow.

**Backend**

- Bounded per-execution node concurrency (default 10) and per-org concurrent-execution caps.
- Separate Celery queues by expected duration; dedicated queue for `wait` resumption.
- Stream node results to `workflow_node_executions` incrementally; never hold a whole run in memory.
- Index `(workflow_id, started_at desc)` and `(status, heartbeat_at)`.
- Partition `workflow_node_executions` by month; nightly retention job.
- Rate-limit outbound calls per connector per org.

---

## 9. Phased Roadmap

Estimates assume one full-time engineer; parallelizable across two (frontend/backend split) from Phase 2 onward.

### Phase 0 — Stabilization *(3–5 days, do first, ship independently)*

Not part of the rebuild, but shipping the rebuild on top of these is not advisable.

1. Fix the `or_` import → `GET /workflows?search=` 500 (#7).
2. Fix cross-tenant trigger execution: scope `process_event` by organization; authenticate/scope the three trigger endpoints (#16).
3. Fix the scheduler's session-lifetime bug and task GC (#8); fix duplicate cron firing (#9).
4. Wire up `TriggerValidator` on create/update (#6).
5. Add a stranded-execution reaper (#13).
6. Remove or fix the dead links and the hardcoded agent dropdown (#24, #25).

### Phase 1 — Graph foundation *(2–3 weeks)*

Schema v2, new tables, `migrate_v1_to_v2` with round-trip proof, DAG scheduler replacing the linear walker, node descriptor registry, connector self-registration replacing the hardcoded dict.

**Exit criteria:** every existing production workflow migrates and produces byte-identical output under the new engine.

### Phase 2 — Visual canvas *(3–4 weeks)*

React Flow v12 migration (all 11 files, drop v10 + v11), canvas shell, drag-drop that actually works, edge creation, node palette with search, config panel with descriptor-driven forms, undo/redo on a working history implementation, autosave + unsaved guard, save-time validation.

**Exit criteria:** a user can build, save, and run a branching workflow entirely on the canvas.

### Phase 3 — Execution UX *(2–3 weeks)*

Live WS execution view, execution history with replay, run-single-node, run-from-here, pin data, error output handles, per-node retry/timeout config, durable `wait`.

### Phase 4 — Expressions & data *(2–3 weeks)*

Shared expression grammar + sandboxed evaluators (Python AST-based, JS), `data_mapper` transformations exposed as the function library, expression editor with autocomplete, data picker tree, live resolved preview.

### Phase 5 — Advanced control flow *(2–3 weeks)*

Switch (n-way), Merge with modes, Loop Over Items, Split Out, Aggregate, sub-workflows, error-trigger workflows, parallel branch execution, concurrency limits.

### Phase 6 — Polish & scale *(2–3 weeks)*

Auto-layout, sticky notes, groups, cross-tab copy/paste, templates rewritten as v2 graphs, versioning UI with diff and rollback, performance hardening against the stated targets, accessibility pass, observability and cost tracking.

**Total: ~14–19 weeks** for the full scope. Phases 1–3 (~8–10 weeks) deliver something already dramatically better than today and are a defensible v1 cut.

---

## 10. Recommended Libraries

| Need | Choice | Why |
|---|---|---|
| Canvas | `@xyflow/react` v12 | Successor to both packages already present; handles, minimap, controls built in |
| Auto-layout | `elkjs` | Best layered-DAG quality; runs in a worker |
| Canvas state | `zustand` | Already a dependency; selector granularity matters at scale |
| Forms | `react-hook-form` + `zod` | Already dependencies; descriptor → schema → form |
| Expression editor | CodeMirror 6 | Autocomplete, inline preview widgets, small |
| Server state | `@tanstack/react-query` | Already a dependency |
| DnD | React Flow native + HTML5 DnD | No extra library needed |
| Queue | Celery | Already deployed; see §3.4 caveats |
| Scheduling | Celery Beat + `croniter` | `croniter` already used |
| JS sandbox (Code node) | `deno` subprocess or `isolated-vm` | Never `eval` in-process |
| Python expressions | Custom AST evaluator | Replaces `data_mapper.py:628` `eval()` |
| Tracing | OpenTelemetry | Standard, vendor-neutral |
| Graph tests | `hypothesis` | Property-test the scheduler against random DAGs |

**Architectural patterns:** descriptor-driven nodes (n8n), item-based data flow (Make), event-sourced execution log, CQRS split between the draft graph JSON and queried execution tables, and a strict shared-schema contract between frontend and backend for both node descriptors and expression grammar.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| Migration breaks live workflows | Dual-run old and new engines on a prod snapshot; diff outputs before cutover; keep v1 engine behind a flag for one release |
| Expression evaluator diverges frontend/backend | Single spec + shared fixture corpus run against both in CI |
| Celery redelivery re-runs side effects | Persist node completion before ack; idempotency key `(execution_id, node_id, run_index)` |
| Canvas performance regresses as node count grows | Perf budget enforced in CI on a 200- and 500-node fixture |
| Scope creep — this is a large surface | Phases 1–3 are the committed v1; 4–6 are re-evaluated after |
| Security debt carried into the rewrite | Phase 0 is a hard prerequisite, shipped and verified first |

---

## 12. Open Questions

1. **Do we migrate v1 workflows, or run both engines side by side?** Recommendation: migrate, with the v1 engine retained behind a flag for one release.
2. **Should the agent call-flow builder and the workflow builder converge onto one canvas?** They have disjoint node vocabularies today but identical infrastructure needs. Recommendation: shared canvas + descriptor system, separate node catalogues.
3. **Is a `Code` node in scope?** It is a large security surface (needs a real sandbox) but is the single most-used node in n8n. Recommendation: defer to Phase 5, decide on sandbox tech first.
4. **What are the actual scale numbers?** Nodes per workflow, executions per day, peak concurrency. The performance targets in §8 are estimates and should be replaced with measured requirements.
5. **Retention policy for execution data?** Drives the partitioning and storage design in §3.2.
