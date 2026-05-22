#!/usr/bin/env python3
"""as-any-blocker

PreToolUse hook that blocks the `any` type in TypeScript code.
Rule source: ~/.claude/rules/code-style.md "Strong typing" + "Maximum
Compiler and Checker Strictness".

  - Never `any`, use `unknown` and narrow.
  - When modifying a file that already uses `any`, replace it with proper types.

Patterns blocked:
  - `as any`           (type assertion)
  - `: any`            (annotation)
  - `<any>`            (generic argument)
  - `any[]`            (array of any)
  - `Promise<any>`, `Array<any>`, `Record<string, any>`, etc.

Skipped:
  - Type declaration files where `any` is unavoidable: *.d.ts (still warned).
  - Hooks directory itself (~/.claude/).

Suppression markers (per line):

  - `// allow-any -- justification` honored when justified.
  - `// @allow-any -- justification` at the top of the file
    suppresses every `any` in that file.
  - Standard ESLint and TypeScript markers honored:
    `eslint-disable`, `eslint-disable-line`, `eslint-disable-next-line`,
    `@ts-expect-error`, `@ts-ignore`, `@ts-nocheck`,
    block ranges `/* eslint-disable */ ... /* eslint-enable */`.

Bypass:
  AS_ANY_DISABLE=1
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

TS_EXTS: tuple[str, ...] = (".ts", ".tsx", ".mts", ".cts")

PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bas\s+any\b"), "as any"),
    (re.compile(r":\s*any(?=[\s,;)\]>=|&]|$)"), ": any"),
    (re.compile(r"<\s*any\s*>"), "<any>"),
    (re.compile(r"\bany\s*\[\s*\]"), "any[]"),
    (re.compile(r"<[^<>]*\bany\b[^<>]*>"), "generic with any"),
)

ALLOW_FILE_MARKER = "@allow-any"
ALLOW_LINE_MARKER = "allow-any"
TOP_OF_FILE_SCAN = 10
MAX_HITS_PER_FILE = 8


def is_skipped_path(path: str) -> bool:
    """Skip non-TypeScript paths and the hooks directory."""
    if not path:
        return True
    p = path.lower()
    if not p.endswith(TS_EXTS):
        return True
    if p.endswith(".d.ts"):
        return True
    if "/.claude/" in p:
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


def find(text: str) -> list[str]:
    """Return formatted hits for every line carrying an `any` pattern.

    Honors block-level eslint-disable, line-level eslint and TypeScript
    markers, and the hook-specific `allow-any` markers when they
    carry a justification trailer.
    """
    lines = text.splitlines()
    if _file_marker_active(lines):
        return []

    block_state = compute_block_state(lines)
    hits: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (
            stripped.startswith("//")
            or stripped.startswith("*")
            or stripped.startswith("/*")
        ):
            continue
        if is_suppressed(lines, i, block_state=block_state):
            continue
        if _line_allow_marker_active(lines, i):
            continue
        for pat, label in PATTERNS:
            m = pat.search(line)
            if m:
                hits.append(f"L{i + 1} ({label}): {stripped[:120]}")
                break
    return hits


def main() -> int:
    if os.environ.get("AS_ANY_DISABLE") == "1":
        _audit(hook="as-any-blocker", decision="bypass", bypass_env="AS_ANY_DISABLE")
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
    for path, _field, text in items:
        if is_skipped_path(path):
            continue
        hits = find(text)
        if hits:
            findings.append(f"  - {path}:")
            findings.extend(f"      {h}" for h in hits[:MAX_HITS_PER_FILE])
            if len(hits) > MAX_HITS_PER_FILE:
                findings.append(f"      ... and {len(hits) - MAX_HITS_PER_FILE} more")

    if not findings:
        return 0

    print(
        "Blocked: `any` type detected. "
        'Rule: ~/.claude/rules/code-style.md "Strong typing".\n'
        + "\n".join(findings)
        + "\n\nFix: replace `any` with `unknown` and narrow at the boundary, or define a "
        "proper type. For ORM queries use the generated types (Prisma.WhereInput, etc.). "
        "For payloads use Zod parsing.\n"
        "Suppression:\n"
        "  - Per-line: append `// allow-any -- <reason>` (justification required).\n"
        "  - Per-file: top-of-file `// @allow-any -- <reason>`.\n"
        "  - Standard ESLint and TypeScript markers honored.\n"
        "Bypass (genuine third-party gap with no alternative): set AS_ANY_DISABLE=1.",
        file=sys.stderr,
    )
    _audit(
        hook="as-any-blocker",
        decision="block",
        tool=tool,
        reason="TypeScript any usage",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
