#!/usr/bin/env python3
"""Block `gh run watch` (polls every 3 seconds, burns GitHub API rate limit).

`gh run watch` polls the workflow run status every 3 seconds. Over an hour
that is ~1200 requests, a quarter of the unauthenticated rate budget. When
combined with `gh pr checks --watch` (same cadence) the budget evaporates.

This hook blocks `gh run watch` and `gh pr checks --watch`. The fix is one
of:
  - `gh run view <id>` for a one-shot snapshot
  - polling loop with a longer interval (`sleep 30` between checks)
  - a single `gh run view --log-failed` after the run completes naturally

The same hook also covers `glab ci view --live` for the GitLab equivalent.

Triggers PreToolUse on Bash. Exit 0 = allow, exit 2 = block.

Bypass: GH_RUN_WATCH_DISABLE=1 in the parent shell.

Enforces: rules/git-workflow.md CI/CD Monitoring section.
"""

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


# `gh run watch ...`
GH_RUN_WATCH = re.compile(r"\bgh\s+run\s+watch\b")

# `gh pr checks ... --watch` or `gh pr checks -w` (where -w is the alias).
GH_PR_CHECKS_WATCH = re.compile(r"\bgh\s+pr\s+checks\b[^\n;&|]*?(?:--watch|\s-w\b)")

# `gh workflow run ... --watch`
GH_WORKFLOW_WATCH = re.compile(r"\bgh\s+workflow\s+run\b[^\n;&|]*?--watch")

# `glab ci view --live`
GLAB_CI_LIVE = re.compile(r"\bglab\s+ci\s+view\b[^\n;&|]*?(?:--live|\s-l\b)")

from _lib.bypass import is_bypassed  # noqa: E402


def find_offender(command: str) -> str | None:
    if GH_RUN_WATCH.search(command):
        return "gh run watch"
    if GH_PR_CHECKS_WATCH.search(command):
        return "gh pr checks --watch"
    if GH_WORKFLOW_WATCH.search(command):
        return "gh workflow run --watch"
    if GLAB_CI_LIVE.search(command):
        return "glab ci view --live"
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


def main() -> int:
    if os.environ.get("GH_RUN_WATCH_DISABLE") == "1":
        return 0
    if is_bypassed("gh-run-watch-blocker"):
        return 0

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if data.get("tool_name") != "Bash":
        return 0

    command = (data.get("tool_input") or {}).get("command", "")
    if not command:
        return 0

    offender = find_offender(command)
    if offender is None:
        return 0

    reason = (
        f"BLOCKED: `{offender}` polls every 3 seconds and burns the GitHub "
        f"API rate budget (~1200 requests/hour).\n"
        f"Rule: ~/.claude/rules/git-workflow.md CI/CD Monitoring.\n"
        f"Fix one of:\n"
        f"  - One-shot snapshot: `gh run view <run-id>`\n"
        f"  - One-shot failure logs: `gh run view <run-id> --log-failed`\n"
        f"  - Bounded poll loop with `sleep 30` between checks\n"
        f"  - Wait for the run, then read it once.\n"
        f"Before polling, check quota: `gh api rate_limit`. Quota under 500 "
        f"means stop polling entirely.\n"
        f"Bypass (one-off): set GH_RUN_WATCH_DISABLE=1 in parent shell."
    )
    emit_block(reason, command)
    return 2  # unreachable


if __name__ == "__main__":
    sys.exit(main())
