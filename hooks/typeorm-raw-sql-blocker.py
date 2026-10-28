#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.audit_log import record as _audit  # noqa: E402


PATTERN = re.compile(
    r"\b(?:dataSource|appDataSource|connection|conn|manager|entityManager|"
    r"queryRunner|qr|repository|repo|orm|ds)\s*\.\s*query\s*\(",
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
    for match in PATTERN.finditer(text):
        hits.append(match.group(0) + ")")
    return hits


from _lib.hook_profile import should_run  # noqa: E402


def _disabled() -> bool:
    if not should_run("typeorm-raw-sql-blocker"):
        sys.exit(0)
    if os.environ.get("TYPEORM_RAW_SQL_DISABLE") == "1":
        _audit(
            hook="typeorm-raw-sql-blocker",
            decision="bypass",
            bypass_env="TYPEORM_RAW_SQL_DISABLE",
        )
        return True
    return is_bypassed("typeorm-raw-sql-blocker")


def _collect_findings(items: list[tuple[str, str, str]]) -> list[str]:
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


def _block_message(findings: list[str]) -> str:
    return (
        "Blocked: TypeORM raw .query() is banned in application code. "
        'Rule: ~/.claude/standards/code-style.md "Fundamentals".\n'
        + "\n".join(findings)
        + "\n\nFix: express the query using TypeORM's query builder "
        "(repository.createQueryBuilder(), find(), findOne(), update(), delete()). "
        "Raw .query() is only allowed in migration files and operational scripts.\n"
        "Bypass (when there is genuinely no query builder equivalent): "
        "set TYPEORM_RAW_SQL_DISABLE=1."
    )


def main() -> int:
    if _disabled():
        return 0

    payload = read_hook_payload("typeorm-raw-sql-blocker")

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    items = collect(tool, tool_input)
    if not items:
        return 0

    findings = _collect_findings(items)
    if not findings:
        return 0

    print(_block_message(findings), file=sys.stderr)
    _audit(
        hook="typeorm-raw-sql-blocker",
        decision="block",
        tool=tool,
        reason="raw SQL outside migration",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
