#!/usr/bin/env python3
"""Warn when an edit lands outside the file list of the active spec plan.

Triggers PreToolUse on Write, Edit, MultiEdit. Looks for the most recently
modified `specs/<date>-<slug>/plan.md` (or `.claude/specs/...`) that has
been touched within the last 60 minutes. If found, parses the plan body for
a "Task breakdown" or "## Tasks" section and extracts every file path
mentioned in backticks. If the current edit target is not in that list, the
hook emits an advisory (exit 2 with permissionDecision=ask, which the
harness treats as an interrupt the model must explicitly acknowledge).

This is NOT a hard block. Files that legitimately must be edited outside
the declared scope (companion test files, config side-effects) can be
acknowledged.

Bypass: SCOPE_GUARD_DISABLE=1 in the parent shell.

Enforces: rules/surgical-edits.md and the /plan spec folder convention.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


PLAN_WINDOW_SECONDS = 60 * 60  # active within last 60 min

SPEC_GLOBS = (
    "specs/*/plan.md",
    ".claude/specs/*/plan.md",
)

BACKTICK_PATH = re.compile(r"`([^`\s]+\.[a-zA-Z0-9]+|[^`\s]+/[^`\s]*)`")

from _lib.bypass import is_bypassed  # noqa: E402



def find_active_plan(cwd: Path) -> Path | None:
    """Return the most recently modified plan.md within the freshness window."""
    candidates: list[tuple[float, Path]] = []
    now = time.time()
    cursor = cwd
    for _ in range(5):  # walk up bounded
        for pattern in SPEC_GLOBS:
            for p in cursor.glob(pattern):
                try:
                    mtime = p.stat().st_mtime
                except OSError:
                    continue
                if now - mtime <= PLAN_WINDOW_SECONDS:
                    candidates.append((mtime, p))
        if cursor == cursor.parent:
            break
        cursor = cursor.parent
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def extract_declared_paths(plan_text: str) -> set[str]:
    """Extract every backtick-quoted path from the plan body."""
    paths: set[str] = set()
    for match in BACKTICK_PATH.finditer(plan_text):
        token = match.group(1)
        # Filter out non-path tokens (env vars, flags, function names)
        if token.startswith("-") or "=" in token:
            continue
        if "/" not in token and "." not in token:
            continue
        paths.add(token)
    return paths


def is_in_scope(target: Path, declared: set[str]) -> bool:
    """True if target matches any declared path or lives under a declared dir."""
    target_str = str(target)
    target_name = target.name
    for decl in declared:
        if decl in target_str:
            return True
        if decl == target_name:
            return True
        # Treat directories as prefixes
        if decl.endswith("/") and decl.rstrip("/") in target_str:
            return True
    return False


def emit_advisory(reason: str, file_path: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stderr.write(reason)
    _audit(
        hook="scope-guard",
        decision="ask",
        decision_class="warn",
        reason=reason[:200],
        file_path=file_path,
        tool="Edit",
    )
    sys.exit(2)


def main() -> int:
    if os.environ.get("SCOPE_GUARD_DISABLE") == "1":
        return 0
    if is_bypassed("scope-guard"):
        return 0

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_name = data.get("tool_name", "")
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        return 0

    tool_input = data.get("tool_input") or {}
    file_path_str = tool_input.get("file_path", "")
    if not file_path_str:
        return 0

    cwd_str = data.get("cwd", os.getcwd())
    cwd = Path(cwd_str)

    plan_path = find_active_plan(cwd)
    if plan_path is None:
        return 0

    try:
        plan_text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return 0

    declared = extract_declared_paths(plan_text)
    if not declared:
        return 0

    target = Path(file_path_str)
    if is_in_scope(target, declared):
        return 0

    # Always allow edits to the plan/spec folder itself
    if str(plan_path.parent) in str(target):
        return 0

    reason = (
        f"ASK: editing `{target.name}` which is not listed in the active "
        f"plan `{plan_path}`.\n"
        f"Rule: ~/.claude/rules/surgical-edits.md.\n"
        f"If this edit is necessary, confirm by retrying. To suppress "
        f"this gate: set SCOPE_GUARD_DISABLE=1."
    )
    emit_advisory(reason, str(target))
    return 2  # unreachable


if __name__ == "__main__":
    sys.exit(main())
