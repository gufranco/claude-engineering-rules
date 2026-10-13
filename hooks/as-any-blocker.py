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

TS_EXTS: tuple[str, ...] = (".ts", ".tsx", ".mts", ".cts")

PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bas\s+any\b"), "as any"),
    (re.compile(r":\s*any(?=[\s,;)\]>=|&]|$)"), ": any"),
    (re.compile(r"<\s*any\s*>"), "<any>"),
    (re.compile(r"\bany\s*\[\s*\]"), "any[]"),
    (re.compile(r"<[^<>]*\bany\b[^<>]*>"), "generic with any"),
)

MAX_HITS_PER_FILE = 8
ESLINT_RULES = frozenset({"@typescript-eslint/no-explicit-any"})

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


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


def find(text: str) -> list[str]:
    lines = text.splitlines()
    block_state = compute_block_state(lines, rules=ESLINT_RULES)
    hits: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (
            stripped.startswith("//")
            or stripped.startswith("*")
            or stripped.startswith("/*")
        ):
            continue
        if is_suppressed(lines, i, block_state=block_state, rules=ESLINT_RULES):
            continue
        for pat, label in PATTERNS:
            m = pat.search(line)
            if m:
                hits.append(f"L{i + 1} ({label}): {stripped[:120]}")
                break
    return hits


from _lib.hook_profile import should_run  # noqa: E402


BLOCK_FOOTER = (
    "\n\nFix: replace `any` with `unknown` and narrow at the boundary, or define a "
    "proper type. For ORM queries use the generated types (Prisma.WhereInput, etc.). "
    "For payloads use Zod parsing.\n"
    "Third-party tool directives are honored: @ts-expect-error, and an "
    "eslint-disable that names no rule or names @typescript-eslint/no-explicit-any.\n"
    "Bypass (genuine third-party gap with no alternative): set AS_ANY_DISABLE=1, "
    "or register a TTL-bound pass with `python3 ~/.claude/scripts/bypass.py "
    "set as-any-blocker`."
)


def _skipped() -> bool:
    if os.environ.get("AS_ANY_DISABLE") == "1":
        _audit(hook="as-any-blocker", decision="bypass", bypass_env="AS_ANY_DISABLE")
        return True
    return is_bypassed("as-any-blocker")


def _file_findings(path: str, hits: list[str]) -> list[str]:
    lines = [f"  - {path}:", *(f"      {h}" for h in hits[:MAX_HITS_PER_FILE])]
    if len(hits) > MAX_HITS_PER_FILE:
        return [*lines, f"      ... and {len(hits) - MAX_HITS_PER_FILE} more"]
    return lines


def _findings(items: list[tuple[str, str, str]]) -> list[str]:
    findings: list[str] = []
    for path, _field, text in items:
        if is_skipped_path(path):
            continue
        hits = find(text)
        if hits:
            findings = [*findings, *_file_findings(path, hits)]
    return findings


def _block(tool: str, findings: list[str]) -> int:
    print(
        "Blocked: `any` type detected. "
        'Rule: ~/.claude/standards/code-style.md "Fundamentals".\n'
        + "\n".join(findings)
        + BLOCK_FOOTER,
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


def main() -> int:
    if not should_run("as-any-blocker"):
        sys.exit(0)
    if _skipped():
        return 0

    payload = read_hook_payload("as-any-blocker")

    tool = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}

    findings = _findings(collect(tool, tool_input))
    if not findings:
        return 0
    return _block(tool, findings)


if __name__ == "__main__":
    sys.exit(main())
