#!/usr/bin/env python3
"""
migration-idempotency.py

PreToolUse hook that requires idempotent DDL in migration files.
Rule source: ~/.claude/rules/git-workflow.md "Migration Idempotency".

  - CREATE TABLE/INDEX/EXTENSION/MATERIALIZED VIEW/TYPE/FUNCTION must use IF NOT EXISTS
  - DROP TABLE/INDEX/EXTENSION/VIEW must use IF EXISTS

Scope: Write/Edit/MultiEdit on files under */migrations/* or *prisma/migrations*
       or files matching V<num>__*.sql (Flyway).

Bypass:
  MIGRATION_IDEMPOTENCY_DISABLE=1
"""

from __future__ import annotations

import json
import os
import re
import sys

MIGRATION_PATH_HINTS = (
    "/migrations/",
    "/prisma/migrations/",
    "/db/migrations/",
    "/database/migrations/",
)
FLYWAY_NAME = re.compile(r"/[VRU]\d+(?:_\d+)*__[^/]+\.sql$", re.IGNORECASE)

CREATE_BAD = re.compile(
    r"\bCREATE\s+(?!OR\s+REPLACE\b)"
    r"(?:UNIQUE\s+)?(?:CONCURRENTLY\s+)?"
    r"(TABLE|INDEX|EXTENSION|MATERIALIZED\s+VIEW|TYPE|FUNCTION|SCHEMA|SEQUENCE|TRIGGER|VIEW|ROLE|USER|POLICY)\b"
    r"(?!\s+(?:CONCURRENTLY\s+)?IF\s+NOT\s+EXISTS\b)",
    re.IGNORECASE,
)
DROP_BAD = re.compile(
    r"\bDROP\s+"
    r"(TABLE|INDEX|EXTENSION|MATERIALIZED\s+VIEW|TYPE|FUNCTION|SCHEMA|SEQUENCE|TRIGGER|VIEW|ROLE|USER|POLICY|COLUMN|CONSTRAINT)\b"
    r"(?!\s+IF\s+EXISTS\b)",
    re.IGNORECASE,
)
# CREATE INDEX without CONCURRENTLY locks the table in PostgreSQL. On large
# production tables this stalls writes long enough to cause an outage. Require
# CONCURRENTLY so the migration is non-blocking. The model can opt out of this
# check by setting MIGRATION_ALLOW_BLOCKING_INDEX=1 for a baseline migration.
CREATE_INDEX_BLOCKING = re.compile(
    r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\b(?!\s+CONCURRENTLY\b)",
    re.IGNORECASE,
)


def is_migration_path(path: str) -> bool:
    if not path:
        return False
    p = path.lower()
    if any(seg in p for seg in MIGRATION_PATH_HINTS):
        return True
    if FLYWAY_NAME.search(path):
        return True
    return False


def strip_comments(sql: str) -> str:
    no_block = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", "", no_block)


def collect(tool: str, tool_input: dict) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    fp = tool_input.get("file_path", "") or ""
    if not is_migration_path(fp):
        return out
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
    sql = strip_comments(text)
    hits: list[str] = []
    for m in CREATE_BAD.finditer(sql):
        hits.append(f"CREATE {m.group(1).upper()} without IF NOT EXISTS")
    for m in DROP_BAD.finditer(sql):
        hits.append(f"DROP {m.group(1).upper()} without IF EXISTS")
    if os.environ.get("MIGRATION_ALLOW_BLOCKING_INDEX") != "1":
        for _ in CREATE_INDEX_BLOCKING.finditer(sql):
            hits.append(
                "CREATE INDEX without CONCURRENTLY (locks the table on large "
                "PostgreSQL tables; set MIGRATION_ALLOW_BLOCKING_INDEX=1 to "
                "bypass for baseline or empty-table migrations)"
            )
    return hits


def main() -> int:
    if os.environ.get("MIGRATION_IDEMPOTENCY_DISABLE") == "1":
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
        hits = find(text)
        if hits:
            findings.append(f"  - {path}:")
            for h in sorted(set(hits)):
                findings.append(f"      {h}")

    if not findings:
        return 0

    print(
        "Blocked: migration is not idempotent. "
        "Rule: ~/.claude/rules/git-workflow.md \"Migration Idempotency\".\n"
        + "\n".join(findings)
        + "\n\nFix: every CREATE must use IF NOT EXISTS, every DROP must use IF EXISTS. "
        "For statements without native support (CREATE MATERIALIZED VIEW pre-Postgres 14), "
        "wrap in DO $$ BEGIN ... IF NOT EXISTS ... END $$.\n"
        "Bypass (rare, e.g., baseline migration): set MIGRATION_IDEMPOTENCY_DISABLE=1.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
