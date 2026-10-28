#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.audit_log import record as _audit  # noqa: E402


from _lib.suppression import line_or_prev_has_suppression  # noqa: E402


JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".go", ".rb")

SKIP_SUFFIXES = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
)
SKIP_SEGMENTS = (
    "/__tests__/",
    "/__test__/",
    "/test/",
    "/tests/",
    "/.claude/hooks/",
)

RECEIVER = r"(?P<recv>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\.\s*"
INCR_LIKE = re.compile(
    RECEIVER
    + r"(?:incr|incrBy|incrby|incrByFloat|incrbyfloat|hincrBy|hincrby|sadd|hset|rpush|lpush|setnx|setNX)\s*\(",
    re.IGNORECASE,
)
EXPIRE_LIKE = re.compile(
    RECEIVER + r"(?:expire|pexpire|expireAt|pexpireAt)\s*\(", re.IGNORECASE
)
GET_LIKE = re.compile(RECEIVER + r"(?:get|hget|smembers|lrange)\s*\(", re.IGNORECASE)
SET_LIKE = re.compile(RECEIVER + r"(?:set|hset|sadd|lpush|rpush)\s*\(", re.IGNORECASE)
MAP_DECLARATION = re.compile(
    r"(?P<name>[A-Za-z_$][\w$]*)\s*(?::\s*(?:Readonly)?(?:Weak)?Map<[^=;\n]*)?=\s*new\s+(?:Weak)?Map\b"
    r"|(?P<typed>[A-Za-z_$][\w$]*)\s*:\s*(?:Readonly)?(?:Weak)?Map<"
)

ATOMIC_MARKERS = re.compile(
    r"\b(?:multi\s*\(|pipeline\s*\(|exec\s*\(|eval\s*\(|evalsha\s*\(|MULTI|EXEC|defineCommand)\b",
    re.IGNORECASE,
)

LOCK_ACQUIRE = re.compile(r"\.(?:set|setnx|setNX)\s*\(", re.IGNORECASE)
LOCK_NX_MARKER = re.compile(r"\bNX\b|\.setnx\s*\(|\.setNX\s*\(", re.IGNORECASE)
LOCK_TTL_MARKER = re.compile(r"\b(?:EX|PX|EXAT|PXAT|expiration|ttl)\b", re.IGNORECASE)

WINDOW_LINES = 5

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.edit_resolution import payload_fragments  # noqa: E402


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
    fp = tool_input.get("file_path", "") or ""
    return [(fp, name, text) for name, text in payload_fragments(tool, tool_input)]


def _map_names(text: str) -> frozenset[str]:
    return frozenset(
        m.group("name") or m.group("typed") for m in MAP_DECLARATION.finditer(text)
    )


def _receiver(pattern: re.Pattern[str], line: str) -> str | None:
    match = pattern.search(line)
    return match.group("recv").split(".")[-1] if match else None


def _lock_hit(lines: list[str], i: int) -> list[str]:
    line = lines[i]
    if not (LOCK_ACQUIRE.search(line) and LOCK_NX_MARKER.search(line)):
        return []
    if LOCK_TTL_MARKER.search(line) or line_or_prev_has_suppression(lines, i):
        return []
    return [
        f"L{i + 1}: lock without a TTL (survives a crash of the holder): "
        f"{line.strip()[:80]}"
    ]


def _pair_hit(lines: list[str], i: int, j: int, maps: frozenset[str]) -> str | None:
    line, target = lines[i], lines[j]
    incr = _receiver(INCR_LIKE, line)
    if incr and incr not in maps and incr == _receiver(EXPIRE_LIKE, target):
        return (
            f"L{i + 1}->L{j + 1}: increment/setnx then expire (not atomic): "
            f"{line.strip()[:80]} ... {target.strip()[:80]}"
        )
    read = _receiver(GET_LIKE, line)
    if read and read not in maps and read == _receiver(SET_LIKE, target):
        return (
            f"L{i + 1}->L{j + 1}: get then set (TOCTOU race): "
            f"{line.strip()[:80]} ... {target.strip()[:80]}"
        )
    return None


def _race_hit(lines: list[str], i: int, maps: frozenset[str]) -> list[str]:
    if line_or_prev_has_suppression(lines, i):
        return []
    for j in range(i + 1, min(i + 1 + WINDOW_LINES, len(lines))):
        if ATOMIC_MARKERS.search("\n".join(lines[i : j + 1])):
            return []
        if line_or_prev_has_suppression(lines, j):
            return []
        hit = _pair_hit(lines, i, j, maps)
        if hit:
            return [hit]
    return []


def find(text: str) -> list[str]:
    lines = text.splitlines()
    maps = _map_names(text)
    return [
        hit
        for i in range(len(lines))
        for hit in (*_lock_hit(lines, i), *_race_hit(lines, i, maps))
    ]


from _lib.hook_profile import should_run  # noqa: E402


def _disabled() -> bool:
    if not should_run("redis-atomicity"):
        sys.exit(0)
    if os.environ.get("REDIS_ATOMICITY_DISABLE") == "1":
        _audit(
            hook="redis-atomicity",
            decision="bypass",
            bypass_env="REDIS_ATOMICITY_DISABLE",
        )
        return True
    return is_bypassed("redis-atomicity")


def _collect_findings(items: list[tuple[str, str, str]]) -> list[str]:
    findings: list[str] = []
    for path, _field, text in items:
        if is_skipped(path):
            continue
        hits = find(text)
        if hits:
            findings.append(f"  - {path}:")
            findings.extend(f"      {h}" for h in hits[:5])
    return findings


def _block_message(findings: list[str]) -> str:
    return (
        "Blocked: non-atomic Redis sequence detected. "
        "Rule: ~/.claude/standards/redis.md + checklist.md cat 4.\n"
        + "\n".join(findings)
        + "\n\nFix:\n"
        "  - Replace `INCRBY` + `EXPIRE` with a Lua script (`eval`) or `SET key val EX seconds` "
        "for counters that reset on TTL.\n"
        "  - Replace `SETNX` + `EXPIRE` with `SET key val NX EX seconds`.\n"
        "  - Replace `GET` then `SET` with a Lua script or a `WATCH/MULTI/EXEC` transaction.\n"
        "  - Give every lock a TTL: `SET lock token NX EX <seconds>`, with the TTL above\n"
        "    the p99 of the protected operation, and check a fencing token at the write.\n"
        "Bypass (when sequencing is intentional and safe): set REDIS_ATOMICITY_DISABLE=1."
    )


def main() -> int:
    if _disabled():
        return 0

    payload = read_hook_payload("redis-atomicity")

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    findings = _collect_findings(collect(tool, tool_input))
    if not findings:
        return 0

    print(_block_message(findings), file=sys.stderr)
    _audit(
        hook="redis-atomicity",
        decision="block",
        tool=tool,
        reason="non-atomic redis sequence",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
