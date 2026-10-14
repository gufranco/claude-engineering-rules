#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


from _lib.suppression import (
    compute_block_state,
    is_suppressed,
)

SOURCE_EXTS: tuple[str, ...] = (
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".py",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".kts",
    ".c",
    ".cpp",
    ".cc",
    ".cxx",
    ".h",
    ".hpp",
    ".hh",
    ".cs",
    ".swift",
    ".rb",
    ".php",
    ".scala",
    ".m",
    ".mm",
    ".sh",
    ".bash",
    ".zsh",
)

SKIP_SEGMENTS: tuple[str, ...] = (
    "/specs/",
    "/docs/adr/",
    "/docs/plan/",
    "/docs/plans/",
    "/docs/planning/",
    "/templates/",
    "/template/",
    "/__tests__/",
    "/__test__/",
    "/test-utils/",
    "/testing/",
    "/e2e/",
    "/fixtures/",
    "/.claude/",
    "/node_modules/",
    "/vendor/",
    "/.git/",
    "/dist/",
    "/build/",
)

SKIP_SUFFIXES: tuple[str, ...] = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".test.py",
    ".test.rs",
    ".test.go",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
    ".tmpl",
    ".template",
    ".tpl",
)

WORD_MARKERS: tuple[str, ...] = ("TODO", "FIXME", "HACK", "XXX", "WIP")

_MARKER_ALTERNATION = "|".join(WORD_MARKERS)
MARKER_PATTERN = re.compile(
    rf"\b({_MARKER_ALTERNATION})\b",
    re.IGNORECASE,
)

PHRASE_PATTERN = re.compile(
    r"\bleave\s+(?:it\s+|this\s+|that\s+)?for\s+later\b",
    re.IGNORECASE,
)


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


def is_skipped(path: str) -> bool:
    if not path:
        return True
    p = path.lower()
    if not any(p.endswith(ext) for ext in SOURCE_EXTS):
        return True
    if any(seg in p for seg in SKIP_SEGMENTS):
        return True
    if any(p.endswith(suf) for suf in SKIP_SUFFIXES):
        return True
    return False


def collect(tool: str, tool_input: dict) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    fp = tool_input.get("file_path", "") or ""
    if tool == "Write":
        c = tool_input.get("content", "")
        if isinstance(c, str):
            out.append((fp, "content", c))
    elif tool == "Edit":
        c = tool_input.get("new_string", "")
        if isinstance(c, str):
            out.append((fp, "new_string", c))
    elif tool == "MultiEdit":
        for i, edit in enumerate(tool_input.get("edits", []) or []):
            if isinstance(edit, dict):
                c = edit.get("new_string", "")
                if isinstance(c, str):
                    out.append((fp, f"edits[{i}].new_string", c))
    return out


PHRASE_LABEL = "leave for later"
ESLINT_RULES = frozenset({"no-warning-comments"})


def find(text: str) -> list[str]:
    lines = text.splitlines()
    block_state = compute_block_state(lines, rules=ESLINT_RULES)
    hits: list[str] = []
    for i, line in enumerate(lines):
        if is_suppressed(lines, i, block_state=block_state, rules=ESLINT_RULES):
            continue
        hits = [*hits, *(m.group(1).upper() for m in MARKER_PATTERN.finditer(line))]
        if PHRASE_PATTERN.search(line):
            hits = [*hits, PHRASE_LABEL]
    return hits


from _lib.hook_profile import should_run  # noqa: E402


def _disabled() -> bool:
    if not should_run("todo-marker-blocker"):
        sys.exit(0)
    if os.environ.get("TODO_MARKER_DISABLE") == "1":
        _audit(
            hook="todo-marker-blocker",
            decision="bypass",
            bypass_env="TODO_MARKER_DISABLE",
        )
        return True
    return is_bypassed("todo-marker-blocker")


def _collect_findings(items: list[tuple[str, str, str]]) -> list[str]:
    findings: list[str] = []
    for path, field, text in items:
        if is_skipped(path):
            continue
        hits = find(text)
        if hits:
            findings.append(f"  - {field} ({path}): {', '.join(sorted(set(hits)))}")
    return findings


def _block_message(findings: list[str]) -> str:
    return (
        "Blocked: tactical-debt marker in source code. "
        'Rule: ~/.claude/rules/code-style.md "Completeness" and '
        "~/.claude/rules/found-fix.md, which says a code marker is never a fix.\n"
        + "\n".join(findings)
        + "\n\nFix options:\n"
        "  1. Complete the work now.\n"
        "  2. Delete the marker if the work is not actually needed.\n"
        "A marker with an issue number is still a marker; the issue tracks the "
        "work, the code does not need to.\n"
        "Third-party tool directives (eslint-disable, @ts-expect-error) are honored.\n"
        "Bypass (rare): set TODO_MARKER_DISABLE=1, "
        "or register a TTL-bound pass with `python3 ~/.claude/scripts/bypass.py "
        "set todo-marker-blocker`."
    )


def main() -> int:
    if _disabled():
        return 0

    payload = read_hook_payload("todo-marker-blocker")

    tool = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}

    items = collect(tool, tool_input)
    if not items:
        return 0

    findings = _collect_findings(items)
    if not findings:
        return 0

    print(_block_message(findings), file=sys.stderr)
    _audit(
        hook="todo-marker-blocker",
        decision="block",
        tool=tool,
        reason="tactical-debt marker in source",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
