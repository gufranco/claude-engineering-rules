#!/usr/bin/env python3
"""Block production-code writes that have no companion test file.

Triggers PreToolUse on Write, Edit, MultiEdit. The hook returns exit 2
(block) with a fix hint when a target file looks like production code and
no test sibling can be located.

Definition of "production code":
  - source file (.py .js .ts .jsx .tsx .go .rs .rb .java .kt .swift .cs .php ...)
  - NOT under tests/, __tests__/, spec/, e2e/
  - NOT itself a test file (.test. .spec. _test.go etc.)
  - NOT a config, doc, fixture, migration, or generated file

Test discovery strategy (first match wins):
  1. sibling `<name>.test.<ext>` / `<name>.spec.<ext>` / `<name>_test.<ext>`
  2. `__tests__/` or `tests/` next to the source
  3. project test root scan for filenames matching the source basename
  4. Python: `tests/test_<name>.py` mirror
  5. Go: `<name>_test.go` sibling

Edits to files that already exist on disk pass without checking; the gate
fires only when a production source file is being CREATED.

Bypass: TDD_GATE_DISABLE=1 in the parent shell.

Enforces: rules/testing.md.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


SOURCE_EXTS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".mjs",
    ".cjs",
    ".go",
    ".rs",
    ".rb",
    ".java",
    ".kt",
    ".swift",
    ".cs",
    ".php",
    ".scala",
    ".clj",
    ".ex",
    ".exs",
}

TEST_DIR_PARTS = {
    "tests",
    "test",
    "__tests__",
    "spec",
    "specs",
    "e2e",
    "integration-tests",
}

TEST_NAME_MARKERS = (
    ".test.",
    ".spec.",
    ".int.",
    ".e2e.",
    "_test.",
    "_spec.",
    "Test.",
    "Spec.",
)

EXCLUDED_DIR_PARTS = {
    "node_modules",
    "dist",
    "build",
    ".next",
    "out",
    "coverage",
    "vendor",
    "target",
    ".git",
    "migrations",
    "fixtures",
    "__pycache__",
    ".venv",
    "venv",
    "env",
}

EXCLUDED_NAME_MARKERS = (
    ".d.ts",
    ".min.js",
    ".bundle.js",
    ".generated.",
)

from _lib.bypass import is_bypassed  # noqa: E402


def is_test_file(path: Path) -> bool:
    parts = set(path.parts)
    if parts & TEST_DIR_PARTS:
        return True
    name = path.name
    return any(marker in name for marker in TEST_NAME_MARKERS)


def is_production_source(path: Path) -> bool:
    if path.suffix not in SOURCE_EXTS:
        return False
    if any(marker in path.name for marker in EXCLUDED_NAME_MARKERS):
        return False
    parts = set(path.parts)
    if parts & EXCLUDED_DIR_PARTS:
        return False
    if is_test_file(path):
        return False
    return True


def stem_variants(stem: str) -> set[str]:
    """Return name variants used to match a test against a source file."""
    variants = {stem}
    variants.add(stem.replace("-", "_"))
    variants.add(stem.replace("_", "-"))
    return variants


def find_companion_test(path: Path) -> Path | None:
    """Locate a test that names this source file. None if missing."""
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    variants = stem_variants(stem)

    for v in variants:
        sibling_candidates = [
            parent / f"{v}.test{suffix}",
            parent / f"{v}.spec{suffix}",
            parent / f"{v}_test{suffix}",
            parent / f"test_{v}{suffix}",
        ]
        for cand in sibling_candidates:
            if cand.exists():
                return cand

    for testdir_name in ("__tests__", "tests", "test"):
        td = parent / testdir_name
        if td.is_dir():
            for cand in td.iterdir():
                if cand.is_file() and any(v in cand.name for v in variants):
                    return cand

    cursor = parent
    for _ in range(6):
        if cursor == cursor.parent:
            break
        for testdir_name in ("tests", "__tests__", "test"):
            td = cursor / testdir_name
            if td.is_dir():
                for v in variants:
                    for cand in td.rglob(f"*{v}*"):
                        if cand.is_file() and is_test_file(cand):
                            return cand
        cursor = cursor.parent

    return None


def emit_block(reason: str, file_path: str) -> None:
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
        hook="tdd-gate",
        decision="block",
        decision_class="block",
        reason=reason[:200],
        file_path=file_path,
        tool="Write",
    )
    sys.exit(2)


def main() -> int:
    if os.environ.get("TDD_GATE_DISABLE") == "1":
        return 0
    if is_bypassed("tdd-gate"):
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

    target = Path(file_path_str)

    if not is_production_source(target):
        return 0

    if tool_name in {"Edit", "MultiEdit"} and target.exists():
        return 0

    if tool_name == "Write" and target.exists():
        return 0

    companion = find_companion_test(target)
    if companion is not None:
        return 0

    reason = (
        f"BLOCKED: creating production source `{target.name}` without a "
        f"companion test.\n"
        f"Rule: ~/.claude/rules/testing.md.\n"
        f"Fix: write a failing test at one of these paths first:\n"
        f"  - {target.parent}/{target.stem}.test{target.suffix}\n"
        f"  - {target.parent}/__tests__/{target.stem}.test{target.suffix}\n"
        f"  - tests/{target.stem}/test_{target.stem}{target.suffix}\n"
        f"Then write the production code to make it pass.\n"
        f"Bypass (one-off): set TDD_GATE_DISABLE=1 in parent shell."
    )
    emit_block(reason, str(target))
    return 2  # unreachable


if __name__ == "__main__":
    sys.exit(main())
