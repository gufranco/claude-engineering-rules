#!/usr/bin/env python3
from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.project_scope import walk_up  # noqa: E402
from _lib.audit_log import record as _audit  # noqa: E402


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
    "scratchpad",
}

EXCLUDED_NAME_MARKERS = (
    ".d.ts",
    ".min.js",
    ".bundle.js",
    ".generated.",
    ".config.",
)

EXCLUDED_EXACT_NAMES = {
    "__init__.py",
    "conftest.py",
    "setup.py",
    "types.ts",
    "types.tsx",
    "types.py",
    "types.go",
    "next-env.d.ts",
}

BARREL_STATEMENT = re.compile(
    r"""(?xs)
    \s*(?:
        //[^\n]*
      | /\*.*?\*/
      | import\s[^;\n]*;?
      | export\s+(?:type\s+)?\*\s*(?:as\s+\w+\s*)?from\s*['"][^'"]+['"]\s*;?
      | export\s+(?:type\s+)?\{[^}]*\}\s*(?:from\s*['"][^'"]+['"]\s*)?;?
    )\s*
    """
)

from _lib.assertion_weakening import findings_for  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.test_paths import is_test_file  # noqa: E402

WEAKENING_HOOK = "test-weakening"
WEAKENING_BYPASS_ENV = "TEST_WEAKENING_DISABLE"


def is_barrel(content: str) -> bool:
    if not content.strip():
        return True
    pos = 0
    while pos < len(content):
        match = BARREL_STATEMENT.match(content, pos)
        if match is None or match.end() == pos:
            return not content[pos:].strip()
        pos = match.end()
    return True


def _shared_temp_roots() -> tuple[Path, ...]:
    return tuple(
        dict.fromkeys(
            Path(candidate).resolve() for candidate in ("/tmp", "/private/tmp")
        )
    )


SHARED_TEMP_ROOTS = _shared_temp_roots()


def is_ephemeral_path(path: Path) -> bool:
    resolved = path.resolve()
    return any(resolved.is_relative_to(root) for root in SHARED_TEMP_ROOTS)


def is_production_source(path: Path) -> bool:
    if path.suffix not in SOURCE_EXTS:
        return False
    if is_ephemeral_path(path):
        return False
    if path.name in EXCLUDED_EXACT_NAMES:
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
    variants = {stem}
    variants.add(stem.replace("-", "_"))
    variants.add(stem.replace("_", "-"))
    return variants


TEST_AFFIXES = ("test_", "spec_", "_test", "_spec", ".test", ".spec")


def names_the_source(candidate: Path, variants: set[str]) -> bool:
    stem = candidate.stem
    for affix in TEST_AFFIXES:
        if stem.startswith(affix):
            stem = stem[len(affix) :]
        elif stem.endswith(affix):
            stem = stem[: -len(affix)]
    for affix in (".test", ".spec"):
        if stem.endswith(affix):
            stem = stem[: -len(affix)]
    return stem in variants or stem.replace("-", "_") in variants


def _sibling_test(parent: Path, variant: str, suffix: str) -> Path | None:
    sibling_candidates = [
        parent / f"{variant}.test{suffix}",
        parent / f"{variant}.spec{suffix}",
        parent / f"{variant}_test{suffix}",
        parent / f"test_{variant}{suffix}",
    ]
    for cand in sibling_candidates:
        if cand.exists():
            return cand
    for kind in ("test", "spec"):
        for cand in parent.glob(f"{glob.escape(variant)}.*.{kind}{suffix}"):
            if cand.is_file():
                return cand
    return None


def _is_named_test(cand: Path, variants: set[str]) -> bool:
    return cand.is_file() and is_test_file(cand) and names_the_source(cand, variants)


def _nested_test(parent: Path, variants: set[str]) -> Path | None:
    for testdir_name in ("__tests__", "tests", "test"):
        td = parent / testdir_name
        if td.is_dir():
            for cand in td.iterdir():
                if _is_named_test(cand, variants):
                    return cand
    return None


def _ancestor_test(parent: Path, variants: set[str]) -> Path | None:
    for cursor in walk_up(parent, limit=6):
        for testdir_name in ("tests", "__tests__", "test"):
            td = cursor / testdir_name
            if not td.is_dir():
                continue
            for v in variants:
                for cand in td.rglob(f"*{v}*"):
                    if _is_named_test(cand, variants):
                        return cand
    return None


def find_companion_test(path: Path) -> Path | None:
    variants = stem_variants(path.stem)
    for v in variants:
        sibling = _sibling_test(path.parent, v, path.suffix)
        if sibling is not None:
            return sibling
    nested = _nested_test(path.parent, variants)
    if nested is not None:
        return nested
    return _ancestor_test(path.parent, variants)


def emit_block(reason: str, file_path: str, hook: str = "tdd-gate") -> int:
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
        hook=hook,
        decision="block",
        decision_class="block",
        reason=reason[:200],
        file_path=file_path,
        tool="Write",
    )
    return 2


def _new_source_target(data: dict) -> Path | None:
    tool_name = data.get("tool_name", "")
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        return None
    tool_input = data.get("tool_input") or {}
    file_path_str = tool_input.get("file_path", "")
    if not file_path_str:
        return None
    target = Path(file_path_str)
    if not is_production_source(target):
        return None
    if target.stem == "index" and is_barrel(tool_input.get("content", "")):
        return None
    if target.exists():
        return None
    return target


def _block_reason(target: Path) -> str:
    return (
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


def _weakened_test_file(data: dict) -> tuple[str, list[str]] | None:
    if os.environ.get(WEAKENING_BYPASS_ENV) == "1" or is_bypassed(WEAKENING_HOOK):
        return None
    tool_input = data.get("tool_input") or {}
    file_path = str(tool_input.get("file_path", ""))
    if not file_path or not is_test_file(Path(file_path)):
        return None
    findings = findings_for(str(data.get("tool_name", "")), tool_input)
    return (file_path, findings) if findings else None


def _weakening_reason(file_path: str, findings: list[str]) -> str:
    listed = "\n".join(f"  - {finding}" for finding in findings)
    return (
        f"BLOCKED: this change weakens the test file `{Path(file_path).name}`.\n"
        f"{listed}\n"
        f"Rule: ~/.claude/rules/testing.md. A test or assertion is never weakened, "
        f"skipped, or deleted to make a change pass.\n"
        f"Fix: keep every assertion and test case; fix the code instead. When the "
        f"behavior was removed on purpose or the test moved to another file, ask the "
        f"user, then bypass once.\n"
        f"Bypass (one-off): set {WEAKENING_BYPASS_ENV}=1 in parent shell."
    )


def main() -> int:
    data = read_hook_payload("tdd-gate")

    weakened = _weakened_test_file(data)
    if weakened is not None:
        return emit_block(
            _weakening_reason(*weakened), weakened[0], hook=WEAKENING_HOOK
        )

    if os.environ.get("TDD_GATE_DISABLE") == "1":
        return 0
    if is_bypassed("tdd-gate"):
        return 0

    target = _new_source_target(data)
    if target is None:
        return 0

    if find_companion_test(target) is not None:
        return 0

    return emit_block(_block_reason(target), str(target))


if __name__ == "__main__":
    sys.exit(main())
