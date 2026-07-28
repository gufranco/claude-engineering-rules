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

Third-party tool directives are honored, since they are the one comment form
the project ban exempts:
  `eslint-disable`, `eslint-disable-line`, `eslint-disable-next-line`,
  `@ts-expect-error`, `@ts-ignore`, `@ts-nocheck`,
  block ranges `/* eslint-disable */ ... /* eslint-enable */`.

There is no allow marker of our own. The fix for an unavoidable `any` is
`unknown` plus a narrowing guard, which the type system checks.

Bypass:
  AS_ANY_DISABLE=1, or a TTL entry via scripts/bypass.py
"""

from __future__ import annotations

import json
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

TS_EXTS: tuple[str, ...] = (".ts", ".tsx", ".mts", ".cts")

PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bas\s+any\b"), "as any"),
    (re.compile(r":\s*any(?=[\s,;)\]>=|&]|$)"), ": any"),
    (re.compile(r"<\s*any\s*>"), "<any>"),
    (re.compile(r"\bany\s*\[\s*\]"), "any[]"),
    (re.compile(r"<[^<>]*\bany\b[^<>]*>"), "generic with any"),
)

MAX_HITS_PER_FILE = 8

from _lib.bypass import is_bypassed  # noqa: E402


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


def find(text: str) -> list[str]:
    """Return formatted hits for every line carrying an `any` pattern.

    Honors block-level eslint-disable plus line-level eslint and TypeScript
    directives. There is no allow marker of our own: narrow the type, or
    disable the hook out-of-band.
    """
    lines = text.splitlines()
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
        for pat, label in PATTERNS:
            m = pat.search(line)
            if m:
                hits.append(f"L{i + 1} ({label}): {stripped[:120]}")
                break
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
    if not should_run("as-any-blocker"):
        _sys.exit(0)
    if os.environ.get("AS_ANY_DISABLE") == "1":
        _audit(hook="as-any-blocker", decision="bypass", bypass_env="AS_ANY_DISABLE")
        return 0
    if is_bypassed("as-any-blocker"):
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
        "Third-party tool directives (eslint-disable, @ts-expect-error) are honored.\n"
        "Bypass (genuine third-party gap with no alternative): set AS_ANY_DISABLE=1, "
        "or register a TTL-bound pass with `python3 ~/.claude/scripts/bypass.py "
        "set as-any-blocker`.",
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
