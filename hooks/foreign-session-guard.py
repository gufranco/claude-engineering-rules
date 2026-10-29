#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.audit_log import record as audit  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload, tool_input_of  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402
from _lib.knowledge_notes import in_vault  # noqa: E402
from _lib.live_sessions import LiveSession, owner_of, sessions, sessions_dir  # noqa: E402

HOOK = "foreign-session-guard"
ENV_DISABLE = "FOREIGN_SESSION_GUARD_DISABLE"
PATH_KEYS = ("file_path", "notebook_path")
WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

REASON = (
    "{path} is inside {cwd}, where another live Claude Code session works "
    "({name}, {session}, {status}). That session reports a file changed in its "
    "tree while one of its commands runs as its own change, and its next edit "
    "can collide with this one. Do not write there, and do not retry this write "
    "another way. Give the user a prompt to paste into session {name}, which "
    "adds the work to that session's queue. The prompt names {cwd}; lists each "
    "change as a numbered item with the files it touches; lists what already "
    "landed there, for that session to verify only; names the verification "
    "commands to run; and says what its final reply must list.\n"
    "Rule: rules/agent-operating-limits.md"
)


def _skipped() -> bool:
    if not should_run(HOOK):
        return True
    if os.environ.get(ENV_DISABLE) == "1":
        audit(hook=HOOK, decision="bypass", bypass_env=ENV_DISABLE)
        return True
    return is_bypassed(HOOK)


def _target(tool_input: dict[str, object]) -> str:
    values = [tool_input.get(key) for key in PATH_KEYS]
    return next((value for value in values if isinstance(value, str) and value), "")


def _deny(path: str, owner: LiveSession) -> int:
    reason = REASON.format(
        path=path,
        cwd=owner.cwd,
        name=owner.name or "unnamed",
        session=owner.session_id[:8],
        status=owner.status or "unknown status",
    )
    decision = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }
    print(json.dumps({"hookSpecificOutput": decision}))
    audit(hook=HOOK, decision="deny", tool="Write", command_excerpt=path[:240])
    return 0


def main() -> int:
    if _skipped():
        return 0
    payload = read_hook_payload(HOOK)
    path = _target(tool_input_of(payload))
    if payload.get("tool_name") not in WRITE_TOOLS or not path or in_vault(path):
        return 0
    cwd = str(payload.get("cwd") or os.getcwd())
    own = str(payload.get("session_id") or "")
    owner = owner_of(path, cwd, own, sessions(sessions_dir()))
    return _deny(path, owner) if owner is not None else 0


if __name__ == "__main__":
    sys.exit(main())
