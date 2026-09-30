#!/usr/bin/env python3
"""Inject a "Resume here" pointer on session start, clear, or compact.

Triggers SessionStart. On every event (startup, clear, compact), the hook
scans for the most recently modified spec plan and checkpoint artifacts in
the current working directory and emits an `additionalContext` block
naming them, so the model knows where the previous session left off
without having to re-discover.

Discovery (in priority order):
  0. <workspace>/PROMPT.md, the continuation prompt in the local project
     workspace (`docs/` or `.work/`, see _lib/project_workspace.py). No
     freshness window: it is always the handoff. Up to 200 lines shown.
  1. checkpoints/<date>.md or .claude/checkpoints/<date>.md (most recent,
     within 7 days)
  2. specs/<date>-<slug>/plan.md, .claude/specs/.../plan.md, or
     <workspace>/plans/<date>-<slug>/plan.md (most recent, within 7 days)
  3. sessions/<date>.md (legacy)

Output: a single context block listing the file paths and the first ~30
lines of the most relevant artifact.

No bypass: this hook is read-only and emits non-blocking context. It can
be disabled by removing the SessionStart entry from settings.json.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


WINDOW_SECONDS = 7 * 24 * 60 * 60

CHECKPOINT_GLOBS = (
    "checkpoints/*.md",
    ".claude/checkpoints/*.md",
)
SPEC_GLOBS = (
    "specs/*/plan.md",
    ".claude/specs/*/plan.md",
)
SESSION_GLOBS = (
    "sessions/*.md",
    ".claude/sessions/*.md",
)

WORKSPACE_PLAN_GLOBS = ("plans/*/plan.md",)

MAX_PREVIEW_LINES = 30
PROMPT_MAX_LINES = 200

from _lib import project_workspace as pw  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402


def workspace_dir(cwd: Path) -> Path | None:
    """Return the local workspace folder for the repo at `cwd`, or None."""
    try:
        top = pw.toplevel(cwd)
        return None if top is None else top / pw.resolve_root(top)
    except pw.WorkspaceError:
        return None


def find_recent(cwd: Path, patterns: tuple[str, ...]) -> list[Path]:
    """Return matching paths within the freshness window, newest first."""
    found: list[tuple[float, Path]] = []
    now = time.time()
    for pattern in patterns:
        for p in cwd.glob(pattern):
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if now - mtime <= WINDOW_SECONDS:
                found.append((mtime, p))
    found.sort(reverse=True)
    return [p for _, p in found]


def preview(path: Path, limit: int = MAX_PREVIEW_LINES) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    lines = text.splitlines()
    head = lines[:limit]
    if len(lines) > limit:
        head.append(f"... ({len(lines) - limit} more lines)")
    return "\n".join(head)


def prompt_file(workspace: Path | None) -> Path | None:
    """Return the workspace continuation prompt when it exists."""
    if workspace is None:
        return None
    candidate = workspace / pw.PROMPT_NAME
    return candidate if candidate.is_file() else None


def recent_plans(cwd: Path, workspace: Path | None) -> list[Path]:
    """Return project spec plans and workspace plans, newest first."""
    found = find_recent(cwd, SPEC_GLOBS)
    if workspace is not None:
        found = found + find_recent(workspace, WORKSPACE_PLAN_GLOBS)
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def workspace_note(workspace: Path | None) -> list[str]:
    """Name the workspace folder so the session writes into the right one."""
    if workspace is None:
        return []
    return [
        f"Local workspace: `{workspace}/`. It is excluded from git and never "
        f"committed. Keep `{pw.PROMPT_NAME}` there current per "
        "~/.claude/rules/project-workspace.md.",
        "",
    ]


def build_context(cwd: Path, source: str) -> str | None:
    """Build the context block. Returns None when nothing to surface."""
    workspace = workspace_dir(cwd)
    prompt = prompt_file(workspace)
    checkpoints = find_recent(cwd, CHECKPOINT_GLOBS)
    specs = recent_plans(cwd, workspace)
    sessions = find_recent(cwd, SESSION_GLOBS)

    if not (prompt or checkpoints or specs or sessions):
        note = workspace_note(workspace)
        if not note:
            return None
        return "\n".join([f"WORKSPACE (SessionStart: {source})", *note]).rstrip()

    lines: list[str] = []
    lines.append(f"RESUME CONTEXT (SessionStart: {source})")
    lines.append("")
    lines.append("The previous session left these artifacts behind. Read them")
    lines.append("before starting new work so you do not duplicate or override")
    lines.append("in-progress changes.")
    lines.append("")
    lines.extend(workspace_note(workspace))

    primary: Path
    if prompt is not None:
        primary = prompt
        lines.append(f"Continuation prompt: `{primary}`")
    elif checkpoints:
        primary = checkpoints[0]
        lines.append(f"Most recent checkpoint: `{primary}`")
    elif specs:
        primary = specs[0]
        lines.append(f"Most recent active plan: `{primary}`")
    else:
        primary = sessions[0]
        lines.append(f"Most recent session log: `{primary}`")

    if prompt is not None and checkpoints:
        lines.append("")
        lines.append("Recent checkpoints:")
        for c in checkpoints[:5]:
            lines.append(f"  - `{c}`")
    elif len(checkpoints) > 1:
        lines.append("")
        lines.append("Other recent checkpoints:")
        for c in checkpoints[1:5]:
            lines.append(f"  - `{c}`")

    if specs and primary not in specs:
        lines.append("")
        lines.append("Recent active plans:")
        for s in specs[:5]:
            lines.append(f"  - `{s}`")

    excerpt = preview(primary, PROMPT_MAX_LINES if prompt else MAX_PREVIEW_LINES)
    if excerpt:
        lines.append("")
        lines.append(f"Preview of `{primary.name}`:")
        lines.append("```")
        lines.append(excerpt)
        lines.append("```")

    return "\n".join(lines)


def emit_context(context: str, source: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    sys.stdout.write(json.dumps(payload))
    _audit(
        hook="session-resume-context",
        decision="info",
        decision_class="info",
        reason=f"source={source} chars={len(context)}",
    )


def main() -> int:
    if os.environ.get("SESSION_RESUME_CONTEXT_DISABLE") == "1":
        return 0
    if is_bypassed("session-resume-context"):
        return 0
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if data.get("hook_event_name") != "SessionStart":
        return 0

    source = data.get("source", "startup")
    cwd_str = data.get("cwd", os.getcwd())
    cwd = Path(cwd_str)

    context = build_context(cwd, source)
    if context is None:
        return 0

    emit_context(context, source)
    return 0


if __name__ == "__main__":
    sys.exit(main())
