#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.audit_log import record as _audit  # noqa: E402


PATTERN = re.compile(
    r"\.\$\s*(?:queryRaw|executeRaw|queryRawUnsafe|executeRawUnsafe|queryRawTyped)\b"
)
ALT_PATTERN = re.compile(
    r"\b(?:prisma|tx|db|client)\s*\.\s*\$\s*(?:queryRaw|executeRaw|queryRawUnsafe|executeRawUnsafe)\b"
)
TAG_PATTERN = re.compile(
    r"\$\s*(?:queryRaw|executeRaw|queryRawUnsafe|executeRawUnsafe)\s*[`(]"
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.edit_resolution import payload_fragments  # noqa: E402


DOCUMENTATION_EXTENSIONS: tuple[str, ...] = (
    ".md",
    ".mdx",
    ".markdown",
    ".rst",
    ".txt",
)


def is_skipped_path(path: str) -> bool:
    if not path:
        return False
    p = path.lower()
    if p.endswith(DOCUMENTATION_EXTENSIONS):
        return True
    if "/migrations/" in p or p.endswith(".sql"):
        return True
    return False


def collect(tool: str, tool_input: dict) -> list[tuple[str, str, str]]:
    fp = tool_input.get("file_path", "") or ""
    return [(fp, name, text) for name, text in payload_fragments(tool, tool_input)]


def find(text: str) -> list[str]:
    hits: list[str] = []
    for pat in (PATTERN, ALT_PATTERN, TAG_PATTERN):
        for m in pat.finditer(text):
            hits.append(m.group(0))
    return hits


from _lib.hook_profile import should_run  # noqa: E402


BLOCK_MESSAGE_HEAD = (
    "Blocked: Prisma raw SQL is banned in application code. "
    'Rule: ~/.claude/standards/code-style.md "Fundamentals".\n'
)
BLOCK_MESSAGE_TAIL = (
    "\n\nFix: express the query using Prisma's typed methods "
    "(findMany, updateMany, createMany, etc.). Raw SQL is only allowed in migration files.\n"
    "Bypass (when there is genuinely no Prisma equivalent): set PRISMA_RAW_SQL_DISABLE=1."
)


def _skip_run() -> bool:
    if not should_run("prisma-raw-sql-blocker"):
        sys.exit(0)
    if os.environ.get("PRISMA_RAW_SQL_DISABLE") == "1":
        _audit(
            hook="prisma-raw-sql-blocker",
            decision="bypass",
            bypass_env="PRISMA_RAW_SQL_DISABLE",
        )
        return True
    return is_bypassed("prisma-raw-sql-blocker")


def _findings(items: list[tuple[str, str, str]]) -> list[str]:
    findings: list[str] = []
    for path, field, text in items:
        if is_skipped_path(path):
            continue
        hits = find(text)
        if hits:
            findings.append(
                f"  - {field} ({path or 'unknown'}): {', '.join(sorted(set(hits)))}"
            )
    return findings


def _block(tool: str, findings: list[str]) -> int:
    print(
        BLOCK_MESSAGE_HEAD + "\n".join(findings) + BLOCK_MESSAGE_TAIL,
        file=sys.stderr,
    )
    _audit(
        hook="prisma-raw-sql-blocker",
        decision="block",
        tool=tool,
        reason="raw SQL outside migration",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


def main() -> int:
    if _skip_run():
        return 0
    payload = read_hook_payload("prisma-raw-sql-blocker")
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    items = collect(tool, tool_input)
    if not items:
        return 0
    findings = _findings(items)
    if not findings:
        return 0
    return _block(tool, findings)


if __name__ == "__main__":
    sys.exit(main())
