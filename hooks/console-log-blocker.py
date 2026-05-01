#!/usr/bin/env python3
"""
console-log-blocker.py

PreToolUse hook that blocks console.log/warn/error/info/debug in production code.
Rule source: ~/.claude/rules/code-style.md "Use the project logger, never console".

Skipped paths:
  - Test files: *.test.*, *.spec.*, **/__tests__/**, **/__test__/**
  - Next.js error boundaries: **/error.tsx, **/global-error.tsx
  - Scripts and tools: **/scripts/**, **/bin/**, **/tools/**, **/cli/**
  - Config files: **/*.config.{js,ts,mjs}
  - Hooks themselves: ~/.claude/hooks/**

Bypass:
  CONSOLE_LOG_DISABLE=1
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


PATTERN = re.compile(r"\bconsole\.(log|warn|error|info|debug|trace)\s*\(")

JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

SKIP_SEGMENTS = (
    "/scripts/",
    "/bin/",
    "/tools/",
    "/cli/",
    "/__tests__/",
    "/__test__/",
    "/.claude/hooks/",
    "/test-utils/",
    "/testing/",
    "/e2e/",
)

SKIP_FILENAMES = (
    "error.tsx",
    "global-error.tsx",
    "error.jsx",
)

SKIP_SUFFIXES = (
    ".test.ts", ".test.tsx", ".test.js", ".test.jsx",
    ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx",
    ".config.ts", ".config.js", ".config.mjs",
    ".stories.ts", ".stories.tsx",
)


def is_skipped(path: str) -> bool:
    if not path:
        return True
    p = path.lower()
    if not p.endswith(JS_EXTS):
        return True
    if any(seg in p for seg in SKIP_SEGMENTS):
        return True
    base = p.rsplit("/", 1)[-1]
    if base in SKIP_FILENAMES:
        return True
    if any(p.endswith(suf) for suf in SKIP_SUFFIXES):
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
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        if "eslint-disable" in line:
            continue
        if i > 0 and "eslint-disable-next-line" in lines[i - 1]:
            continue
        for m in PATTERN.finditer(line):
            hits.append(m.group(0))
    return hits


def main() -> int:
    if os.environ.get("CONSOLE_LOG_DISABLE") == "1":
        _audit(hook="console-log-blocker", decision="bypass", bypass_env="CONSOLE_LOG_DISABLE")
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
        if is_skipped(path):
            continue
        hits = find(text)
        if hits:
            findings.append(f"  - {field} ({path}): {', '.join(sorted(set(hits)))}")

    if not findings:
        return 0

    print(
        "Blocked: console.* calls in production code. "
        "Rule: ~/.claude/rules/code-style.md \"Use the project logger, never console\".\n"
        + "\n".join(findings)
        + "\n\nFix: use the project's structured logger (Pino, Winston, @repo/logger, etc.). "
        "console is allowed only in tests, scripts, and Next.js error boundaries.\n"
        "Bypass (one-off, rare): set CONSOLE_LOG_DISABLE=1.",
        file=sys.stderr,
    )
    _audit(hook="console-log-blocker", decision="block", tool=tool, reason="console.log in production", command_excerpt=" | ".join(findings)[:240] if findings else None)
    return 2


if __name__ == "__main__":
    sys.exit(main())
