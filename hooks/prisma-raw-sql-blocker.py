#!/usr/bin/env python3
"""
prisma-raw-sql-blocker.py

PreToolUse hook that blocks Prisma raw SQL methods in application code.
Rule source: ~/.claude/rules/code-style.md "No raw SQL" + standards/database.md.

Blocks: $queryRaw, $executeRaw, $queryRawUnsafe, $executeRawUnsafe.

Allowed paths (skipped):
  - Anything under */migrations/* or *prisma/migrations*
  - *.sql files

Bypass:
  PRISMA_RAW_SQL_DISABLE=1
"""

from __future__ import annotations

import json
import os
import re
import sys

PATTERN = re.compile(
    r"\.\$\s*(?:queryRaw|executeRaw|queryRawUnsafe|executeRawUnsafe|queryRawTyped)\b"
)
ALT_PATTERN = re.compile(
    r"\b(?:prisma|tx|db|client)\s*\.\s*\$\s*(?:queryRaw|executeRaw|queryRawUnsafe|executeRawUnsafe)\b"
)
TAG_PATTERN = re.compile(
    r"\$\s*(?:queryRaw|executeRaw|queryRawUnsafe|executeRawUnsafe)\s*[`(]"
)


def is_skipped_path(path: str) -> bool:
    if not path:
        return False
    p = path.lower()
    if "/migrations/" in p or p.endswith(".sql"):
        return True
    if "/seed" in p and (p.endswith(".sql") or "/migrations/" in p):
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
    hits: list[str] = []
    for pat in (PATTERN, ALT_PATTERN, TAG_PATTERN):
        for m in pat.finditer(text):
            hits.append(m.group(0))
    return hits


def main() -> int:
    if os.environ.get("PRISMA_RAW_SQL_DISABLE") == "1":
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
            findings.append(f"  - {field} ({path or 'unknown'}): {', '.join(sorted(set(hits)))}")

    if not findings:
        return 0

    print(
        "Blocked: Prisma raw SQL is banned in application code. "
        "Rule: ~/.claude/rules/code-style.md \"No raw SQL\".\n"
        + "\n".join(findings)
        + "\n\nFix: express the query using Prisma's typed methods "
        "(findMany, updateMany, createMany, etc.). Raw SQL is only allowed in migration files.\n"
        "Bypass (when there is genuinely no Prisma equivalent): set PRISMA_RAW_SQL_DISABLE=1.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
