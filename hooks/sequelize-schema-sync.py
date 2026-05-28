#!/usr/bin/env python3
"""
sequelize-schema-sync.py

PreToolUse hook that blocks the most common Sequelize schema-drift sources:

  1. `sync({ force: true })` and `sync({ alter: true })` invocations outside
     test files. Both modes rewrite the schema without writing a migration.
     `force` additionally drops every table.
  2. `indexes` array entries that omit the `name` field. Sequelize's default
     naming is `<table>_<fields>`, which collides with raw-SQL index names
     and produces ambiguous diffs when fields are renamed.
  3. Umzug storage set to `'none'`, which disables migration tracking.

Rule source: ~/.claude/rules/lang/sequelize-migrations.md

Scope:
  Write/Edit/MultiEdit on *.ts/*.js files outside test directories.

Bypass:
  SEQUELIZE_SCHEMA_SYNC_DISABLE=1
  Use only for test fixtures and greenfield prototyping.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
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

SYNC_FORCE_RE = re.compile(
    r"\.\s*sync\s*\(\s*\{[^}]*\bforce\s*:\s*true\b",
    re.DOTALL,
)
SYNC_ALTER_RE = re.compile(
    r"\.\s*sync\s*\(\s*\{[^}]*\balter\s*:\s*true\b",
    re.DOTALL,
)
INDEX_ENTRY_RE = re.compile(
    r"\{\s*(?P<body>(?:[^{}]|\{[^{}]*\})*?fields\s*:\s*\[[^\]]+\][^}]*)\}",
    re.DOTALL,
)
INDEXES_ARRAY_RE = re.compile(
    r"\bindexes\s*:\s*\[",
)
UMZUG_NONE_STORAGE_RE = re.compile(
    r"\bstorage\s*:\s*['\"]none['\"]",
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


def find_indexes_without_name(text: str) -> list[str]:
    findings: list[str] = []
    for arr_match in INDEXES_ARRAY_RE.finditer(text):
        start = arr_match.end()
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        if i >= len(text):
            continue
        array_body = text[start:i]
        for entry in INDEX_ENTRY_RE.finditer(array_body):
            body = entry.group("body")
            if not re.search(r"\bname\s*:\s*['\"`]", body):
                summary = body.strip().replace("\n", " ")[:80]
                findings.append(
                    f"indexes entry without `name`: {{{summary}...}}. "
                    f"Add an explicit name field: name: '<Table>_<col>_idx'"
                )
    return findings


def find(text: str) -> list[str]:
    findings: list[str] = []
    if SYNC_FORCE_RE.search(text):
        findings.append(
            "sync({ force: true }) call. The mode drops every table on boot. "
            "Acceptable only inside test fixtures"
        )
    if SYNC_ALTER_RE.search(text):
        findings.append(
            "sync({ alter: true }) call. The mode mutates the schema in place "
            "without writing a migration. Use migrations instead"
        )
    if UMZUG_NONE_STORAGE_RE.search(text):
        findings.append(
            "Umzug `storage: 'none'` disables migration tracking. Every restart "
            "replays every migration. Use SequelizeMeta or a file-based storage"
        )
    findings.extend(find_indexes_without_name(text))
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
    from _lib.hook_profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main() -> int:
    if not should_run("sequelize-schema-sync"):
        _sys.exit(0)
    if os.environ.get("SEQUELIZE_SCHEMA_SYNC_DISABLE") == "1":
        _audit(
            hook="sequelize-schema-sync",
            decision="bypass",
            bypass_env="SEQUELIZE_SCHEMA_SYNC_DISABLE",
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
        "Blocked: Sequelize schema-sync defect. "
        "Rule: ~/.claude/rules/lang/sequelize-migrations.md.\n"
        + "\n".join(all_findings)
        + "\n\nFix: remove sync({ force/alter: true }) from application code, "
        "use migrations (sequelize-cli or umzug). Add an explicit `name` to every "
        "indexes entry. Use a real Umzug storage backend, not 'none'.\n"
        "Bypass (test fixtures only): set SEQUELIZE_SCHEMA_SYNC_DISABLE=1.",
        file=sys.stderr,
    )
    _audit(
        hook="sequelize-schema-sync",
        decision="block",
        tool=tool,
        reason="sequelize schema-sync defect",
        command_excerpt=" | ".join(all_findings)[:240] if all_findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
