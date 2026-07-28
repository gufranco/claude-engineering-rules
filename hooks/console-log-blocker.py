#!/usr/bin/env python3
"""console-log-blocker

PreToolUse hook that blocks console.log/warn/error/info/debug/trace in
production code. Rule source: ~/.claude/rules/code-style.md "Use the
project logger, never console".

Skipped paths:
  - Test files: *.test.*, *.spec.*, **/__tests__/**, **/__test__/**
  - Next.js error boundaries: **/error.tsx, **/global-error.tsx
  - Scripts and tools: **/scripts/**, **/bin/**, **/tools/**, **/cli/**
  - Config files: **/*.config.{js,ts,mjs}
  - Hooks themselves: ~/.claude/hooks/**

Third-party tool directives are honored, since they are the one comment form
the project ban exempts:
  `eslint-disable`, `eslint-disable-line`, `eslint-disable-next-line`,
  `@ts-expect-error`, `@ts-ignore`, `@ts-nocheck`,
  block ranges `/* eslint-disable */ ... /* eslint-enable */`.

There is no allow marker of our own. Legitimate console use lives in the
skipped paths above; everything else uses the project logger.

Bypass:
  CONSOLE_LOG_DISABLE=1, or a TTL entry via scripts/bypass.py
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


from _lib.suppression import (
    compute_block_state,
    is_suppressed,
)

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


def is_skipped(path: str) -> bool:
    """Skip non-JS/TS files, test directories, error boundaries, and configs."""
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
    """Return (file_path, field_name, text) tuples for Write/Edit/MultiEdit."""
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
    """Return console.* matches per line, honoring third-party tool directives."""
    lines = text.splitlines()
    block_state = compute_block_state(lines)
    hits: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        if is_suppressed(lines, i, block_state=block_state):
            continue
        for m in PATTERN.finditer(line):
            hits.append(m.group(0))
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
    if not should_run("console-log-blocker"):
        _sys.exit(0)
    if os.environ.get("CONSOLE_LOG_DISABLE") == "1":
        _audit(
            hook="console-log-blocker",
            decision="bypass",
            bypass_env="CONSOLE_LOG_DISABLE",
        )
        return 0
    if is_bypassed("console-log-blocker"):
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get("tool_name", "") or ""
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
        'Rule: ~/.claude/rules/code-style.md "Use the project logger, never console".\n'
        + "\n".join(findings)
        + "\n\nFix: use the project's structured logger (Pino, Winston, @repo/logger, etc.). "
        "console is allowed only in tests, scripts, and Next.js error boundaries.\n"
        "Third-party tool directives (eslint-disable, @ts-expect-error) are honored.\n"
        "Bypass (one-off, rare): set CONSOLE_LOG_DISABLE=1, or register a TTL-bound "
        "pass with `python3 ~/.claude/scripts/bypass.py set console-log-blocker`.",
        file=sys.stderr,
    )
    _audit(
        hook="console-log-blocker",
        decision="block",
        tool=tool,
        reason="console.log in production",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
