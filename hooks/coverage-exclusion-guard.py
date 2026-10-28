#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import cast

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.coverage_exclusion import Action, Verdict, verdict_for  # noqa: E402
from _lib.edit_resolution import resolved_change  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402

HOOK = "coverage-exclusion-guard"
BYPASS_ENV = "COVERAGE_EXCLUSION_GUARD_DISABLE"

BLOCK_MESSAGE = (
    "BLOCKED: {path} lowers the coverage bar.\n\n"
    "{problems}\n\n"
    "Every measured file stays at 100% statements, branches, functions, and\n"
    "lines, with no exclusion directive and no threshold under 100. A line no\n"
    "test can reach is dead code to delete, a hidden dependency to inject, or a\n"
    "defensive check to move to the boundary.\n\n"
    "Rule: rules/testing.md\n"
    f"Bypass for a genuine false positive: export {BYPASS_ENV}=1"
)

ASK_MESSAGE = (
    "{path} adds coverage exclusion entries: {problems}. Approve only when each "
    "path is generated or vendored code. Rule: rules/testing.md"
)


def _block(path: str, verdict: Verdict) -> int:
    problems = "\n".join(f"  - {problem}" for problem in verdict.problems)
    print(BLOCK_MESSAGE.format(path=path, problems=problems), file=sys.stderr)
    return 2


def _ask(path: str, verdict: Verdict) -> int:
    reason = ASK_MESSAGE.format(path=path, problems="; ".join(verdict.problems))
    decision = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(decision))
    return 0


def main() -> int:
    if os.environ.get(BYPASS_ENV) == "1" or is_bypassed(HOOK):
        return 0
    payload = read_hook_payload(HOOK)
    tool_input = cast("dict[str, object]", payload["tool_input"])
    change = resolved_change(str(payload.get("tool_name", "")), tool_input)
    if change is None:
        return 0
    verdict = verdict_for(change.path, change.before, change.after)
    if verdict.action is Action.BLOCK:
        return _block(change.path, verdict)
    if verdict.action is Action.ASK:
        return _ask(change.path, verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
