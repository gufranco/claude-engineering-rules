"""TypeScript Project Service integration (plan item 394).

When `MUTATION_METHOD_TS_PROJECT_SERVICE=1` and Node.js with the
`typescript` package (>= 5.6) are available, the hook spawns a
long-running Node helper that uses the TypeScript Project Service to
answer narrow type questions about each mutation site:

    - Is the receiver typed as `readonly T[]` / `ReadonlyArray<T>` /
      `ReadonlyMap` / `ReadonlySet`? Skip the finding because the
      compiler already rejects it.
    - Is the receiver a `URLSearchParams`, `Headers`, or `FormData`?
      Keep the finding even when the source looks ambiguous.
    - Is the receiver a `TypedArray` subtype (Uint8Array, Int32Array,
      etc.)? Apply hot-path semantics regardless of directory.

The integration is optional. When the env var is unset, or Node /
typescript are not on PATH, the hook falls back to regex-only behavior
with no penalty. Detection accuracy improves quietly when the
integration is available; it never blocks the hook from running.

Public API:

    is_enabled() -> bool
        True only when MUTATION_METHOD_TS_PROJECT_SERVICE=1.

    is_available() -> bool
        True when the helper subprocess can start (node + typescript
        present, helper script readable).

    query_receiver_type(file_path, line, col) -> dict | None
        Returns a small dict describing the receiver type at the
        mutation site or None when unavailable. Cached per
        (file_path, line, col).

    shutdown() -> None
        Terminate the helper subprocess. Safe to call multiple times.

Wire protocol (NDJSON over stdio):

    request:   {"id":"<uuid>","file":"<abs>","line":<n>,"col":<n>}
    response:  {"id":"<uuid>","type":"<name>","readonly":<bool>,
                "kind":"array|map|set|typed-array|url-params|...",
                "error":<str?>}

Latency budget: the helper must answer in under 200ms p95 or the
caller drops the request and continues with regex-only analysis.

Design notes:

  - One subprocess per hook invocation. Project Service caches the
    project graph, so subsequent queries within the same run are fast.
  - Fail closed: any subprocess error returns None and disables
    further queries for the remainder of the invocation.
  - Type information is advisory. The hook never relies on it for
    correctness, only for confidence tuning and noise reduction.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from typing import Any

_HELPER_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "ts_project_service.js",
)
_QUERY_TIMEOUT_MS = 200
_TOTAL_BUDGET_MS = 5000

_PROC: subprocess.Popen[str] | None = None
_PROC_LOCK = threading.Lock()
_CACHE: dict[tuple[str, int, int], dict[str, Any] | None] = {}
_DISABLED: bool = False
_START_TS: float = 0.0


def is_enabled() -> bool:
    """True when the env var requests the Project Service."""
    return (os.environ.get("MUTATION_METHOD_TS_PROJECT_SERVICE") or "").strip() == "1"


def is_available() -> bool:
    """True only when Node and the helper script are both present.

    Does NOT verify the `typescript` package is installed; that check
    happens inside the helper on first request and surfaces as an
    error response.
    """
    if not is_enabled():
        return False
    if not shutil.which("node"):
        return False
    if not os.path.exists(_HELPER_SCRIPT):
        return False
    return True


def _start_helper() -> subprocess.Popen[str] | None:
    """Spawn the long-running Node helper. Returns None on failure."""
    global _PROC, _START_TS
    with _PROC_LOCK:
        if _PROC is not None:
            return _PROC
        if not is_available():
            return None
        try:
            _PROC = subprocess.Popen(
                ["node", _HELPER_SCRIPT],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            _START_TS = time.perf_counter()
        except (OSError, subprocess.SubprocessError):
            _PROC = None
        return _PROC


def _budget_exhausted() -> bool:
    """True when the total Project Service budget has been used up."""
    if _START_TS <= 0.0:
        return False
    elapsed_ms = (time.perf_counter() - _START_TS) * 1000.0
    return elapsed_ms > _TOTAL_BUDGET_MS


def _disable(reason: str) -> None:
    """Disable further queries and log to stderr via audit."""
    global _DISABLED
    _DISABLED = True
    try:
        import sys

        if (os.environ.get("MUTATION_METHOD_DEBUG") or "").strip() == "1":
            sys.stderr.write(f"ts-project-service: disabled ({reason})\n")
    except Exception:
        pass


def query_receiver_type(file_path: str, line: int, col: int) -> dict[str, Any] | None:
    """Query the receiver type at `file_path:line:col`.

    Returns a dict like
    `{"type": "ReadonlyArray<number>", "readonly": True, "kind": "array"}`
    or None when unavailable. Cached per (path, line, col).
    """
    if _DISABLED or not is_enabled():
        return None
    if _budget_exhausted():
        return None
    key = (file_path, line, col)
    if key in _CACHE:
        return _CACHE[key]
    proc = _start_helper()
    if proc is None or proc.stdin is None or proc.stdout is None:
        _disable("helper start failed")
        return None
    request_id = uuid.uuid4().hex
    payload = json.dumps(
        {
            "id": request_id,
            "file": file_path,
            "line": line,
            "col": col,
        }
    )
    try:
        proc.stdin.write(payload + "\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError):
        _disable("write failed")
        _CACHE[key] = None
        return None
    response = _read_response(proc, request_id)
    if response is None:
        _disable("response timeout or error")
        _CACHE[key] = None
        return None
    if response.get("error"):
        _CACHE[key] = None
        return None
    result = {
        "type": response.get("type") or "",
        "readonly": bool(response.get("readonly")),
        "kind": response.get("kind") or "",
    }
    _CACHE[key] = result
    return result


def _read_response(
    proc: subprocess.Popen[str], request_id: str
) -> dict[str, Any] | None:
    """Read NDJSON responses until one matches `request_id`."""
    if proc.stdout is None:
        return None
    deadline = time.perf_counter() + (_QUERY_TIMEOUT_MS / 1000.0)
    while time.perf_counter() < deadline:
        line = proc.stdout.readline()
        if not line:
            return None
        try:
            payload: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("id") == request_id:
            return payload
    return None


def shutdown() -> None:
    """Terminate the helper subprocess."""
    global _PROC
    with _PROC_LOCK:
        if _PROC is None:
            return
        try:
            if _PROC.stdin is not None and not _PROC.stdin.closed:
                _PROC.stdin.close()
        except OSError:
            pass
        try:
            _PROC.terminate()
            _PROC.wait(timeout=0.5)
        except (subprocess.TimeoutExpired, OSError):
            try:
                _PROC.kill()
            except OSError:
                pass
        _PROC = None
