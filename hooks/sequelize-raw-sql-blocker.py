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


PATTERN = re.compile(
    r"\b(?:sequelize|db|database|connection|conn|sq)\s*\.\s*query\s*\(",
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
    if "/migrations/" in p or "/seeders/" in p or p.endswith(".sql"):
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
    for match in PATTERN.finditer(text):
        hits.append(match.group(0) + ")")
    return hits


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.hook_profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main() -> int:
    if not should_run("sequelize-raw-sql-blocker"):
        _sys.exit(0)
    if os.environ.get("SEQUELIZE_RAW_SQL_DISABLE") == "1":
        _audit(
            hook="sequelize-raw-sql-blocker",
            decision="bypass",
            bypass_env="SEQUELIZE_RAW_SQL_DISABLE",
        )
        return 0
    if is_bypassed("sequelize-raw-sql-blocker"):
        return 0

    payload = read_hook_payload("sequelize-raw-sql-blocker")

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
        "Blocked: Sequelize raw .query() is banned in application code. "
        'Rule: ~/.claude/standards/code-style.md "Fundamentals".\n'
        + "\n".join(findings)
        + "\n\nFix: express the query using Sequelize's model methods "
        "(findAll, findOne, update, destroy, bulkCreate). Raw .query() is only "
        "allowed in migration files and operational scripts.\n"
        "Bypass (when there is genuinely no model-method equivalent): "
        "set SEQUELIZE_RAW_SQL_DISABLE=1.",
        file=sys.stderr,
    )
    _audit(
        hook="sequelize-raw-sql-blocker",
        decision="block",
        tool=tool,
        reason="raw SQL outside migration",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
