#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402

HOOK = "gh-short-sha-guard"
FULL_SHA_LENGTH = 40

GH_RUN_LIST_COMMIT = re.compile(
    r"\bgh\s+run\s+list\b[^\n;&|]*?(?:--commit|-c)(?:=|\s+)[\"']?([0-9a-fA-F]+)[\"']?(?=[\s;&|)]|$)"
)


def find_short_sha(command: str) -> str | None:
    for match in GH_RUN_LIST_COMMIT.finditer(command):
        sha = match.group(1)
        if len(sha) < FULL_SHA_LENGTH:
            return sha
    return None


def _block_reason(sha: str) -> str:
    return (
        f"BLOCKED: `gh run list --commit {sha}` passes a {len(sha)}-character SHA. "
        f"The filter matches only the full 40-character SHA, so a short one "
        f"returns zero runs with exit 0 and reads as CI not started or done.\n"
        f'Fix: `gh run list --commit "$(git rev-parse {sha})"`.\n'
        f"Bypass (one-off): set GH_SHORT_SHA_GUARD_DISABLE=1 in parent shell."
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
    if os.environ.get("GH_SHORT_SHA_GUARD_DISABLE") == "1":
        return 0
    if is_bypassed(HOOK):
        return 0

    data = read_hook_payload(HOOK)

    if data.get("tool_name") != "Bash":
        return 0

    command = (data.get("tool_input") or {}).get("command", "")
    if not command:
        return 0

    sha = find_short_sha(command)
    if sha is None:
        return 0

    return emit_block(_block_reason(sha), command)


if __name__ == "__main__":
    sys.exit(main())
