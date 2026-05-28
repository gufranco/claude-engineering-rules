#!/usr/bin/env python3
"""
typeorm-schema-sync.py

PreToolUse hook that blocks the most common TypeORM schema-drift sources:

  1. `synchronize: true` in any DataSource/createConnection/TypeOrmModule config
     outside test files. Synchronize mutates the schema in place without
     writing a migration, breaking parity between entity decorators and
     migration history.
  2. Direct `.synchronize()` calls on a DataSource in application code.
  3. `@Index(...)`, `@Unique(...)`, and `@Check(...)` declarations without
     an explicit name argument. Default names are SHA1 hashes that collide
     with raw-SQL names and produce unreadable diffs.

Rule source: ~/.claude/rules/lang/typeorm-migrations.md

Scope:
  Write/Edit/MultiEdit on *.ts and *.js files that are not under
  */test/* or */__tests__/*.

Bypass:
  TYPEORM_SCHEMA_SYNC_DISABLE=1
  Use for greenfield prototyping where synchronize is intentional.
  Never bypass in code paths that run in staging or production.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
try:
    from audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


TS_EXT_RE = re.compile(r"\.(?:ts|tsx|js|jsx|mjs|cjs)$", re.IGNORECASE)
SKIP_PATH_HINTS = (
    "/test/",
    "/tests/",
    "/__tests__/",
    "/__mocks__/",
    "/spec/",
    ".spec.",
    ".test.",
    "/e2e/",
    "/fixtures/",
)

SYNCHRONIZE_TRUE_RE = re.compile(
    r"\bsynchronize\s*:\s*true\b",
)
DROP_SCHEMA_TRUE_RE = re.compile(
    r"\bdropSchema\s*:\s*true\b",
)
SYNC_CALL_RE = re.compile(
    r"\b(?:dataSource|connection|conn|ds|appDataSource|orm)\s*"
    r"\.\s*synchronize\s*\(",
)
DROP_DB_CALL_RE = re.compile(
    r"\b(?:dataSource|connection|conn|ds|appDataSource|orm)\s*"
    r"\.\s*dropDatabase\s*\(",
)

INDEX_DECORATOR_RE = re.compile(
    r"@Index\s*\(\s*(?P<args>[^)]*)\)",
    re.DOTALL,
)
UNIQUE_DECORATOR_RE = re.compile(
    r"@Unique\s*\(\s*(?P<args>[^)]*)\)",
    re.DOTALL,
)
CHECK_DECORATOR_RE = re.compile(
    r"@Check\s*\(\s*(?P<args>[^)]*)\)",
    re.DOTALL,
)


def is_skipped_path(path: str) -> bool:
    if not path:
        return False
    if not TS_EXT_RE.search(path):
        return True
    p = path.lower()
    if any(seg in p for seg in SKIP_PATH_HINTS):
        return True
    return False


def first_arg_is_string_literal(args: str) -> bool:
    stripped = args.lstrip()
    if not stripped:  # pragma: no cover - defensive; callers strip first
        return False
    return stripped[0] in ("'", '"', "`")


def has_top_level_comma(args: str) -> bool:
    depth = 0
    for ch in args:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":  # pragma: no cover - CHECK regex stops at first close paren
            depth -= 1
        elif ch == "," and depth == 0:
            return True
    return False


def find_decorator_without_name(
    text: str, pattern: re.Pattern, label: str
) -> list[str]:
    findings: list[str] = []
    for match in pattern.finditer(text):
        args = match.group("args").strip()
        if not args:
            findings.append(
                f"{label}() without an explicit name. Pass a string as the first "
                f"argument: {label}('<EntityName>_<column>_idx', [...])"
            )
            continue
        if not first_arg_is_string_literal(args):
            findings.append(
                f"{label}({args[:60]}...) without an explicit name. Pass a string "
                f"literal as the first argument to override TypeORM's SHA1 default"
            )
    return findings


def find_check_without_name(text: str) -> list[str]:
    findings: list[str] = []
    for match in CHECK_DECORATOR_RE.finditer(text):
        args = match.group("args").strip()
        if not args:
            findings.append(
                "@Check() without arguments. Pass a name and an expression: "
                "@Check('<Entity>_<purpose>_chk', '<expression>')"
            )
            continue
        if not has_top_level_comma(args):
            findings.append(
                f"@Check({args[:60]}...) without an explicit name argument. "
                f"TypeORM @Check requires two arguments: name first, then expression"
            )
    return findings


def find(text: str) -> list[str]:
    findings: list[str] = []
    if SYNCHRONIZE_TRUE_RE.search(text):
        findings.append(
            "synchronize: true in a DataSource/Connection config. The flag rewrites "
            "the schema without writing a migration. Remove it or set "
            "TYPEORM_SCHEMA_SYNC_DISABLE=1 if this is a local-only data source"
        )
    if DROP_SCHEMA_TRUE_RE.search(text):
        findings.append(
            "dropSchema: true in a DataSource/Connection config. The flag drops "
            "every table on boot. Acceptable only in test fixtures"
        )
    for match in SYNC_CALL_RE.finditer(text):
        findings.append(
            f"{match.group(0)}) call in application code. Use migrations: "
            f"`typeorm migration:generate` followed by `typeorm migration:run`"
        )
    for match in DROP_DB_CALL_RE.finditer(text):
        findings.append(
            f"{match.group(0)}) call in application code. Never call dropDatabase "
            f"from application code. Use a dedicated test fixture or operational script"
        )
    findings.extend(find_decorator_without_name(text, INDEX_DECORATOR_RE, "@Index"))
    findings.extend(find_decorator_without_name(text, UNIQUE_DECORATOR_RE, "@Unique"))
    findings.extend(find_check_without_name(text))
    return findings


def collect(tool: str, tool_input: dict) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    fp = tool_input.get("file_path", "") or ""
    if is_skipped_path(fp):
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


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main() -> int:
    if not should_run("typeorm-schema-sync"):
        _sys.exit(0)
    if os.environ.get("TYPEORM_SCHEMA_SYNC_DISABLE") == "1":
        _audit(
            hook="typeorm-schema-sync",
            decision="bypass",
            bypass_env="TYPEORM_SCHEMA_SYNC_DISABLE",
        )
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

    all_findings: list[str] = []
    for path, field, text in items:
        hits = find(text)
        if hits:
            all_findings.append(f"  - {field} ({path or 'unknown'}):")
            for h in hits:
                all_findings.append(f"      {h}")

    if not all_findings:
        return 0

    print(
        "Blocked: TypeORM schema-sync defect. "
        "Rule: ~/.claude/rules/lang/typeorm-migrations.md.\n"
        + "\n".join(all_findings)
        + "\n\nFix: set synchronize to false, write migrations with "
        "`typeorm migration:generate`, and pass explicit names to every "
        "@Index/@Unique/@Check decorator.\n"
        "Bypass (local dev only): set TYPEORM_SCHEMA_SYNC_DISABLE=1.",
        file=sys.stderr,
    )
    _audit(
        hook="typeorm-schema-sync",
        decision="block",
        tool=tool,
        reason="typeorm schema-sync defect",
        command_excerpt=" | ".join(all_findings)[:240] if all_findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
