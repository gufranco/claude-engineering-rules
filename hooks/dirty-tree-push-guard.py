#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.audit_log import record as _audit  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402

HOOK = "dirty-tree-push-guard"
GIT_TIMEOUT_S = 10.0
LISTED_FILES = 5

GIT_PUSH = re.compile(r"\bgit\s+(?:-C\s+(\"[^\"]+\"|'[^']+'|\S+)\s+)?push\b")
LEADING_CD = re.compile(r"^\s*cd\s+(\"[^\"]+\"|'[^']+'|[^\s;&|]+)\s*&&")
STAGES_EVERYTHING = re.compile(
    r"\bgit\s+add\s+(?:-A\b|--all\b|\.(?=\s|$|[;&|]))"
    r"|\bgit\s+commit\b[^;&|]*?(?:\s-[a-zA-Z]*a[a-zA-Z]*\b|\s--all\b)"
)


def _unquote(value: str) -> str:
    parts = shlex.split(value)
    return parts[0] if parts else value


def target_directory(command: str, cwd: str) -> str:
    push = GIT_PUSH.search(command)
    if push is not None and push.group(1):
        return os.path.join(cwd, os.path.expanduser(_unquote(push.group(1))))
    cd = LEADING_CD.match(command)
    if cd is not None:
        return os.path.join(cwd, os.path.expanduser(_unquote(cd.group(1))))
    return cwd


def modified_tracked_files(directory: str) -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", "-C", directory, "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return [line[3:] for line in result.stdout.splitlines() if line.strip()]


def _block_reason(files: list[str]) -> str:
    listed = ", ".join(files[:LISTED_FILES])
    more = f" and {len(files) - LISTED_FILES} more" if len(files) > LISTED_FILES else ""
    return (
        f"BLOCKED: `git push` with modified tracked files: {listed}{more}. "
        "The pushed commit is not the tree that was tested, and a change left "
        "out of the commit, such as a test that matches a deleted file, breaks CI.\n"
        "Fix: commit or restore those files, check `git status`, then push alone. "
        "A blocked call ran nothing: repeat any staging it carried.\n"
        "Bypass (one-off, when the files belong to other work): set "
        "DIRTY_TREE_PUSH_GUARD_DISABLE=1 in parent shell."
    )


def emit_block(reason: str, command: str) -> int:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stderr.write(reason)
    _audit(
        hook=HOOK,
        decision="block",
        decision_class="block",
        reason=reason[:200],
        tool="Bash",
        command_excerpt=command[:200],
    )
    return 2


def main() -> int:
    if os.environ.get("DIRTY_TREE_PUSH_GUARD_DISABLE") == "1" or is_bypassed(HOOK):
        return 0
    data = read_hook_payload(HOOK)
    if data.get("tool_name") != "Bash":
        return 0
    command = (data.get("tool_input") or {}).get("command", "")
    if not GIT_PUSH.search(command) or STAGES_EVERYTHING.search(command):
        return 0
    directory = target_directory(command, data.get("cwd") or os.getcwd())
    files = modified_tracked_files(directory)
    if not files:
        return 0
    return emit_block(_block_reason(files), command)


if __name__ == "__main__":
    sys.exit(main())
