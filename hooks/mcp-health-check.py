#!/usr/bin/env python3

from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


from _lib.hook_profile import should_run  # noqa: E402


CACHE_DIR = os.path.expanduser("~/.claude/cache")
STATE_FILE = os.path.join(CACHE_DIR, "mcp-health.json")
LOCK_FILE = os.path.join(CACHE_DIR, "mcp-health.lock")
HOOK = "mcp-health-check"
UNHEALTHY_THRESHOLD = 3
TTL_SECONDS = 5 * 60

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


State = dict[str, dict[str, float]]


def _load_state() -> State:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            loaded = json.load(f)
    except (json.JSONDecodeError, OSError) as error:
        _audit(hook=HOOK, decision="error", reason=f"state unreadable: {error}")
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _save_state(state: State) -> None:
    try:
        handle, temp = tempfile.mkstemp(dir=CACHE_DIR, prefix=".mcp-health.")
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(temp, STATE_FILE)
    except OSError as error:
        _audit(hook=HOOK, decision="error", reason=f"state not saved: {error}")


def _update_state(update: Callable[[State], State]) -> State:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(LOCK_FILE, "a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = _load_state()
        updated = update(state)
        if updated != state:
            _save_state(updated)
        return updated


def _server_name(tool_name: str) -> str:
    parts = tool_name.split("__")
    if len(parts) >= 2 and parts[0] == "mcp":
        return parts[1]
    return ""


def _is_failure(data: dict) -> bool:
    tool_response = data.get("tool_response", {})
    return isinstance(tool_response, dict) and bool(
        tool_response.get("error") or tool_response.get("isError")
    )


def _expire(server: str) -> Callable[[State], State]:
    def update(state: State) -> State:
        info = state.get(server, {})
        stale = time.time() - info.get("last_failure", 0) > TTL_SECONDS
        return (
            {**state, server: {"failures": 0, "last_failure": 0}}
            if stale and info
            else state
        )

    return update


def _record(server: str, failed: bool) -> Callable[[State], State]:
    def update(state: State) -> State:
        info = state.get(server, {"failures": 0, "last_failure": 0})
        if not failed:
            return {**state, server: {**info, "failures": 0}}
        failures = info.get("failures", 0) + 1
        return {**state, server: {"failures": failures, "last_failure": time.time()}}

    return update


def _handle_pre(data: dict) -> int:
    tool_name = data.get("tool_name", "")
    server = _server_name(tool_name)
    if not server:
        return 0
    failures = _update_state(_expire(server)).get(server, {}).get("failures", 0)
    if failures < UNHEALTHY_THRESHOLD:
        return 0
    print(
        f"BLOCKED: MCP server `{server}` is unhealthy ({int(failures)} consecutive "
        f"failures).\nWait at least {TTL_SECONDS // 60} minutes before retrying, or "
        "restart the MCP server. To skip this check for one server outage, register "
        "a TTL-bound pass with `python3 ~/.claude/scripts/bypass.py set "
        "mcp-health-check`; MCP_HEALTH_DISABLE=1 in the parent shell disables it "
        "for the whole session.",
        file=sys.stderr,
    )
    _audit(
        hook=HOOK, decision="block", tool=tool_name, reason=f"server {server} unhealthy"
    )
    return 2


def _handle_post(data: dict) -> int:
    server = _server_name(data.get("tool_name", ""))
    if server:
        _update_state(_record(server, _is_failure(data)))
    return 0


def main() -> None:
    if not should_run("mcp-health-check"):
        sys.exit(0)
    if os.environ.get("MCP_HEALTH_DISABLE") == "1":
        sys.exit(0)
    if is_bypassed("mcp-health-check"):
        sys.exit(0)
    data = read_hook_payload("mcp-health-check")

    tool_name = data.get("tool_name", "")
    if not tool_name.startswith("mcp__"):
        sys.exit(0)

    event = data.get("hook_event_name", "")
    if event == "PreToolUse":
        sys.exit(_handle_pre(data))
    if event == "PostToolUse":
        sys.exit(_handle_post(data))
    sys.exit(0)


if __name__ == "__main__":
    main()
