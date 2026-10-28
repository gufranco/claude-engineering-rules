#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.project_scope import walk_up  # noqa: E402
from _lib.audit_log import record as _audit  # noqa: E402


MIGRATION_PATH_RE = re.compile(
    r"/prisma/migrations/[^/]+/migration\.sql$", re.IGNORECASE
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.edit_resolution import payload_fragments  # noqa: E402


def is_prisma_migration(path: str) -> bool:
    if not path:
        return False
    return bool(MIGRATION_PATH_RE.search(path))


def find_schema(migration_path: str) -> Path | None:
    p = Path(migration_path).resolve()
    for parent in walk_up(p.parent, limit=20):
        candidate = parent / "schema.prisma"
        if candidate.is_file():
            return candidate
        if parent.name in ("migrations", "prisma"):
            continue
        if (parent / "prisma" / "schema.prisma").is_file():
            return parent / "prisma" / "schema.prisma"
    return None


def strip_comments(sql: str) -> str:
    no_block = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", "", no_block)


CREATE_INDEX_RE = re.compile(
    r"\bCREATE\s+(?P<unique>UNIQUE\s+)?INDEX"
    r"(?:\s+CONCURRENTLY)?(?:\s+IF\s+NOT\s+EXISTS)?\s+"
    r'"?(?P<name>[A-Za-z0-9_]+)"?\s+ON\s+'
    r'"?(?P<table>[A-Za-z0-9_]+)"?',
    re.IGNORECASE,
)

DROP_INDEX_RE = re.compile(
    r"\bDROP\s+INDEX(?:\s+CONCURRENTLY)?(?:\s+IF\s+EXISTS)?\s+"
    r'"?(?P<name>[A-Za-z0-9_]+)"?',
    re.IGNORECASE,
)

ALTER_TABLE_RE = re.compile(
    r'\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?"?(?P<table>[A-Za-z0-9_]+)"?(?P<body>[^;]*)',
    re.IGNORECASE | re.DOTALL,
)
ADD_COLUMN_RE = re.compile(
    r'\bADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?"?(?P<col>[A-Za-z0-9_]+)"?',
    re.IGNORECASE,
)
DROP_COLUMN_RE = re.compile(
    r'\bDROP\s+COLUMN\s+(?:IF\s+EXISTS\s+)?"?(?P<col>[A-Za-z0-9_]+)"?', re.IGNORECASE
)

CREATE_TABLE_RE = re.compile(
    r"\bCREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+"
    r'"?(?P<table>[A-Za-z0-9_]+)"?',
    re.IGNORECASE,
)

DROP_TABLE_RE = re.compile(
    r"\bDROP\s+TABLE(?:\s+IF\s+EXISTS)?\s+"
    r'"?(?P<table>[A-Za-z0-9_]+)"?',
    re.IGNORECASE,
)


SCHEMA_INDEX_RE = re.compile(
    r"@@index\s*\([^)]*?\bmap\s*:\s*\"(?P<name>[^\"]+)\"",
    re.DOTALL,
)
SCHEMA_UNIQUE_RE = re.compile(
    r"@@unique\s*\([^)]*?\bmap\s*:\s*\"(?P<name>[^\"]+)\"",
    re.DOTALL,
)
FIELD_UNIQUE_RE = re.compile(
    r"(?<!@)@unique\s*\([^)]*?\bmap\s*:\s*\"(?P<name>[^\"]+)\""
)


MODEL_RE = re.compile(r"^model\s+(\w+)\s*\{", re.MULTILINE)


def _block_end(schema_text: str, start: int) -> int:
    depth = 1
    i = start
    while i < len(schema_text) and depth > 0:
        ch = schema_text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    return i


def _model_table(name: str, body: str) -> str:
    m = re.search(r"@@map\s*\(\s*\"([^\"]+)\"", body)
    return m.group(1) if m else name


def _field_column(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("//") or stripped.startswith("@@"):
        return None
    field_match = re.match(r"(\w+)\s+\S+", stripped)
    if not field_match:
        return None
    map_match = re.search(r"@map\s*\(\s*\"([^\"]+)\"", line)
    return map_match.group(1) if map_match else field_match.group(1)


def _model_fields(body: str) -> set:
    columns = (_field_column(line) for line in body.splitlines())
    return {column for column in columns if column is not None}


def parse_schema_models(schema_text: str) -> dict:
    out: dict = {}
    for match in MODEL_RE.finditer(schema_text):
        name = match.group(1)
        start = match.end()
        body = schema_text[start : _block_end(schema_text, start) - 1]
        out[name] = {"table": _model_table(name, body), "fields": _model_fields(body)}
    return out


def parse_schema_indexes(schema_text: str) -> tuple[set, set]:
    idx = {m.group("name") for m in SCHEMA_INDEX_RE.finditer(schema_text)}
    unq = {
        m.group("name")
        for pattern in (SCHEMA_UNIQUE_RE, FIELD_UNIQUE_RE)
        for m in pattern.finditer(schema_text)
    }
    return idx, unq


def column_changes(sql: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    return [
        (alter.group("table"), column.group("col"))
        for alter in ALTER_TABLE_RE.finditer(sql)
        for column in pattern.finditer(alter.group("body"))
    ]


def find_table_to_model(models: dict) -> dict:
    return {info["table"]: name for name, info in models.items()}


def _create_index_findings(sql: str, schema_idx: set, schema_unq: set) -> list[str]:
    findings: list[str] = []
    for m in CREATE_INDEX_RE.finditer(sql):
        name = m.group("name")
        is_unique = bool(m.group("unique"))
        target = schema_unq if is_unique else schema_idx
        kind = "@@unique" if is_unique else "@@index"
        if name not in target:
            findings.append(
                f'CREATE {"UNIQUE " if is_unique else ""}INDEX "{name}" has no '
                f'matching {kind}(map: "{name}") in schema.prisma'
            )
    return findings


def _drop_index_findings(sql: str, schema_idx: set, schema_unq: set) -> list[str]:
    return [
        f'DROP INDEX "{m.group("name")}" but schema.prisma still declares it; '
        f"remove the matching @@index/@@unique entry"
        for m in DROP_INDEX_RE.finditer(sql)
        if m.group("name") in schema_idx or m.group("name") in schema_unq
    ]


def _add_column_finding(
    table: str, col: str, models: dict, table_to_model: dict
) -> str | None:
    model_name = table_to_model.get(table)
    if model_name is None:
        return (
            f'ALTER TABLE "{table}" ADD COLUMN "{col}" but no model '
            f'maps to table "{table}" in schema.prisma'
        )
    if col not in models[model_name]["fields"]:
        return (
            f'ALTER TABLE "{table}" ADD COLUMN "{col}" has no matching '
            f"field on model {model_name}"
        )
    return None


def _column_findings(sql: str, models: dict, table_to_model: dict) -> list[str]:
    added = (
        _add_column_finding(table, col, models, table_to_model)
        for table, col in column_changes(sql, ADD_COLUMN_RE)
    )
    findings = [finding for finding in added if finding is not None]
    for table, col in column_changes(sql, DROP_COLUMN_RE):
        model_name = table_to_model.get(table)
        if model_name and col in models[model_name]["fields"]:
            findings.append(
                f'ALTER TABLE "{table}" DROP COLUMN "{col}" but field still '
                f"present on model {model_name}; remove from schema.prisma"
            )
    return findings


def _table_findings(sql: str, table_to_model: dict) -> list[str]:
    created = [
        f'CREATE TABLE "{m.group("table")}" but no model in schema.prisma maps to it'
        for m in CREATE_TABLE_RE.finditer(sql)
        if m.group("table") not in table_to_model
    ]
    dropped = [
        f'DROP TABLE "{m.group("table")}" but model {table_to_model[m.group("table")]} '
        f"still present in schema.prisma; remove the model block"
        for m in DROP_TABLE_RE.finditer(sql)
        if m.group("table") in table_to_model
    ]
    return [*created, *dropped]


def analyze(sql: str, schema_text: str) -> list[str]:
    sql = strip_comments(sql)
    schema_idx, schema_unq = parse_schema_indexes(schema_text)
    models = parse_schema_models(schema_text)
    table_to_model = find_table_to_model(models)
    return [
        *_create_index_findings(sql, schema_idx, schema_unq),
        *_drop_index_findings(sql, schema_idx, schema_unq),
        *_column_findings(sql, models, table_to_model),
        *_table_findings(sql, table_to_model),
    ]


def collect(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    fp = tool_input.get("file_path", "") or ""
    if not is_prisma_migration(fp):
        return []
    texts = [text for _, text in payload_fragments(tool, tool_input)]
    return [(fp, "\n".join(texts))] if texts else []


from _lib.hook_profile import should_run  # noqa: E402


BLOCK_MESSAGE_HEAD = (
    "Blocked: Prisma migration is out of sync with schema.prisma. "
    "Rule: ~/.claude/rules/lang/orm-migrations.md.\n"
)
BLOCK_MESSAGE_TAIL = (
    '\n\nFix: every CREATE INDEX needs @@index(..., map: "<name>") on the model. '
    "Every ADD COLUMN needs a model field. Every DROP must remove the schema entry too. "
    "Verify with: prisma migrate diff --from-schema-datamodel <schema> "
    "--to-migrations <dir> --exit-code\n"
    "Bypass for unmanaged objects (extensions, materialized views, trgm indexes, "
    "triggers, RLS): set PRISMA_SCHEMA_SYNC_DISABLE=1 and record the reason "
    "in the pull request description or an ADR, never in a migration comment."
)


def _skip_run() -> bool:
    if not should_run("prisma-schema-sync"):
        sys.exit(0)
    if os.environ.get("PRISMA_SCHEMA_SYNC_DISABLE") == "1":
        _audit(
            hook="prisma-schema-sync",
            decision="bypass",
            bypass_env="PRISMA_SCHEMA_SYNC_DISABLE",
        )
        return True
    return is_bypassed("prisma-schema-sync")


def _item_findings(path: str, sql: str) -> list[str]:
    schema = find_schema(path)
    if schema is None:
        return [f"  - {path}:\n      no schema.prisma found relative to migration path"]
    try:
        schema_text = schema.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"  - {path}:\n      failed to read {schema}: {exc}"]
    findings = analyze(sql, schema_text)
    if not findings:
        return []
    return [f"  - {path}:", *(f"      {f}" for f in findings)]


def _block(tool: str, all_findings: list[str]) -> int:
    print(
        BLOCK_MESSAGE_HEAD + "\n".join(all_findings) + BLOCK_MESSAGE_TAIL,
        file=sys.stderr,
    )
    _audit(
        hook="prisma-schema-sync",
        decision="block",
        tool=tool,
        reason="schema-migration drift",
        command_excerpt=" | ".join(all_findings)[:240] if all_findings else None,
    )
    return 2


def main() -> int:
    if _skip_run():
        return 0
    payload = read_hook_payload("prisma-schema-sync")
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    items = collect(tool, tool_input)
    if not items:
        return 0
    all_findings = [line for path, sql in items for line in _item_findings(path, sql)]
    if not all_findings:
        return 0
    return _block(tool, all_findings)


if __name__ == "__main__":
    sys.exit(main())
