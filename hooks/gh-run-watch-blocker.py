#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


GH_RUN_WATCH = re.compile(r"\bgh\s+run\s+watch\b")

GH_PR_CHECKS_WATCH = re.compile(r"\bgh\s+pr\s+checks\b[^\n;&|]*?(?:--watch|\s-w\b)")

GH_WORKFLOW_WATCH = re.compile(r"\bgh\s+workflow\s+run\b[^\n;&|]*?--watch")

GLAB_CI_LIVE = re.compile(r"\bglab\s+ci\s+view\b[^\n;&|]*?(?:--live|\s-l\b)")

GLAB_CI_STATUS_WAIT = re.compile(
    r"\bglab\s+ci\s+status\b[^\n;&|]*?(?:--live|--wait|\s-[lw]\b)"
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.shell_segments import mask_literal_text  # noqa: E402


def find_offender(command: str) -> str | None:
    if GH_RUN_WATCH.search(command):
        return "gh run watch"
    if GH_PR_CHECKS_WATCH.search(command):
        return "gh pr checks --watch"
    if GH_WORKFLOW_WATCH.search(command):
        return "gh workflow run --watch"
    if GLAB_CI_LIVE.search(command):
        return "glab ci view --live"
    if GLAB_CI_STATUS_WAIT.search(command):
        return "glab ci status --wait"
    return None


def emit_block(reason: str, command: str) -> None:
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
        hook="gh-run-watch-blocker",
        decision="block",
        decision_class="block",
        reason=reason[:200],
        tool="Bash",
        command_excerpt=command[:200],
    )
    sys.exit(2)


def _block_reason(offender: str) -> str:
    return (
        f"BLOCKED: `{offender}` polls every 3 seconds and burns the GitHub "
        f"API rate budget (~1200 requests/hour).\n"
        f"Rule: ~/.claude/rules/git-workflow.md CI/CD Monitoring.\n"
        f"Fix one of:\n"
        f"  - One-shot snapshot: `gh run view <run-id>`\n"
        f"  - One-shot failure logs: `gh run view <run-id> --log-failed`\n"
        f"  - GitLab one-shot: `glab ci status -F json`\n"
        f"  - Bounded poll loop with `sleep 30` between checks\n"
        f"  - Wait for the run, then read it once.\n"
        f"Before polling, check quota: `gh api rate_limit`. Quota under 500 "
        f"means stop polling entirely.\n"
        f"Bypass (one-off): set GH_RUN_WATCH_DISABLE=1 in parent shell."
    )


def main() -> int:
    if os.environ.get("GH_RUN_WATCH_DISABLE") == "1":
        return 0
    if is_bypassed("gh-run-watch-blocker"):
        return 0

    data = read_hook_payload("gh-run-watch-blocker")

    if data.get("tool_name") != "Bash":
        return 0

    command = (data.get("tool_input") or {}).get("command", "")
    if not command:
        return 0

    offender = find_offender(mask_literal_text(command))
    if offender is None:
        return 0

    emit_block(_block_reason(offender), command)
    return 2


if __name__ == "__main__":
    sys.exit(main())
