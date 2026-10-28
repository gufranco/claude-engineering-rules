#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.audit_log import record as _audit  # noqa: E402


from _lib.suppression import (
    compute_block_state,
    is_suppressed,
)

ESLINT_RULES = frozenset({"no-console"})
PATTERN = re.compile(r"\bconsole\.(log|warn|error|info|debug|trace)\s*\(")

JS_EXTS: tuple[str, ...] = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

SKIP_SEGMENTS: tuple[str, ...] = (
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

SKIP_FILENAMES: tuple[str, ...] = (
    "error.tsx",
    "global-error.tsx",
    "error.jsx",
)

SKIP_SUFFIXES: tuple[str, ...] = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
    ".config.ts",
    ".config.js",
    ".config.mjs",
    ".stories.ts",
    ".stories.tsx",
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.edit_resolution import payload_fragments  # noqa: E402


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
    fp = tool_input.get("file_path", "") or ""
    return [(fp, name, text) for name, text in payload_fragments(tool, tool_input)]


def find(text: str) -> list[str]:
    lines = text.splitlines()
    block_state = compute_block_state(lines, rules=ESLINT_RULES)
    hits: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        if is_suppressed(lines, i, block_state=block_state, rules=ESLINT_RULES):
            continue
        for m in PATTERN.finditer(line):
            hits.append(m.group(0))
    return hits


from _lib.hook_profile import should_run  # noqa: E402


HOOK_NAME = "console-log-blocker"
EXCERPT_LIMIT = 240


def _skipped() -> bool:
    if not should_run(HOOK_NAME):
        return True
    if os.environ.get("CONSOLE_LOG_DISABLE") == "1":
        _audit(
            hook=HOOK_NAME,
            decision="bypass",
            bypass_env="CONSOLE_LOG_DISABLE",
        )
        return True
    return is_bypassed(HOOK_NAME)


def _findings(items: list[tuple[str, str, str]]) -> list[str]:
    findings: list[str] = []
    for path, field, text in items:
        if is_skipped(path):
            continue
        hits = find(text)
        if hits:
            findings.append(f"  - {field} ({path}): {', '.join(sorted(set(hits)))}")
    return findings


def _report(tool: str, findings: list[str]) -> int:
    print(
        "Blocked: console.* calls in production code. "
        'Rule: ~/.claude/standards/code-style.md "Fundamentals".\n'
        + "\n".join(findings)
        + "\n\nFix: use the project's structured logger (Pino, Winston, @repo/logger, etc.). "
        "console is allowed only in tests, scripts, and Next.js error boundaries.\n"
        "Third-party tool directives are honored: @ts-expect-error, and an "
        "eslint-disable that names no rule or names no-console.\n"
        "Bypass (one-off, rare): set CONSOLE_LOG_DISABLE=1, or register a TTL-bound "
        "pass with `python3 ~/.claude/scripts/bypass.py set console-log-blocker`.",
        file=sys.stderr,
    )
    _audit(
        hook=HOOK_NAME,
        decision="block",
        tool=tool,
        reason="console.log in production",
        command_excerpt=" | ".join(findings)[:EXCERPT_LIMIT] if findings else None,
    )
    return 2


def main() -> int:
    if _skipped():
        return 0

    payload = read_hook_payload(HOOK_NAME)

    tool = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}

    findings = _findings(collect(tool, tool_input))
    if not findings:
        return 0
    return _report(tool, findings)


if __name__ == "__main__":
    sys.exit(main())
