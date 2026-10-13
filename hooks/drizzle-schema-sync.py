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


def collect(tool: str, tool_input: dict) -> list[tuple[str, str, str, str]]:
    out: list[tuple[str, str, str, str]] = []
    fp = tool_input.get("file_path", "") or ""
    cmd = tool_input.get("command", "") or ""

    if tool == "Bash":
        if isinstance(cmd, str) and cmd:
            out.append(("bash", "command", "", cmd))
        return out

    if not fp:
        return out

    is_schema = bool(SCHEMA_EXT_RE.search(fp))
    is_script = bool(SCRIPT_PATH_HINTS_RE.search(fp))
    if not is_schema and not is_script:
        return out
    if is_schema and is_skipped_test_path(fp):
        return out

    kind = "script" if is_script else "schema"

    if tool == "Write":
        c = tool_input.get("content", "")
        if isinstance(c, str):
            out.append((kind, "content", fp, c))
    elif tool == "Edit":
        c = tool_input.get("new_string", "")
        if isinstance(c, str):
            out.append((kind, "new_string", fp, c))
    elif tool == "MultiEdit":
        for i, edit in enumerate(tool_input.get("edits", []) or []):
            if isinstance(edit, dict):
                c = edit.get("new_string", "")
                if isinstance(c, str):
                    out.append((kind, f"edits[{i}].new_string", fp, c))
    return out


def analyze(kind: str, text: str) -> list[str]:
    if kind == "schema":
        return find_in_schema(text)
    if kind == "script":
        return find_in_script(text)
    if kind == "bash":
        return find_in_script(text)
    return []  # pragma: no cover - defensive; collect() only emits known kinds


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.hook_profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main() -> int:
    if not should_run("drizzle-schema-sync"):
        _sys.exit(0)
    if os.environ.get("DRIZZLE_SCHEMA_SYNC_DISABLE") == "1":
        _audit(
            hook="drizzle-schema-sync",
            decision="bypass",
            bypass_env="DRIZZLE_SCHEMA_SYNC_DISABLE",
        )
        return 0
    if is_bypassed("drizzle-schema-sync"):
        return 0

    payload = read_hook_payload("drizzle-schema-sync")

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    items = collect(tool, tool_input)
    if not items:
        return 0

    all_findings: list[str] = []
    for kind, field, path, text in items:
        hits = analyze(kind, text)
        if hits:
            label = path or "(bash command)"
            all_findings.append(f"  - {field} ({label}):")
            for h in hits:
                all_findings.append(f"      {h}")

    if not all_findings:
        return 0

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


if __name__ == "__main__":
    sys.exit(main())
