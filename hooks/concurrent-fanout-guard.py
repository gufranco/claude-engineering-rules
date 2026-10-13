#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.hook_warning import emit_warning  # noqa: E402

try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


try:
    from _lib.suppression import line_or_prev_has_suppression  # type: ignore
except Exception:  # pragma: no cover

    def line_or_prev_has_suppression(lines, line_no):  # type: ignore
        return False


try:
    from _lib.bypass import is_bypassed  # type: ignore
except Exception:  # pragma: no cover

    def is_bypassed(_hook: str) -> bool:  # type: ignore
        return False


try:
    from _lib.hook_profile import should_run  # type: ignore
except Exception:  # pragma: no cover

    def should_run(_id: str) -> bool:  # type: ignore
        return True


from _lib.output import block, warn  # noqa: E402

HOOK_ID = "concurrent-fanout-guard"
ENV_DISABLE = "CONCURRENT_FANOUT_DISABLE"
ENV_ENFORCE = "CONCURRENT_FANOUT_ENFORCE"

SOURCE_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

SKIP_SUFFIXES = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
    ".d.ts",
)
SKIP_SEGMENTS = (
    "/__tests__/",
    "/__test__/",
    "/test/",
    "/tests/",
    "/migrations/",
    "/migration/",
    "/seeds/",
    "/seed/",
    "/fixtures/",
    "/node_modules/",
    "/.claude/hooks/",
)

FANOUT_OPEN = re.compile(r"Promise\.(?:all|allSettled)\s*\(")

MAP_OVER_IDENTIFIER = re.compile(
    r"(?P<collection>[A-Za-z_$][\w$.]*)\s*\.\s*(?:map|flatMap)\s*\("
)

LIMITER_MARKERS = re.compile(
    r"\b(?:pLimit|p-limit|pMap|p-map|pAll|p-all|pQueue|p-queue|concurrency|"
    r"Bluebird|chunk|batchSize|inBatches|semaphore|Semaphore|limiter|throttle)\b"
)

CALLBACK_INVOKES_WORK = re.compile(
    r"=>\s*(?:async\s*)?[\s\S]*?\w\s*\(|\basync\b|\bawait\b"
)

RESOLVED_ONLY = re.compile(r"Promise\.resolve\s*\(")

MAX_FINDINGS = 5


def is_skipped(path: str) -> bool:
    if not path:
        return True
    lowered = path.lower()
    if not lowered.endswith(SOURCE_EXTS):
        return True
    if any(lowered.endswith(suffix) for suffix in SKIP_SUFFIXES):
        return True
    if any(segment in lowered for segment in SKIP_SEGMENTS):
        return True
    return False


def collect(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    path = tool_input.get("file_path", "") or ""
    items: list[tuple[str, str]] = []
    if tool == "Write":
        content = tool_input.get("content", "")
        if isinstance(content, str):
            items.append((path, content))
    elif tool == "Edit":
        content = tool_input.get("new_string", "")
        if isinstance(content, str):
            items.append((path, content))
    elif tool == "MultiEdit":
        for edit in tool_input.get("edits", []) or []:
            if isinstance(edit, dict):
                content = edit.get("new_string", "")
                if isinstance(content, str):
                    items.append((path, content))
    return items


def span_of_call(text: str, open_paren_index: int) -> tuple[int, int] | None:
    depth = 0
    for index in range(open_paren_index, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return open_paren_index, index
    return None


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _hit_for(text: str, lines: list[str], match: re.Match[str]) -> str | None:
    open_paren = text.index("(", match.start())
    span = span_of_call(text, open_paren)
    if span is None:
        return None
    start, end = span
    body = text[start + 1 : end]
    mapped = MAP_OVER_IDENTIFIER.search(body)
    if not mapped or not CALLBACK_INVOKES_WORK.search(body):
        return None
    if RESOLVED_ONLY.search(body):
        return None
    line_no = line_of(text, match.start())
    if line_or_prev_has_suppression(lines, line_no - 1):
        return None
    collection = mapped.group("collection")
    return (
        f"L{line_no}: unbounded fan-out over `{collection}`: "
        f"{lines[line_no - 1].strip()[:80] if line_no - 1 < len(lines) else ''}"
    )


def find(text: str) -> list[str]:
    if LIMITER_MARKERS.search(text):
        return []
    lines = text.splitlines()
    hits = (_hit_for(text, lines, match) for match in FANOUT_OPEN.finditer(text))
    return [hit for hit in hits if hit is not None][:MAX_FINDINGS]


DETECTED_INTRO = "Concurrent fan-out with no bound:"

WHY = (
    "The collection length comes from a caller or a query, so the concurrency is\n"
    "whatever the data happens to be. A large input opens that many simultaneous\n"
    "operations, which exhausts the connection pool, trips the downstream rate\n"
    "limit, and risks the whole batch on one overload. See\n"
    "~/.claude/standards/concurrency.md, Bounded fan-out."
)

FIX = (
    "  - Bound it: `const limit = pLimit(10)` then\n"
    "    `Promise.allSettled(items.map((item) => limit(() => work(item))))`.\n"
    "  - Or `pMap(items, work, { concurrency: 10 })`.\n"
    "  - Or process in explicit chunks when ordering matters.\n"
    "  - Prefer allSettled over all, so one rejection does not discard the work\n"
    "    that already succeeded. Classify the results afterwards."
)

BYPASS_WHEN = (
    "The collection has a known small bound that the type system cannot express,\n"
    "and the downstream call is in-process."
)


def render_findings(findings: list[tuple[str, list[str]]]) -> str:
    lines = [DETECTED_INTRO]
    for path, hits in findings:
        lines.append(f"{path}:")
        lines.extend(f"  {hit}" for hit in hits)
    return "\n".join(lines)


def _skip() -> bool:
    if not should_run(HOOK_ID):
        return True
    if os.environ.get(ENV_DISABLE) == "1":
        _audit(hook=HOOK_ID, decision="bypass", bypass_env=ENV_DISABLE)
        return True
    return is_bypassed(HOOK_ID)


def _findings(tool: str, tool_input: dict) -> list[tuple[str, list[str]]]:
    findings: list[tuple[str, list[str]]] = []
    for path, text in collect(tool, tool_input):
        if is_skipped(path):
            continue
        hits = find(text)
        if hits:
            findings.append((path, hits))
    return findings


def _warn(tool: str, detected: str) -> int:
    emit_warning(
        warn(
            hook=HOOK_ID,
            purpose=f"{detected}\n\n{WHY}\n\n{FIX}",
            next_action=(
                "Bound the concurrency. Set "
                f"{ENV_ENFORCE}=1 to make this a blocking check."
            ),
        )
    )
    _audit(
        hook=HOOK_ID,
        decision="warn",
        tool=tool,
        reason="unbounded fan-out",
        command_excerpt=detected[:240],
    )
    return 0


def _block(tool: str, detected: str) -> int:
    print(
        block(
            hook=HOOK_ID,
            rule_anchor="standards/concurrency.md#bounded-fan-out",
            detected=detected,
            why=WHY,
            fix=FIX,
            bypass_when=BYPASS_WHEN,
            decision="FIX-AND-RETRY",
            env_var=ENV_DISABLE,
            safety="a large input can saturate the pool and the downstream service.",
        ),
        file=sys.stderr,
    )
    _audit(
        hook=HOOK_ID,
        decision="block",
        tool=tool,
        reason="unbounded fan-out",
        command_excerpt=detected[:240],
    )
    return 2


def main() -> int:
    if _skip():
        return 0

    payload = read_hook_payload("concurrent-fanout-guard")

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    findings = _findings(tool, tool_input)
    if not findings:
        return 0

    detected = render_findings(findings)
    if os.environ.get(ENV_ENFORCE) != "1":
        return _warn(tool, detected)
    return _block(tool, detected)


if __name__ == "__main__":
    sys.exit(main())
