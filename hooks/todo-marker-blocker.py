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

Third-party tool directives are honored, since they are the one comment form
the project ban exempts:
  `eslint-disable`, `eslint-disable-line`, `eslint-disable-next-line`,
  `@ts-expect-error`, `@ts-ignore`, `@ts-nocheck`,
  block ranges `/* eslint-disable */ ... /* eslint-enable */`.

There is no allow marker of our own. A legitimate marker uses the
issue-linked form `TODO(#123)`, which passes without any comment annotation.

Bypass:
  TODO_MARKER_DISABLE=1, or a TTL entry via scripts/bypass.py
"""

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


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.hook_profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main() -> int:
    if not should_run("todo-marker-blocker"):
        _sys.exit(0)
    if os.environ.get("TODO_MARKER_DISABLE") == "1":
        _audit(
            hook="todo-marker-blocker",
            decision="bypass",
            bypass_env="TODO_MARKER_DISABLE",
        )
        return 0
    if is_bypassed("todo-marker-blocker"):
        return 0

    payload = read_hook_payload("todo-marker-blocker")

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
        "set todo-marker-blocker`.",
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
