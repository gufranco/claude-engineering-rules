#!/usr/bin/env python3
"""
redis-atomicity.py

PreToolUse hook that flags non-atomic Redis sequences.
Rule source: ~/.claude/standards/redis.md and ~/.claude/checklists/checklist.md cat 4.

  Two sequential Redis commands (e.g., INCRBY then EXPIRE) are not atomic.
  Use a Lua script (eval/evalsha), MULTI/EXEC pipeline, or a single-command equivalent
  (SET ... EX, SET ... NX EX).

Detected sequences (within 5 lines of each other on the same client):
  - INCR / INCRBY / INCRBYFLOAT  followed by  EXPIRE / PEXPIRE
  - SETNX / SET ... NX            followed by  EXPIRE / PEXPIRE
  - HSET / SADD / RPUSH / LPUSH   followed by  EXPIRE   (when first command creates the key)
  - GET                            followed by  SET (on the same key)  -> check-then-set TOCTOU

Skipped:
  - Test files
  - Lines wrapped in multi() / pipeline() / eval()
  - Files importing 'pipeline' or showing MULTI/EXEC markers nearby

Bypass:
  REDIS_ATOMICITY_DISABLE=1
"""

from __future__ import annotations

import json
import os
import re
import sys

JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".go", ".rb")

SKIP_SUFFIXES = (
    ".test.ts", ".test.tsx", ".test.js", ".test.jsx",
    ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx",
)
SKIP_SEGMENTS = (
    "/__tests__/", "/__test__/", "/test/", "/tests/",
    "/.claude/hooks/",
)

INCR_LIKE = re.compile(
    r"\.(?:incr|incrBy|incrby|incrByFloat|incrbyfloat|hincrBy|hincrby|sadd|hset|rpush|lpush|setnx|setNX)\s*\(",
    re.IGNORECASE,
)
EXPIRE_LIKE = re.compile(
    r"\.(?:expire|pexpire|expireAt|pexpireAt)\s*\(",
    re.IGNORECASE,
)
GET_LIKE = re.compile(r"\.(?:get|hget|smembers|lrange)\s*\(", re.IGNORECASE)
SET_LIKE = re.compile(r"\.(?:set|hset|sadd|lpush|rpush)\s*\(", re.IGNORECASE)

ATOMIC_MARKERS = re.compile(
    r"\b(?:multi\s*\(|pipeline\s*\(|exec\s*\(|eval\s*\(|evalsha\s*\(|MULTI|EXEC|defineCommand)\b",
    re.IGNORECASE,
)

WINDOW_LINES = 5


def is_skipped(path: str) -> bool:
    if not path:
        return True
    p = path.lower()
    if not p.endswith(JS_EXTS):
        return True
    if any(p.endswith(s) for s in SKIP_SUFFIXES):
        return True
    if any(seg in p for seg in SKIP_SEGMENTS):
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
    if ATOMIC_MARKERS.search(text):
        if len(ATOMIC_MARKERS.findall(text)) >= 2:
            return []

    lines = text.splitlines()
    hits: list[str] = []
    for i, line in enumerate(lines):
        if not (INCR_LIKE.search(line) or GET_LIKE.search(line)):
            continue
        for j in range(i + 1, min(i + 1 + WINDOW_LINES, len(lines))):
            window = "\n".join(lines[i:j + 1])
            if ATOMIC_MARKERS.search(window):
                break
            target = lines[j]
            if INCR_LIKE.search(line) and EXPIRE_LIKE.search(target):
                hits.append(
                    f"L{i + 1}->L{j + 1}: increment/setnx then expire (not atomic): "
                    f"{line.strip()[:80]} ... {target.strip()[:80]}"
                )
                break
            if GET_LIKE.search(line) and SET_LIKE.search(target):
                if ".set" in target.lower() or "hset" in target.lower():
                    hits.append(
                        f"L{i + 1}->L{j + 1}: get then set (TOCTOU race): "
                        f"{line.strip()[:80]} ... {target.strip()[:80]}"
                    )
                    break
    return hits


def main() -> int:
    if os.environ.get("REDIS_ATOMICITY_DISABLE") == "1":
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
            findings.extend(f"      {h}" for h in hits[:5])

    if not findings:
        return 0

    print(
        "Blocked: non-atomic Redis sequence detected. "
        "Rule: ~/.claude/standards/redis.md + checklist.md cat 4.\n"
        + "\n".join(findings)
        + "\n\nFix:\n"
        "  - Replace `INCRBY` + `EXPIRE` with a Lua script (`eval`) or `SET key val EX seconds` "
        "for counters that reset on TTL.\n"
        "  - Replace `SETNX` + `EXPIRE` with `SET key val NX EX seconds`.\n"
        "  - Replace `GET` then `SET` with a Lua script or a `WATCH/MULTI/EXEC` transaction.\n"
        "Bypass (when sequencing is intentional and safe): set REDIS_ATOMICITY_DISABLE=1.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
