#!/usr/bin/env python3
"""
as-any-blocker.py

PreToolUse hook that blocks the `any` type in TypeScript code.
Rule source: ~/.claude/rules/code-style.md "Strong typing" + "Maximum Compiler Strictness".

  - Never `any`, use `unknown` and narrow.
  - When modifying a file that already uses `any`, replace it with proper types.

Patterns blocked:
  - `as any`           (type assertion)
  - `: any`            (annotation)
  - `<any>`            (generic argument)
  - `any[]`            (array of any)
  - `Promise<any>`, `Array<any>`, `Record<string, any>` etc.

Skipped:
  - Type declaration files where `any` is unavoidable: *.d.ts (with warning)
  - Lines with `eslint-disable` or `@ts-expect-error` comment

Bypass:
  AS_ANY_DISABLE=1
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
try:
    from audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover
    def _audit(**_fields):  # type: ignore
        return None


TS_EXTS = (".ts", ".tsx", ".mts", ".cts")

PATTERNS = [
    (re.compile(r"\bas\s+any\b"), "as any"),
    (re.compile(r":\s*any(?=[\s,;)\]>=|&]|$)"), ": any"),
    (re.compile(r"<\s*any\s*>"), "<any>"),
    (re.compile(r"\bany\s*\[\s*\]"), "any[]"),
    (re.compile(r"<[^<>]*\bany\b[^<>]*>"), "generic with any"),
]


def is_skipped_path(path: str) -> bool:
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


def _line_or_prev_has_suppression(lines: list[str], i: int) -> bool:
    line = lines[i]
    if "eslint-disable" in line or "@ts-expect-error" in line or "@ts-ignore" in line:
        return True
    if i > 0:
        prev = lines[i - 1]
        if "eslint-disable-next-line" in prev or "@ts-expect-error" in prev or "@ts-ignore" in prev:
            return True
    return False


def find(text: str) -> list[str]:
    hits: list[str] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        if _line_or_prev_has_suppression(lines, i):
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

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    items = collect(tool, tool_input)
    if not items:
        return 0

    findings: list[str] = []
    for path, field, text in items:
        if is_skipped_path(path):
            continue
        hits = find(text)
        if hits:
            findings.append(f"  - {path}:")
            findings.extend(f"      {h}" for h in hits[:8])
            if len(hits) > 8:
                findings.append(f"      ... and {len(hits) - 8} more")

    if not findings:
        return 0

    print(
        "Blocked: `any` type detected. "
        "Rule: ~/.claude/rules/code-style.md \"Strong typing\".\n"
        + "\n".join(findings)
        + "\n\nFix: replace `any` with `unknown` and narrow at the boundary, or define a "
        "proper type. For ORM queries use the generated types (Prisma.WhereInput, etc.). "
        "For payloads use Zod parsing.\n"
        "Bypass (genuine third-party gap with no alternative): set AS_ANY_DISABLE=1.",
        file=sys.stderr,
    )
    _audit(hook="as-any-blocker", decision="block", tool=tool, reason="TypeScript any usage", command_excerpt=" | ".join(findings)[:240] if findings else None)
    return 2


if __name__ == "__main__":
    sys.exit(main())
