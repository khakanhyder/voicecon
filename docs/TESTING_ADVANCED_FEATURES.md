# Testing the Advanced Features in the Browser

Step-by-step for the four features: **Code node (Python + JavaScript)**, **live
status streaming**, and **execution history with replay**.

All of these live in the workflow builder. Open any workflow → **Open Builder**.
A good one to use is **[demo] Get crypto price** (it already has real steps).

---

## 1. Code node — JavaScript & Python

**What it does:** runs a Python or JavaScript snippet on the workflow data,
inside a sandbox. A returned object becomes named variables later steps can use.

**How to test:**

1. In the builder, drag a **Code** node (Logic category) onto the canvas.
2. Wire it after the trigger: drag from the trigger's bottom dot to the Code
   node's top dot.
3. Click the Code node. In the right panel you'll now see:
   - a **Language** dropdown (Python / JavaScript),
   - a **dark, syntax-highlighted editor** (keywords, strings, numbers, and
     comments are all colourised — no more single-colour black text).
4. Pick **JavaScript** and enter:
   ```js
   result = { greeting: "hello", doubled: 21 * 2 }
   ```
5. Wire the Code node to an **End** node (or leave it as the last step).
6. Click **Test run** (top right).

**Expected:** the Code node turns green. Open the results panel at the bottom,
expand the Code step — its output shows `{ "greeting": "hello", "doubled": 42 }`.

**Try Python too:** switch Language to Python; the starter code swaps to Python
and highlighting changes. Enter:
```python
result = {"squared": 9 ** 2}
```
Test run → the step shows `{"squared": 81}`.

**Confirm the sandbox is safe** (optional): put this in a JavaScript Code node
and Test run:
```js
result = require("fs").readFileSync("/etc/passwd")
```
Expected: the node turns **red** with an error like *"require is not defined"* —
the sandbox blocked it. An infinite loop (`while(true){}`) fails with a timeout
instead of hanging.

---

## 2. Live status streaming

**What it does:** when you Test run, nodes light up **one by one as they
execute**, instead of all at once at the end.

**How to test:**

1. Open **[demo] Get crypto price** in the builder (it has three real steps,
   so the sequence is visible).
2. Click **Test run**.

**Expected:** watch the canvas — each node shows a **blue spinner while
running**, then turns **green** as it finishes, in order (Fetch the price →
Build the answer). On a branching workflow (like **[demo] Get weather**), the
branch that isn't taken dims out as **skipped**.

**Confirm:** the status moves node-by-node rather than everything flipping green
simultaneously. The "Test run" button shows a spinner until the run completes,
then the results panel opens at the bottom.

> If a node fails, it turns red with the error shown inline on the node.

---

## 3. Execution history + replay

**What it does:** every run is saved; you can browse past runs and replay any of
them on a read-only canvas.

**How to test:**

1. Run a workflow a few times (Test run) so there's history.
2. Go back to the workflow's detail page: **Workflows → click the workflow**.
3. Click **Execution History** (in Quick Actions).

**Expected:**
- A left panel lists every run with its **status, time, duration, and step
  count** (newest first).
- Click any run → the **canvas replays it**: each node shows that run's outcome
  (green/red), and the results panel at the bottom shows every step's output,
  the transcript, and the final data.
- The canvas here is **read-only** — no palette, no editing.
- **Run again** (top right) re-executes the workflow and refreshes the list.

**Confirm:** selecting different runs in the list updates the canvas colours and
the results panel to match that specific run.

---

## Quick reference — expected outcomes

| Feature | Trigger | Confirms working |
|---|---|---|
| JS Code node | Add Code node, pick JavaScript, Test run | Green node, correct output in results |
| Python Code node | Same, pick Python | Green node, correct output |
| Syntax highlighting | Open any Code node | Colourised dark editor, not plain black |
| Sandbox safety | `require(...)` in JS, Test run | Red node with "require is not defined" |
| Live streaming | Test run on a multi-step workflow | Nodes turn blue→green in sequence |
| Branch skip | Test run [demo] Get weather | Untaken branch dims as skipped |
| Execution history | Detail page → Execution History | List of past runs |
| Replay | Click a run in history | Canvas + results reflect that run |

---

## Notes / current limits

- **Sandbox boundary:** both sandboxes stop infinite loops, memory bombs, and
  module/file access, which is right for a trusted deployment. They are not
  container-grade isolation — for untrusted multi-tenant use, run the app inside
  a container.
- **JavaScript needs Node.js** on the server (installed here: Node 22). If it
  were missing, a JS Code node would report that clearly rather than failing
  silently.
- **Live streaming assumes one backend worker** (the run and the socket share a
  process). That's the current setup. Scaling to multiple workers would need a
  Redis pub/sub bridge.
