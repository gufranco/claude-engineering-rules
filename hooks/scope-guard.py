#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


try:
    from _lib.project_scope import repo_root, walk_up
    from _lib.project_workspace import in_workspace
except ImportError:  # pragma: no cover
    sys.exit(0)

PLAN_WINDOW_SECONDS = 60 * 60
PLAN_HEADER_BYTES = 2048
CLOSED_PLAN_STAMP = re.compile(r"^\**(?:Archived|Superseded):", re.MULTILINE)

SPEC_GLOBS = (
    "specs/*/plan.md",
    ".claude/specs/*/plan.md",
    "docs/plans/*/plan.md",
    ".work/plans/*/plan.md",
    ".work-local/plans/*/plan.md",
)

EXTENSIONLESS_FILENAMES = (
    "Makefile",
    "GNUmakefile",
    "Dockerfile",
    "Containerfile",
    "Justfile",
    "Procfile",
    "Gemfile",
    "Rakefile",
    "Brewfile",
    "Vagrantfile",
    "Jenkinsfile",
    "LICENSE",
)

BACKTICK_PATH = re.compile(
    r"`([^`\s]+\.[a-zA-Z0-9]+|[^`\s]+/[^`\s]*|\.[a-zA-Z][a-zA-Z0-9_-]{2,}|"
    + "|".join(EXTENSIONLESS_FILENAMES)
    + ")`"
)

BARE_EXTENSIONS = frozenset(
    {
        ".bak",
        ".bin",
        ".cfg",
        ".csv",
        ".css",
        ".gz",
        ".html",
        ".ini",
        ".jpg",
        ".json",
        ".jsx",
        ".lock",
        ".log",
        ".pdf",
        ".png",
        ".sql",
        ".svg",
        ".tar",
        ".tmp",
        ".toml",
        ".tsv",
        ".tsx",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
        ".zip",
    }
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


def plan_is_closed(plan: Path) -> bool:
    try:
        with plan.open(encoding="utf-8", errors="replace") as handle:
            header = handle.read(PLAN_HEADER_BYTES)
    except OSError:
        return False
    return CLOSED_PLAN_STAMP.search(header) is not None


def find_active_plan(cwd: Path) -> Path | None:
    now = time.time()
    for cursor in walk_up(cwd, limit=5):
        here: list[tuple[float, Path]] = []
        for pattern in SPEC_GLOBS:
            for p in cursor.glob(pattern):
                try:
                    mtime = p.stat().st_mtime
                except OSError:
                    continue
                if now - mtime <= PLAN_WINDOW_SECONDS and not plan_is_closed(p):
                    here.append((mtime, p))
        if here:
            here.sort(reverse=True)
            return here[0][1]
    return None


def extract_declared_paths(plan_text: str) -> set[str]:
    paths: set[str] = set()
    for match in BACKTICK_PATH.finditer(plan_text):
        token = match.group(1)
        if token.startswith("-") or "=" in token:
            continue
        if token.lower() in BARE_EXTENSIONS:
            continue
        paths.add(token)
    return paths


def governs(plan_path: Path, target: Path) -> bool:
    root = repo_root(plan_path.parent)
    if root is None:
        return True
    try:
        target.resolve().relative_to(root)
    except (OSError, ValueError):
        return False
    return True


def is_in_scope(target: Path, declared: set[str]) -> bool:
    target_str = str(target)
    for decl in declared:
        if decl in target_str:
            return True
        if decl.endswith("/") and decl.rstrip("/") in target_str:
            return True
    return False


def emit_block(reason: str, file_path: str) -> NoReturn:
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
        hook="scope-guard",
        decision="block",
        decision_class="block",
        reason=reason[:200],
        file_path=file_path,
        tool="Edit",
    )
    sys.exit(2)


def _edit_target(data: dict) -> tuple[Path, Path] | None:
    if data.get("tool_name", "") not in {"Write", "Edit", "MultiEdit"}:
        return None
    tool_input = data.get("tool_input") or {}
    file_path_str = tool_input.get("file_path", "")
    if not file_path_str:
        return None
    return Path(file_path_str), Path(data.get("cwd", os.getcwd()))


def _active_plan(cwd: Path) -> tuple[Path, set[str]] | None:
    plan_path = find_active_plan(cwd)
    if plan_path is None:
        return None
    try:
        plan_text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return None
    declared = extract_declared_paths(plan_text)
    if not declared:
        return None
    return plan_path, declared


def _allowed(plan_path: Path, target: Path, declared: set[str]) -> bool:
    return (
        not governs(plan_path, target)
        or in_workspace(target)
        or is_in_scope(target, declared)
        or str(plan_path.parent) in str(target)
    )


def _block_reason(plan_path: Path, target: Path) -> str:
    return (
        f"BLOCKED: editing `{target.name}` which is not listed in the active "
        f"plan `{plan_path}`.\n"
        f"Rule: ~/.claude/rules/surgical-edits.md.\n"
        f"If this edit is necessary, add its path to the plan in backticks, "
        f"then retry; a retry alone is blocked again. To suppress this gate: set "
        f"SCOPE_GUARD_DISABLE=1."
    )


def main() -> int:
    if os.environ.get("SCOPE_GUARD_DISABLE") == "1":
        return 0
    if is_bypassed("scope-guard"):
        return 0

    data = read_hook_payload("scope-guard")

    edit = _edit_target(data)
    if edit is None:
        return 0
    target, cwd = edit

    plan = _active_plan(cwd)
    if plan is None:
        return 0
    plan_path, declared = plan

    if _allowed(plan_path, target, declared):
        return 0

    emit_block(_block_reason(plan_path, target), str(target))


if __name__ == "__main__":
    sys.exit(main())
