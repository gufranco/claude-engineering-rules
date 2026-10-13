from __future__ import annotations

import json
import os
import sys
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
    return (os.environ.get("MUTATION_METHOD_TS_PROJECT_SERVICE") or "").strip() == "1"


def is_available() -> bool:
    if not is_enabled():
        return False
    if not shutil.which("node"):
        return False
    if not os.path.exists(_HELPER_SCRIPT):
        return False
    return True


def _start_helper() -> subprocess.Popen[str] | None:
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
    if _START_TS <= 0.0:
        return False
    elapsed_ms = (time.perf_counter() - _START_TS) * 1000.0
    return elapsed_ms > _TOTAL_BUDGET_MS


def _disable(reason: str) -> None:
    global _DISABLED
    _DISABLED = True
    if (os.environ.get("MUTATION_METHOD_DEBUG") or "").strip() == "1":
        sys.stderr.write(f"ts-project-service: disabled ({reason})\n")


def query_receiver_type(file_path: str, line: int, col: int) -> dict[str, Any] | None:
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
    global _PROC
    with _PROC_LOCK:
        if _PROC is None:
            return
        try:
            if _PROC.stdin is not None and not _PROC.stdin.closed:
                _PROC.stdin.close()
        except OSError as error:
            sys.stderr.write(f"ts-project-service: stdin close failed: {error}\n")
        try:
            _PROC.terminate()
            _PROC.wait(timeout=0.5)
        except (subprocess.TimeoutExpired, OSError):
            try:
                _PROC.kill()
            except OSError as error:
                sys.stderr.write(f"ts-project-service: kill failed: {error}\n")
        _PROC = None
