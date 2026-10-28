#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


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
    try:
        top = pw.toplevel(cwd)
        return None if top is None else top / pw.resolve_root(top)
    except pw.WorkspaceError:
        return None


def find_recent(cwd: Path, patterns: tuple[str, ...]) -> list[Path]:
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
    if workspace is None:
        return None
    candidate = workspace / pw.PROMPT_NAME
    return candidate if candidate.is_file() else None


def recent_plans(cwd: Path, workspace: Path | None) -> list[Path]:
    found = find_recent(cwd, SPEC_GLOBS)
    if workspace is not None:
        found = found + find_recent(workspace, WORKSPACE_PLAN_GLOBS)
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def workspace_note(workspace: Path | None) -> list[str]:
    if workspace is None:
        return []
    return [
        f"Local workspace: `{workspace}/`. It is excluded from git and never "
        f"committed. Keep `{pw.PROMPT_NAME}` there current per "
        "~/.claude/rules/project-workspace.md.",
        "",
    ]


RESUME_INTRO = (
    "",
    "The previous session left these artifacts behind. Read them",
    "before starting new work so you do not duplicate or override",
    "in-progress changes.",
    "",
)


def _primary_artifact(
    prompt: Path | None,
    checkpoints: list[Path],
    specs: list[Path],
    sessions: list[Path],
) -> tuple[Path, str]:
    if prompt is not None:
        return prompt, f"Continuation prompt: `{prompt}`"
    if checkpoints:
        return checkpoints[0], f"Most recent checkpoint: `{checkpoints[0]}`"
    if specs:
        return specs[0], f"Most recent active plan: `{specs[0]}`"
    return sessions[0], f"Most recent session log: `{sessions[0]}`"


def _checkpoint_lines(prompt: Path | None, checkpoints: list[Path]) -> list[str]:
    if prompt is not None and checkpoints:
        return ["", "Recent checkpoints:", *(f"  - `{c}`" for c in checkpoints[:5])]
    if len(checkpoints) > 1:
        return [
            "",
            "Other recent checkpoints:",
            *(f"  - `{c}`" for c in checkpoints[1:5]),
        ]
    return []


def _spec_lines(specs: list[Path], primary: Path) -> list[str]:
    if not specs or primary in specs:
        return []
    return ["", "Recent active plans:", *(f"  - `{s}`" for s in specs[:5])]


def _preview_lines(primary: Path, prompt: Path | None) -> list[str]:
    excerpt = preview(primary, PROMPT_MAX_LINES if prompt else MAX_PREVIEW_LINES)
    if not excerpt:
        return []
    return ["", f"Preview of `{primary.name}`:", "```", excerpt, "```"]


def build_context(cwd: Path, source: str) -> str | None:
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

    primary, primary_line = _primary_artifact(prompt, checkpoints, specs, sessions)
    lines = [
        f"RESUME CONTEXT (SessionStart: {source})",
        *RESUME_INTRO,
        *workspace_note(workspace),
        primary_line,
        *_checkpoint_lines(prompt, checkpoints),
        *_spec_lines(specs, primary),
        *_preview_lines(primary, prompt),
    ]
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
