"""
JavaScript sandbox for the Code node.

Runs user-supplied JavaScript in a **separate Node.js process** using Node's
built-in ``vm`` module, mirroring the Python sandbox's model:

- The user code runs in a fresh ``vm`` context — no ``require``, no ``process``,
  no ``global``, no filesystem or network module reachable.
- ``vm.runInNewContext(..., {timeout})`` enforces a wall-clock CPU limit,
  stopping an infinite loop.
- ``--max-old-space-size`` caps heap memory.
- Input is handed in as ``input`` / ``items``; the script returns data by
  assigning ``result`` or defining ``main(input)``.

## Threat model — same boundary as the Python sandbox

Node's ``vm`` is **not** a hardened security boundary on its own (a determined
script can attempt context escapes). It stops infinite loops, memory bombs, and
casual module access, which is the right level for a trusted-operator
deployment. For untrusted multi-tenant use, run the whole process inside a
container with seccomp / network namespaces — this module slots behind that
unchanged.
"""
import asyncio
import json
import logging
import os
import shutil
import textwrap
from typing import Any, Dict

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 5
DEFAULT_MEMORY_MB = 128
MAX_OUTPUT_BYTES = 1_000_000


class JSSandboxError(Exception):
    """Raised when sandboxed JavaScript fails or is rejected."""


# The runner reads {code, input} as JSON from stdin, runs the user code in a
# locked-down vm context, and prints the result as a single JSON line. console
# output is captured (and dropped) so a stray console.log can't corrupt the
# result line.
_RUNNER = textwrap.dedent(
    """
    const vm = require('vm');

    let raw = '';
    process.stdin.on('data', (c) => (raw += c));
    process.stdin.on('end', () => {
      let payload;
      try { payload = JSON.parse(raw || '{}'); }
      catch (e) { emit({ __sandbox_error__: 'bad input: ' + e.message }); return; }

      const userCode = payload.code || '';
      const data = payload.input || {};

      // A minimal, side-effect-free context. No require/process/global.
      const sandbox = {
        input: data,
        items: data,
        result: undefined,
        JSON, Math, Date, Object, Array, String, Number, Boolean,
        parseInt, parseFloat, isNaN, isFinite,
        console: { log() {}, error() {}, warn() {}, info() {} },
      };

      const timeoutMs = Number(payload.timeout_ms) || 5000;

      let out;
      try {
        vm.createContext(sandbox);
        vm.runInContext(userCode, sandbox, { timeout: timeoutMs });

        out = sandbox.result;
        if (out === undefined && typeof sandbox.main === 'function') {
          out = sandbox.main(data);
        }
      } catch (e) {
        const msg = e && e.message ? e.message : String(e);
        // vm surfaces a timeout as a specific error.
        if (/script execution timed out/i.test(msg)) {
          emit({ __sandbox_error__: 'Code timed out' });
        } else {
          emit({ __sandbox_error__: (e && e.name ? e.name + ': ' : '') + msg });
        }
        return;
      }

      try {
        emit(out === undefined ? null : out);
      } catch (e) {
        emit({ __sandbox_error__: 'result is not JSON serialisable: ' + e.message });
      }
    });

    function emit(value) {
      process.stdout.write(JSON.stringify(value === undefined ? null : value));
    }
    """
)


async def run_js(
    code: str,
    data: Dict[str, Any],
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    memory_mb: int = DEFAULT_MEMORY_MB,
) -> Any:
    """
    Execute user JavaScript in the sandbox and return its result.

    Args:
        code: JavaScript source. May assign ``result`` or define
            ``main(input)``; ``input``/``items`` hold the passed-in data.
        data: JSON-serialisable input made available to the script.
        timeout_seconds: Wall-clock ceiling.
        memory_mb: Heap ceiling (Node ``--max-old-space-size``).

    Returns:
        The script's returned value (any JSON type).

    Raises:
        JSSandboxError: On timeout, a runtime error, or a policy violation.
    """
    if not code or not code.strip():
        raise JSSandboxError("Code node has no code")

    node = shutil.which("node")
    if not node:
        raise JSSandboxError(
            "JavaScript is not available on the server (Node.js is not installed)"
        )

    payload = json.dumps(
        {"code": code, "input": data, "timeout_ms": timeout_seconds * 1000}
    ).encode()

    proc = await asyncio.create_subprocess_exec(
        node,
        f"--max-old-space-size={memory_mb}",
        "-e",
        _RUNNER,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(payload), timeout=timeout_seconds + 2
        )
    except asyncio.TimeoutError:
        _kill(proc)
        raise JSSandboxError(f"Code timed out after {timeout_seconds}s")

    if proc.returncode and proc.returncode != 0:
        detail = (stderr or b"").decode(errors="replace").strip()
        if "out of memory" in detail.lower() or proc.returncode < 0:
            raise JSSandboxError("Code exceeded its time or memory limit")
        raise JSSandboxError(detail.splitlines()[-1] if detail else "Code failed")

    raw = (stdout or b"").strip()
    if len(raw) > MAX_OUTPUT_BYTES:
        raise JSSandboxError("Code produced too much output")
    if not raw:
        return None

    try:
        result = json.loads(raw.decode())
    except (ValueError, UnicodeDecodeError):
        raise JSSandboxError(
            f"Code did not return valid output: {raw.decode(errors='replace')[:200]}"
        )

    if isinstance(result, dict) and "__sandbox_error__" in result:
        raise JSSandboxError(result["__sandbox_error__"])

    return result


def _kill(proc: "asyncio.subprocess.Process") -> None:
    try:
        os.killpg(os.getpgid(proc.pid), 9)
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass
