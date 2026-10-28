#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


PUSH_RE = re.compile(
    r"\bdrizzle-kit\s+push\b",
)
PUSH_NPX_RE = re.compile(
    r"\b(?:npx|pnpm\s+exec|pnpm\s+dlx|yarn\s+dlx|bunx|bun\s+x)\s+"
    r"drizzle-kit\s+push\b",
)
INDEX_CALL_RE = re.compile(
    r"\b(?:uniqueIndex|index)\s*\(\s*(?P<args>[^)]*)\)",
    re.DOTALL,
)

SCHEMA_EXT_RE = re.compile(
    r"\.(?:ts|tsx|js|jsx|mjs|cjs)$",
    re.IGNORECASE,
)
SCRIPT_PATH_HINTS_RE = re.compile(
    r"(?:"
    r"/\.github/workflows/[^/]+\.ya?ml$"
    r"|Dockerfile(?:\.[A-Za-z0-9_-]+)?$"
    r"|\.dockerfile$"
    r"|\.sh$"
    r"|/package\.json$"
    r")",
    re.IGNORECASE,
)
SKIP_PATH_HINTS = (
    "/test/",
    "/tests/",
    "/__tests__/",
    "/spec/",
    ".spec.",
    ".test.",
    "/e2e/",
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


def looks_like_drizzle_schema(text: str) -> bool:
    return (
        "drizzle-orm" in text
        or "pgTable(" in text
        or "mysqlTable(" in text
        or "sqliteTable(" in text
    )


def first_arg_is_string_literal(args: str) -> bool:
    stripped = args.lstrip()
    if not stripped:  # pragma: no cover - defensive; callers strip first
        return False
    return stripped[0] in ("'", '"', "`")


def is_skipped_test_path(path: str) -> bool:
    if not path:  # pragma: no cover - defensive; caller already guards on empty path
        return False
    p = path.lower()
    return any(seg in p for seg in SKIP_PATH_HINTS)


def find_in_schema(text: str) -> list[str]:
    findings: list[str] = []
    if not looks_like_drizzle_schema(text):
        return findings
    for match in INDEX_CALL_RE.finditer(text):
        args = match.group("args").strip()
        call = match.group(0)[:60]
        if not args or not first_arg_is_string_literal(args):
            findings.append(
                f"{call}... without an explicit name. Pass a string as the first "
                f"argument: index('<Table>_<column>_idx').on(table.col)"
            )
    return findings


def find_in_script(text: str) -> list[str]:
    findings: list[str] = []
    if PUSH_RE.search(text) or PUSH_NPX_RE.search(text):
        findings.append(
            "drizzle-kit push invocation in a deployment or CI script. The command "
            "rewrites the database schema without writing a migration file. Use "
            "`drizzle-kit migrate` against generated SQL files instead"
        )
    return findings


def _path_kind(fp: str) -> str | None:
    is_schema = bool(SCHEMA_EXT_RE.search(fp))
    is_script = bool(SCRIPT_PATH_HINTS_RE.search(fp))
    if not is_schema and not is_script:
        return None
    if is_schema and is_skipped_test_path(fp):
        return None
    return "script" if is_script else "schema"


def _multiedit_texts(tool_input: dict) -> list[tuple[str, str]]:
    edits = [
        (i, edit.get("new_string", ""))
        for i, edit in enumerate(tool_input.get("edits", []) or [])
        if isinstance(edit, dict)
    ]
    return [(f"edits[{i}].new_string", c) for i, c in edits if isinstance(c, str)]


def _edited_texts(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    if tool == "MultiEdit":
        return _multiedit_texts(tool_input)
    field = {"Write": "content", "Edit": "new_string"}.get(tool)
    if field is None:
        return []
    c = tool_input.get(field, "")
    return [(field, c)] if isinstance(c, str) else []


def collect(tool: str, tool_input: dict) -> list[tuple[str, str, str, str]]:
    fp = tool_input.get("file_path", "") or ""
    cmd = tool_input.get("command", "") or ""
    if tool == "Bash":
        return [("bash", "command", "", cmd)] if isinstance(cmd, str) and cmd else []
    kind = _path_kind(fp) if fp else None
    if kind is None:
        return []
    return [(kind, field, fp, c) for field, c in _edited_texts(tool, tool_input)]


def analyze(kind: str, text: str) -> list[str]:
    if kind == "schema":
        return find_in_schema(text)
    if kind == "script":
        return find_in_script(text)
    if kind == "bash":
        return find_in_script(text)
    return []  # pragma: no cover - defensive; collect() only emits known kinds


from _lib.hook_profile import should_run  # noqa: E402


def _disabled() -> bool:
    if not should_run("drizzle-schema-sync"):
        return True
    if os.environ.get("DRIZZLE_SCHEMA_SYNC_DISABLE") == "1":
        _audit(
            hook="drizzle-schema-sync",
            decision="bypass",
            bypass_env="DRIZZLE_SCHEMA_SYNC_DISABLE",
        )
        return True
    return is_bypassed("drizzle-schema-sync")


def _item_findings(field: str, path: str, hits: list[str]) -> list[str]:
    label = path or "(bash command)"
    return [f"  - {field} ({label}):", *(f"      {h}" for h in hits)]


def _all_findings(items: list[tuple[str, str, str, str]]) -> list[str]:
    analyzed = [(field, path, analyze(kind, text)) for kind, field, path, text in items]
    return [
        line
        for field, path, hits in analyzed
        if hits
        for line in _item_findings(field, path, hits)
    ]


def _report(tool: str, all_findings: list[str]) -> int:
    print(
        "Blocked: Drizzle schema-sync defect. "
        "Rule: ~/.claude/rules/lang/orm-migrations.md.\n"
        + "\n".join(all_findings)
        + "\n\nFix: replace `drizzle-kit push` with `drizzle-kit generate` + "
        "`drizzle-kit migrate` for any environment other than local dev. "
        "Pass an explicit name to every index() and uniqueIndex().\n"
        "Bypass (local dev only): set DRIZZLE_SCHEMA_SYNC_DISABLE=1.",
        file=sys.stderr,
    )
    _audit(
        hook="drizzle-schema-sync",
        decision="block",
        tool=tool,
        reason="drizzle schema-sync defect",
        command_excerpt=" | ".join(all_findings)[:240] if all_findings else None,
    )
    return 2


def main() -> int:
    if _disabled():
        return 0
    payload = read_hook_payload("drizzle-schema-sync")
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    all_findings = _all_findings(collect(tool, tool_input))
    if not all_findings:
        return 0
    return _report(tool, all_findings)


if __name__ == "__main__":
    sys.exit(main())
