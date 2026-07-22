"""
Sandbox for the Code node.

Runs user-supplied Python in a **separate process** with hard OS limits (CPU
time, memory, wall clock) and a restricted set of builtins. Input is handed in
as a JSON object; the script's returned value comes back as JSON.

## Threat model — read this before relying on it

The subprocess enforces, via ``resource`` rlimits and a kill timer:

- CPU time (``RLIMIT_CPU``) — stops an infinite ``while True``.
- Address space (``RLIMIT_AS``) — stops a memory bomb.
- Wall-clock timeout — stops a sleeping / blocked script.
- Dangerous builtins removed — no ``open``, ``eval``, ``exec``, ``__import__``,
  ``compile``, ``input``.

It does **NOT** provide OS-level isolation. A determined attacker who can import
a module the allowlist permits could still touch the filesystem or network. For
a single-tenant / trusted-operator deployment this is an acceptable boundary.
For untrusted multi-tenant use, run the whole app (or at least this subprocess)
inside a container with seccomp / network namespaces — this module is designed
to slot behind that without change.
"""
import asyncio
import json
import logging
import os
import sys
import textwrap
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 5
DEFAULT_MEMORY_MB = 128
MAX_OUTPUT_BYTES = 1_000_000  # 1 MB cap on the returned JSON

# Modules a script may import. Kept deliberately small and side-effect free.
ALLOWED_MODULES = {
    "json", "math", "re", "datetime", "random", "statistics",
    "itertools", "functools", "collections", "string", "textwrap",
    "base64", "hashlib", "uuid", "decimal", "urllib.parse",
}


class SandboxError(Exception):
    """Raised when sandboxed code fails or is rejected."""


# The runner is written to a temp file and executed by a fresh interpreter. It
# sets rlimits *inside* the child (so they bind the child, not the parent),
# installs a restricted import hook and builtins, reads {input} from stdin, runs
# the user code with `input`/`items` in scope, and prints the result as JSON.
_RUNNER = textwrap.dedent(
    '''
    import sys, json, resource, builtins

    MEM_BYTES = {mem_bytes}
    CPU_SECONDS = {cpu_seconds}
    ALLOWED = {allowed!r}

    # Bind limits to this process. Address space caps memory; CPU caps busy loops.
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEM_BYTES, MEM_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
    except (ValueError, OSError):
        pass

    _real_import = builtins.__import__

    def _guarded_import(name, *args, **kwargs):
        root = name.split(".")[0]
        if name in ALLOWED or root in ALLOWED:
            return _real_import(name, *args, **kwargs)
        raise ImportError("import of %r is not allowed in the Code node" % name)

    # A minimal builtins set: no open/eval/exec/compile/input/__import__ except
    # our guarded importer.
    _safe_names = [
        "abs","all","any","bool","dict","enumerate","filter","float","format",
        "frozenset","int","isinstance","issubclass","len","list","map","max",
        "min","print","range","repr","reversed","round","set","slice","sorted",
        "str","sum","tuple","zip","True","False","None","bytes","bytearray",
        "hex","oct","bin","chr","ord","divmod","pow","hasattr","getattr","type",
        "Exception","ValueError","KeyError","IndexError","TypeError",
    ]
    safe_builtins = {{k: getattr(builtins, k) for k in _safe_names if hasattr(builtins, k)}}
    safe_builtins["__import__"] = _guarded_import

    raw = sys.stdin.read()
    payload = json.loads(raw) if raw else {{}}
    user_code = payload.get("code", "")
    data = payload.get("input", {{}})

    scope = {{
        "__builtins__": safe_builtins,
        "input": data,          # the workflow context passed in
        "items": data,          # alias, matches n8n phrasing
        "result": None,
    }}

    try:
        exec(user_code, scope)
    except Exception as e:
        print(json.dumps({{"__sandbox_error__": "%s: %s" % (type(e).__name__, e)}}))
        sys.exit(0)

    # A script communicates back by assigning `result` or defining `main()`.
    out = scope.get("result")
    if out is None and callable(scope.get("main")):
        try:
            out = scope["main"](data)
        except Exception as e:
            print(json.dumps({{"__sandbox_error__": "%s: %s" % (type(e).__name__, e)}}))
            sys.exit(0)

    try:
        encoded = json.dumps(out, default=str)
    except (TypeError, ValueError) as e:
        print(json.dumps({{"__sandbox_error__": "result is not JSON serialisable: %s" % e}}))
        sys.exit(0)

    print(encoded)
    '''
)


async def run_code(
    code: str,
    data: Dict[str, Any],
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    memory_mb: int = DEFAULT_MEMORY_MB,
) -> Any:
    """
    Execute user code in the sandbox and return its result.

    Args:
        code: The Python source to run. It may assign ``result`` or define
            ``main(input)``; ``input``/``items`` hold the passed-in data.
        data: JSON-serialisable input made available to the script.
        timeout_seconds: Wall-clock ceiling.
        memory_mb: Address-space ceiling.

    Returns:
        The script's returned value (any JSON type).

    Raises:
        SandboxError: On timeout, a runtime error, or a policy violation.
    """
    if not code or not code.strip():
        raise SandboxError("Code node has no code")

    runner = _RUNNER.format(
        mem_bytes=memory_mb * 1024 * 1024,
        cpu_seconds=max(1, timeout_seconds),
        allowed=sorted(ALLOWED_MODULES),
    )

    payload = json.dumps({"code": code, "input": data}).encode()

    # A fresh interpreter with -I (isolated: ignore env vars, user site) so the
    # child cannot be influenced by PYTHON* env or a writable site-packages.
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-I", "-c", runner,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        # New session so we can kill the whole process group on timeout.
        start_new_session=True,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(payload), timeout=timeout_seconds + 1
        )
    except asyncio.TimeoutError:
        _kill(proc)
        raise SandboxError(f"Code timed out after {timeout_seconds}s")

    if proc.returncode and proc.returncode != 0:
        # Non-zero without our JSON error usually means a limit killed it.
        detail = (stderr or b"").decode(errors="replace").strip()
        if "MemoryError" in detail:
            raise SandboxError("Code exceeded its memory limit")
        # A signal kill (negative return code) means an rlimit stopped it —
        # SIGXCPU/SIGKILL for CPU, SIGKILL for the address-space cap.
        if proc.returncode < 0:
            raise SandboxError("Code exceeded its time or memory limit")
        raise SandboxError(detail or f"Code exited with status {proc.returncode}")

    raw = (stdout or b"").strip()
    if len(raw) > MAX_OUTPUT_BYTES:
        raise SandboxError("Code produced too much output")

    if not raw:
        return None

    try:
        result = json.loads(raw.decode())
    except (ValueError, UnicodeDecodeError):
        # The script printed something that wasn't our JSON line.
        text = raw.decode(errors="replace")
        raise SandboxError(f"Code did not return valid output: {text[:200]}")

    if isinstance(result, dict) and "__sandbox_error__" in result:
        raise SandboxError(result["__sandbox_error__"])

    return result


def _kill(proc: "asyncio.subprocess.Process") -> None:
    """Kill the subprocess and its process group."""
    try:
        os.killpg(os.getpgid(proc.pid), 9)
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass
