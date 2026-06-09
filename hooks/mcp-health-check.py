#!/usr/bin/env python3
"""Track MCP server health and short-circuit calls to unhealthy servers.

Runs on PreToolUse and PostToolUse for any `mcp__*` tool. State lives at
~/.claude/cache/mcp-health.json.

On PreToolUse:
  - If the server has reached `UNHEALTHY_THRESHOLD` consecutive failures
    within the past `TTL_SECONDS`, block the call with a clear message.
  - Otherwise allow.

On PostToolUse:
  - If the tool returned an error (exit code non-zero or `error` field
    in tool_response), increment the consecutive failure count.
  - On success, reset the failure count.

The intent is to fail fast on a dead MCP server instead of waiting for
each tool call to time out individually.

Exit 0 = allow, exit 2 = block.

Bypass:
  - Set `MCP_HEALTH_DISABLE=1` to skip the check entirely.
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.hook_profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


CACHE_DIR = os.path.expanduser("~/.claude/cache")
STATE_FILE = os.path.join(CACHE_DIR, "mcp-health.json")
UNHEALTHY_THRESHOLD = 3  # consecutive failures before short-circuit
TTL_SECONDS = 5 * 60  # forget failures older than 5 minutes

from _lib.bypass import is_bypassed  # noqa: E402


def _load_state() -> dict[str, dict]:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict[str, dict]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass


def _server_name(tool_name: str) -> str:
    # mcp__github__create_issue -> github
    parts = tool_name.split("__")
    if len(parts) >= 2 and parts[0] == "mcp":
        return parts[1]
    return ""


def _is_failure(data: dict) -> bool:
    """Decide whether a PostToolUse payload represents a failure."""
    tool_response = data.get("tool_response", {})
    if isinstance(tool_response, dict):
        if tool_response.get("error"):
            return True
        if tool_response.get("isError"):
            return True
    if data.get("exit_code") not in (None, 0):
        return True
    return False


def _handle_pre(data: dict, state: dict[str, dict]) -> int:
    tool_name = data.get("tool_name", "")
    server = _server_name(tool_name)
    if not server:
        return 0
    info = state.get(server, {})
    failures = info.get("failures", 0)
    last_failure = info.get("last_failure", 0)
    if failures < UNHEALTHY_THRESHOLD:
        return 0
    if time.time() - last_failure > TTL_SECONDS:
        # Stale failure count. Reset and allow.
        state[server] = {"failures": 0, "last_failure": 0}
        _save_state(state)
        return 0
    print(
        f"BLOCKED: MCP server `{server}` is unhealthy ({failures} consecutive failures).\n",
        file=sys.stderr,
    )
    print(
        f"Wait at least {TTL_SECONDS // 60} minutes before retrying, or restart the\n"
        f"MCP server. Set MCP_HEALTH_DISABLE=1 to bypass once.",
        file=sys.stderr,
    )
    _audit(
        hook="mcp-health-check",
        decision="block",
        tool=tool_name,
        reason=f"server {server} unhealthy",
    )
    return 2


def _handle_post(data: dict, state: dict[str, dict]) -> int:
    tool_name = data.get("tool_name", "")
    server = _server_name(tool_name)
    if not server:
        return 0
    info = state.get(server, {"failures": 0, "last_failure": 0})
    if _is_failure(data):
        info["failures"] = info.get("failures", 0) + 1
        info["last_failure"] = time.time()
    else:
        # Success resets the counter.
        info["failures"] = 0
    state[server] = info
    _save_state(state)
    return 0


def main() -> None:
    if not should_run("mcp-health-check"):
        sys.exit(0)
    if os.environ.get("MCP_HEALTH_DISABLE") == "1":
        sys.exit(0)
    if is_bypassed("mcp-health-check"):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if not tool_name.startswith("mcp__"):
        sys.exit(0)

    event = data.get("hook_event_name", "")
    state = _load_state()

    if event == "PreToolUse":
        sys.exit(_handle_pre(data, state))
    elif event == "PostToolUse":
        sys.exit(_handle_post(data, state))
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
