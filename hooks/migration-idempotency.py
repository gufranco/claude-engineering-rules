#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.audit_log import record as _audit  # noqa: E402


MIGRATION_PATH_HINTS = (
    "/migrations/",
    "/prisma/migrations/",
    "/db/migrations/",
    "/database/migrations/",
)
FLYWAY_NAME = re.compile(r"/[VRU]\d+(?:_\d+)*__[^/]+\.sql$", re.IGNORECASE)

CREATE_BAD = re.compile(
    r"\bCREATE\s+"
    r"(?:UNIQUE\s+)?(?:CONCURRENTLY\s+)?"
    r"(TABLE|INDEX|EXTENSION|MATERIALIZED\s+VIEW|SCHEMA|SEQUENCE)\b"
    r"(?!\s+(?:CONCURRENTLY\s+)?IF\s+NOT\s+EXISTS\b)",
    re.IGNORECASE,
)
CREATE_WITHOUT_REPLACE = re.compile(
    r"\bCREATE\s+(?:CONSTRAINT\s+)?(FUNCTION|VIEW|TRIGGER|PROCEDURE)\b",
    re.IGNORECASE,
)
CREATE_UNGUARDABLE = re.compile(r"\bCREATE\s+(TYPE|POLICY|ROLE|USER)\b", re.IGNORECASE)
DO_BLOCK = re.compile(r"\bDO\s+(\$\w*\$)(?P<body>.*?)\1", re.IGNORECASE | re.DOTALL)
DO_GUARD = re.compile(r"\bIF\s+NOT\s+EXISTS\b|\bEXCEPTION\s+WHEN\b", re.IGNORECASE)
DROP_BAD = re.compile(
    r"\bDROP\s+"
    r"(TABLE|INDEX|EXTENSION|MATERIALIZED\s+VIEW|TYPE|FUNCTION|SCHEMA|SEQUENCE|TRIGGER|VIEW|ROLE|USER|POLICY|COLUMN|CONSTRAINT)\b"
    r"(?!\s+IF\s+EXISTS\b)",
    re.IGNORECASE,
)
CREATE_INDEX_BLOCKING = re.compile(
    r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\b(?!\s+CONCURRENTLY\b)",
    re.IGNORECASE,
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.edit_resolution import payload_fragments  # noqa: E402


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
    fp = tool_input.get("file_path", "") or ""
    if not is_migration_path(fp):
        return []
    return [(fp, name, text) for name, text in payload_fragments(tool, tool_input)]


def strip_guarded_do_blocks(sql: str) -> str:
    return DO_BLOCK.sub(
        lambda m: "" if DO_GUARD.search(m.group("body")) else m.group(0), sql
    )


def find(text: str) -> list[str]:
    sql = strip_guarded_do_blocks(strip_comments(text))
    hits: list[str] = []
    for m in CREATE_BAD.finditer(sql):
        hits.append(f"CREATE {m.group(1).upper()} without IF NOT EXISTS")
    for m in CREATE_WITHOUT_REPLACE.finditer(sql):
        hits.append(f"CREATE {m.group(1).upper()} without OR REPLACE")
    for m in CREATE_UNGUARDABLE.finditer(sql):
        hits.append(f"CREATE {m.group(1).upper()} outside a guarded DO block")
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


from _lib.hook_profile import should_run  # noqa: E402


BLOCK_MESSAGE_HEAD = (
    "Blocked: migration is not idempotent. "
    'Rule: ~/.claude/standards/git-workflow.md "Migration Idempotency".\n'
)
BLOCK_MESSAGE_TAIL = (
    "\n\nFix: CREATE TABLE, INDEX, EXTENSION, MATERIALIZED VIEW, SCHEMA and SEQUENCE "
    "use IF NOT EXISTS; CREATE FUNCTION, VIEW, TRIGGER and PROCEDURE use OR REPLACE; "
    "CREATE TYPE, POLICY, ROLE and USER have no native guard, so wrap them in "
    "DO $$ BEGIN IF NOT EXISTS (SELECT ...) THEN ... END IF; END $$ or catch "
    "duplicate_object in an EXCEPTION block. Every DROP uses IF EXISTS.\n"
    "Bypass (rare, e.g., baseline migration): set MIGRATION_IDEMPOTENCY_DISABLE=1."
)


def _skip_run() -> bool:
    if not should_run("migration-idempotency"):
        sys.exit(0)
    if os.environ.get("MIGRATION_IDEMPOTENCY_DISABLE") == "1":
        _audit(
            hook="migration-idempotency",
            decision="bypass",
            bypass_env="MIGRATION_IDEMPOTENCY_DISABLE",
        )
        return True
    return is_bypassed("migration-idempotency")


def _findings(items: list[tuple[str, str, str]]) -> list[str]:
    findings: list[str] = []
    for path, _field, text in items:
        hits = find(text)
        if hits:
            findings.append(f"  - {path}:")
            findings.extend(f"      {h}" for h in sorted(set(hits)))
    return findings


def _block(tool: str, findings: list[str]) -> int:
    print(
        BLOCK_MESSAGE_HEAD + "\n".join(findings) + BLOCK_MESSAGE_TAIL,
        file=sys.stderr,
    )
    _audit(
        hook="migration-idempotency",
        decision="block",
        tool=tool,
        reason="non-idempotent migration",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


def main() -> int:
    if _skip_run():
        return 0
    payload = read_hook_payload("migration-idempotency")
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
