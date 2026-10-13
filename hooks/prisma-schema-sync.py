#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.project_scope import walk_up
except ImportError:  # pragma: no cover
    sys.exit(0)
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


MIGRATION_PATH_RE = re.compile(
    r"/prisma/migrations/[^/]+/migration\.sql$", re.IGNORECASE
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


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


def parse_schema_models(schema_text: str) -> dict:
    """Return {model_name: {"table": str, "fields": set[str]}}.

    Honors @@map for table-name override and @map for column-name override.
    """
    out: dict = {}
    model_re = re.compile(r"^model\s+(\w+)\s*\{", re.MULTILINE)
    for match in model_re.finditer(schema_text):
        name = match.group(1)
        start = match.end()
        depth = 1
        i = start
        while i < len(schema_text) and depth > 0:
            ch = schema_text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            i += 1
        body = schema_text[start : i - 1]

        table = name
        m = re.search(r"@@map\s*\(\s*\"([^\"]+)\"", body)
        if m:
            table = m.group(1)

        fields: set = set()
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("@@"):
                continue
            field_match = re.match(r"(\w+)\s+\S+", stripped)
            if not field_match:
                continue
            field_name = field_match.group(1)
            map_match = re.search(r"@map\s*\(\s*\"([^\"]+)\"", line)
            fields.add(map_match.group(1) if map_match else field_name)
        out[name] = {"table": table, "fields": fields}
    return out


def parse_schema_indexes(schema_text: str) -> tuple[set, set]:
    """Return (index_map_names, unique_map_names)."""
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


def analyze(sql: str, schema_text: str) -> list[str]:
    sql = strip_comments(sql)
    findings: list[str] = []

    schema_idx, schema_unq = parse_schema_indexes(schema_text)
    models = parse_schema_models(schema_text)
    table_to_model = find_table_to_model(models)
    schema_tables = set(table_to_model.keys())

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

    for m in DROP_INDEX_RE.finditer(sql):
        name = m.group("name")
        if name in schema_idx or name in schema_unq:
            findings.append(
                f'DROP INDEX "{name}" but schema.prisma still declares it; '
                f"remove the matching @@index/@@unique entry"
            )

    for table, col in column_changes(sql, ADD_COLUMN_RE):
        model_name = table_to_model.get(table)
        if model_name is None:
            findings.append(
                f'ALTER TABLE "{table}" ADD COLUMN "{col}" but no model '
                f'maps to table "{table}" in schema.prisma'
            )
            continue
        if col not in models[model_name]["fields"]:
            findings.append(
                f'ALTER TABLE "{table}" ADD COLUMN "{col}" has no matching '
                f"field on model {model_name}"
            )

    for table, col in column_changes(sql, DROP_COLUMN_RE):
        model_name = table_to_model.get(table)
        if model_name and col in models[model_name]["fields"]:
            findings.append(
                f'ALTER TABLE "{table}" DROP COLUMN "{col}" but field still '
                f"present on model {model_name}; remove from schema.prisma"
            )

    for m in CREATE_TABLE_RE.finditer(sql):
        table = m.group("table")
        if table not in schema_tables:
            findings.append(
                f'CREATE TABLE "{table}" but no model in schema.prisma maps to it'
            )

    for m in DROP_TABLE_RE.finditer(sql):
        table = m.group("table")
        if table in schema_tables:
            findings.append(
                f'DROP TABLE "{table}" but model {table_to_model[table]} still '
                f"present in schema.prisma; remove the model block"
            )

    return findings


def collect(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    fp = tool_input.get("file_path", "") or ""
    if not is_prisma_migration(fp):
        return []
    out: list[tuple[str, str]] = []
    if tool == "Write":
        c = tool_input.get("content", "")
        if isinstance(c, str):
            out.append((fp, c))
    elif tool == "Edit":
        c = tool_input.get("new_string", "")
        if isinstance(c, str):
            out.append((fp, c))
    elif tool == "MultiEdit":
        merged = []
        for edit in tool_input.get("edits", []) or []:
            if isinstance(edit, dict):
                ns = edit.get("new_string", "")
                if isinstance(ns, str):
                    merged.append(ns)
        if merged:
            out.append((fp, "\n".join(merged)))
    return out


from _lib.hook_profile import should_run  # noqa: E402


def main() -> int:
    if not should_run("prisma-schema-sync"):
        sys.exit(0)
    if os.environ.get("PRISMA_SCHEMA_SYNC_DISABLE") == "1":
        _audit(
            hook="prisma-schema-sync",
            decision="bypass",
            bypass_env="PRISMA_SCHEMA_SYNC_DISABLE",
        )
        return 0
    if is_bypassed("prisma-schema-sync"):
        return 0

    payload = read_hook_payload("prisma-schema-sync")

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    items = collect(tool, tool_input)
    if not items:
        return 0

    all_findings: list[str] = []
    for path, sql in items:
        schema = find_schema(path)
        if schema is None:
            all_findings.append(
                f"  - {path}:\n      no schema.prisma found relative to migration path"
            )
            continue
        try:
            schema_text = schema.read_text(encoding="utf-8")
        except Exception as exc:
            all_findings.append(f"  - {path}:\n      failed to read {schema}: {exc}")
            continue
        findings = analyze(sql, schema_text)
        if findings:
            all_findings.append(f"  - {path}:")
            for f in findings:
                all_findings.append(f"      {f}")

    if not all_findings:
        return 0

    print(
        "Blocked: Prisma migration is out of sync with schema.prisma. "
        "Rule: ~/.claude/rules/lang/orm-migrations.md.\n"
        + "\n".join(all_findings)
        + '\n\nFix: every CREATE INDEX needs @@index(..., map: "<name>") on the model. '
        "Every ADD COLUMN needs a model field. Every DROP must remove the schema entry too. "
        "Verify with: prisma migrate diff --from-schema-datamodel <schema> "
        "--to-migrations <dir> --exit-code\n"
        "Bypass for unmanaged objects (extensions, materialized views, trgm indexes, "
        "triggers, RLS): set PRISMA_SCHEMA_SYNC_DISABLE=1 and record the reason "
        "in the pull request description or an ADR, never in a migration comment.",
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


if __name__ == "__main__":
    sys.exit(main())
