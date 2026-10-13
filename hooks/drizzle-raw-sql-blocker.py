#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


EXECUTE_RE = re.compile(
    r"\b(?:db|database|drizzle|conn|client|tx|trx|transaction)\s*"
    r"\.\s*(?:execute|run|all|get)\s*\(\s*sql\s*[`(]",
)
SQL_RAW_RE = re.compile(
    r"\bsql\s*\.\s*raw\s*\(",
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


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
    if "/drizzle/" in p and "/drizzle/_meta/" not in p:
        return True
    if any(
        seg in p
        for seg in (
            "/schema/",
            "/db/schema",
            "/db/schemas/",
        )
    ):
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
    for match in EXECUTE_RE.finditer(text):
        hits.append(match.group(0) + "...")
    for match in SQL_RAW_RE.finditer(text):
        hits.append(match.group(0) + "...)")
    return hits


from _lib.hook_profile import should_run  # noqa: E402


def main() -> int:
    if not should_run("drizzle-raw-sql-blocker"):
        sys.exit(0)
    if os.environ.get("DRIZZLE_RAW_SQL_DISABLE") == "1":
        _audit(
            hook="drizzle-raw-sql-blocker",
            decision="bypass",
            bypass_env="DRIZZLE_RAW_SQL_DISABLE",
        )
        return 0
    if is_bypassed("drizzle-raw-sql-blocker"):
        return 0

    payload = read_hook_payload("drizzle-raw-sql-blocker")

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
            findings.append(
                f"  - {field} ({path or 'unknown'}): {', '.join(sorted(set(hits)))}"
            )

    if not findings:
        return 0

    print(
        "Blocked: Drizzle raw SQL is banned in application code. "
        'Rule: ~/.claude/standards/code-style.md "Fundamentals".\n'
        + "\n".join(findings)
        + "\n\nFix: express the query using Drizzle's query builder "
        "(db.select(), db.insert(), db.update(), db.delete()). The `sql` "
        "template is fine inside .where()/.orderBy()/.having() fragments, "
        "but not as a top-level db.execute() call.\n"
        "Bypass (when there is genuinely no query-builder equivalent): "
        "set DRIZZLE_RAW_SQL_DISABLE=1.",
        file=sys.stderr,
    )
    _audit(
        hook="drizzle-raw-sql-blocker",
        decision="block",
        tool=tool,
        reason="raw SQL outside migration",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
