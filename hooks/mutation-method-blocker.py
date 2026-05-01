#!/usr/bin/env python3
"""
mutation-method-blocker.py

PreToolUse hook that blocks Array.push() and Array.sort() mutations.
Rule source: ~/.claude/rules/code-style.md "Immutability".

  - .push() is banned. Use spread [...arr, item] or Array.from(). Only exception is
    router.push() / history.push() / navigation.push() from frameworks.
  - .sort() is banned. Use .toSorted(). If the target does not support ES2023, use
    [...arr].sort().

Skipped paths:
  - Test files (.test.*, .spec.*, **/__tests__/**)
  - Scripts (**/scripts/**, **/bin/**, **/tools/**, **/cli/**)
  - Hooks (~/.claude/hooks/**)

Allowed call patterns (not flagged):
  - router.push, Router.push, navigation.push, nav.push, history.push
  - pathname.push (next/navigation), routerRef.push
  - stream APIs: stream.push, Readable.push, res.push, ws.push
  - .push() with no leading identifier match where preceded by Buffer/stream context

Bypass:
  MUTATION_METHOD_DISABLE=1
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
    "/migrations/",
    "/seed",
)
SKIP_SUFFIXES = (
    ".test.ts", ".test.tsx", ".test.js", ".test.jsx",
    ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx",
    ".config.ts", ".config.js", ".config.mjs",
)

PUSH_ALLOWED_OWNERS = re.compile(
    r"\b(?:router|Router|history|navigation|nav|pathname|routerRef|location|stream|streams"
    r"|Readable|Writable|Duplex|Transform|res|response|ws|socket|client|stack|queue"
    r"|outputs?|errors|warnings|messages|logs|results|chunks)\.push\b"
)
PUSH_PATTERN = re.compile(r"(?P<owner>\w+)?\.push\s*\(")

SORT_PATTERN = re.compile(r"(?P<owner>\w+)?\.sort\s*\(")


def is_skipped(path: str) -> bool:
    if not path:
        return True
    p = path.lower()
    if not p.endswith(JS_EXTS):
        return True
    if any(seg in p for seg in SKIP_SEGMENTS):
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
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        if "eslint-disable" in line:
            continue
        for m in PUSH_PATTERN.finditer(line):
            seg = line[max(0, m.start() - 20):m.end() + 1]
            if PUSH_ALLOWED_OWNERS.search(seg):
                continue
            owner = m.group("owner") or ""
            allowed = re.match(
                r"^(?:router|Router|history|navigation|nav|pathname|routerRef|location"
                r"|stream|streams|Readable|Writable|Duplex|Transform|res|response|ws"
                r"|socket|client|stack|queue|outputs?|errors|warnings|messages|logs"
                r"|results|chunks)$",
                owner,
            )
            if allowed:
                continue
            hits.append(f"L{lineno}: {stripped[:100]}")
        for m in SORT_PATTERN.finditer(line):
            hits.append(f"L{lineno} (sort): {stripped[:100]}")
    return hits


def main() -> int:
    if os.environ.get("MUTATION_METHOD_DISABLE") == "1":
        _audit(hook="mutation-method-blocker", decision="bypass", bypass_env="MUTATION_METHOD_DISABLE")
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
            findings.append(f"  - {path}:")
            findings.extend(f"      {h}" for h in hits[:8])
            if len(hits) > 8:
                findings.append(f"      ... and {len(hits) - 8} more")

    if not findings:
        return 0

    print(
        "Blocked: array mutation methods (.push / .sort) in production code. "
        "Rule: ~/.claude/rules/code-style.md \"Immutability\".\n"
        + "\n".join(findings)
        + "\n\nFix:\n"
        "  - Replace arr.push(item) with arr = [...arr, item] or [...arr, item] in returns.\n"
        "  - Replace arr.sort(fn) with arr.toSorted(fn) (ES2023) or [...arr].sort(fn).\n"
        "  - Framework navigation (router.push, history.push) is auto-allowed.\n"
        "Bypass (rare, e.g., performance-critical hot path): set MUTATION_METHOD_DISABLE=1.",
        file=sys.stderr,
    )
    _audit(hook="mutation-method-blocker", decision="block", tool=tool, reason="mutating array method", command_excerpt=" | ".join(findings)[:240] if findings else None)
    return 2


if __name__ == "__main__":
    sys.exit(main())
