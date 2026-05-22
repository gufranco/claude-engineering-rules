#!/usr/bin/env python3
"""todo-marker-blocker

PreToolUse hook that blocks tactical-debt marker comments in source code.
Rule sources:
  - ~/.claude/CLAUDE.md "Completeness" (no TODOs, no leave-for-later).
  - ~/.claude/rules/code-style.md "Completeness" (full implementation, never half-measures).
  - ~/.claude/rules/design-philosophy.md "Strategic vs Tactical Programming".

Markers blocked (case-insensitive, word-boundary):
  TODO, FIXME, HACK, XXX, WIP, and the literal phrase "leave for later".

Allowlist (issue-linked form):
  TODO(#123), FIXME(#456), TODO(#issue-789), FIXME(issue-42)
  An explicit issue reference converts a bare marker into a tracked item.

Skipped paths:
  - Planning artifacts: **/specs/**, **/docs/adr/**, **/docs/plan*/**
  - Templates: **/templates/**, *.tmpl, *.template
  - Test files: *.test.*, *.spec.*, **/__tests__/**, **/__test__/**
  - The ~/.claude/ tree itself (rules document the patterns, hooks self-test them)
  - Markdown, YAML, TOML, JSON, ini, config files

Suppression markers (per line):
  - `// allow-todo -- justification` honored with explicit reason.
  - `// @allow-todo -- justification` at the top of the file suppresses
    every marker in that file.
  - Standard ESLint and TypeScript markers honored:
    `eslint-disable`, `eslint-disable-line`, `eslint-disable-next-line`,
    `@ts-expect-error`, `@ts-ignore`, `@ts-nocheck`,
    block ranges `/* eslint-disable */ ... /* eslint-enable */`.

Bypass:
  TODO_MARKER_DISABLE=1
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
    ),
)

try:
    from audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


from suppression import (
    compute_block_state,
    has_inline_marker,
    has_justification_trailer,
    is_suppressed,
)

# Source file extensions where markers are blocked.
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

# Path segments that disable the hook.
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

# File suffixes that disable the hook.
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

# Markers to block. Word-boundary, case-insensitive.
# The "leave for later" phrase is treated specially because it spans multiple words.
WORD_MARKERS: tuple[str, ...] = ("TODO", "FIXME", "HACK", "XXX", "WIP")

# Matches a marker possibly followed by a colon, dash, or whitespace,
# but excludes the issue-linked form TODO(...) / FIXME(...).
# Captures the marker name for the error message.
_MARKER_ALTERNATION = "|".join(WORD_MARKERS)
MARKER_PATTERN = re.compile(
    rf"\b({_MARKER_ALTERNATION})\b(?!\s*\()",
    re.IGNORECASE,
)

PHRASE_PATTERN = re.compile(
    r"\bleave\s+(?:it\s+|this\s+|that\s+)?for\s+later\b",
    re.IGNORECASE,
)

# Allowlist: TODO(#123), FIXME(#JIRA-456), TODO(issue-789), FIXME(GH-42)
ISSUE_LINKED_PATTERN = re.compile(
    rf"\b({_MARKER_ALTERNATION})\s*\(\s*#?[A-Za-z0-9_\-]+\s*\)",
    re.IGNORECASE,
)

ALLOW_FILE_MARKER = "@allow-todo"
ALLOW_LINE_MARKER = "allow-todo"
TOP_OF_FILE_SCAN = 10


def is_skipped(path: str) -> bool:
    """Skip non-source files, planning paths, templates, tests, the .claude tree."""
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
    """Return (file_path, field_name, text) tuples for Write/Edit/MultiEdit."""
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


def _file_marker_active(lines: list[str]) -> bool:
    """True when a top-of-file allow marker exists with a justification trailer."""
    seen = 0
    for line in lines:
        if seen >= TOP_OF_FILE_SCAN:
            break
        if not line.strip():
            continue
        seen += 1
        if has_inline_marker(line, ALLOW_FILE_MARKER) and has_justification_trailer(
            line
        ):
            return True
    return False


def _line_allow_marker_active(lines: list[str], idx: int) -> bool:
    """True when the per-line marker is on the offending line or directly above."""
    if idx < 0 or idx >= len(lines):
        return False
    line = lines[idx]
    if has_inline_marker(line, ALLOW_LINE_MARKER) and has_justification_trailer(line):
        return True
    if idx > 0:
        prev = lines[idx - 1]
        if has_inline_marker(prev, ALLOW_LINE_MARKER) and has_justification_trailer(
            prev
        ):
            return True
    return False


def _mask_issue_linked(line: str) -> str:
    """Replace TODO(#123) / FIXME(issue-42) with spaces so they don't match the bare pattern."""
    return ISSUE_LINKED_PATTERN.sub(lambda m: " " * len(m.group(0)), line)


def find(text: str) -> list[str]:
    """Return marker hits per line, honoring suppression markers and the issue-link allowlist."""
    lines = text.splitlines()
    if _file_marker_active(lines):
        return []

    block_state = compute_block_state(lines)
    hits: list[str] = []
    for i, line in enumerate(lines):
        if is_suppressed(lines, i, block_state=block_state):
            continue
        if _line_allow_marker_active(lines, i):
            continue
        masked = _mask_issue_linked(line)
        for m in MARKER_PATTERN.finditer(masked):
            hits.append(m.group(1).upper())
        if PHRASE_PATTERN.search(masked):
            hits.append("leave for later")
    return hits


def main() -> int:
    if os.environ.get("TODO_MARKER_DISABLE") == "1":
        _audit(
            hook="todo-marker-blocker",
            decision="bypass",
            bypass_env="TODO_MARKER_DISABLE",
        )
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}

    items = collect(tool, tool_input)
    if not items:
        return 0

    findings: list[str] = []
    for path, field, text in items:
        if is_skipped(path):
            continue
        hits = find(text)
        if hits:
            findings.append(f"  - {field} ({path}): {', '.join(sorted(set(hits)))}")

    if not findings:
        return 0

    print(
        "Blocked: tactical-debt marker in source code. "
        'Rule: ~/.claude/CLAUDE.md "Completeness" and '
        '~/.claude/rules/design-philosophy.md "Strategic vs Tactical Programming".\n'
        + "\n".join(findings)
        + "\n\nFix options:\n"
        "  1. Complete the work now. The marginal cost of finishing is near zero with AI assistance.\n"
        "  2. Open a tracked issue. Reference it as TODO(#123) or FIXME(#issue-42) for the issue-linked form to pass.\n"
        "  3. Delete the marker if the work is not actually needed.\n"
        "Suppression (when the marker is legitimate, e.g. test fixture, demo, doc example):\n"
        "  - Per-line: append `// allow-todo -- <reason>` (justification required).\n"
        "  - Per-file: top-of-file `// @allow-todo -- <reason>`.\n"
        "  - Standard ESLint and TypeScript markers honored.\n"
        "Bypass (rare, prefer the issue-linked form): set TODO_MARKER_DISABLE=1.",
        file=sys.stderr,
    )
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
