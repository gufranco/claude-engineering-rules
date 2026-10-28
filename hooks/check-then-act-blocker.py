#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.hook_warning import emit_warning  # noqa: E402

from _lib.audit_log import record as _audit  # noqa: E402


from _lib.suppression import line_or_prev_has_suppression  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402


from _lib.hook_profile import should_run  # noqa: E402


from _lib.output import block, warn  # noqa: E402
from _lib.edit_resolution import payload_fragments  # noqa: E402

HOOK_ID = "check-then-act-blocker"
ENV_DISABLE = "CHECK_THEN_ACT_DISABLE"
ENV_ENFORCE = "CHECK_THEN_ACT_ENFORCE"

SOURCE_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".go", ".rb")

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
    "_test.go",
    "_test.py",
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

READ_CALL = re.compile(
    r"(?P<receiver>[A-Za-z_$][\w$.]*)\."
    r"(?P<method>findFirst|findUnique|findUniqueOrThrow|findFirstOrThrow|findOne|findById|"
    r"exists|existsBy|count|getItem|get_by|find_by)\s*\(",
)

WRITE_CALL = re.compile(
    r"(?P<receiver>[A-Za-z_$][\w$.]*)\."
    r"(?P<method>create|createMany|insert|insertOne|insertMany|save|put|putItem|add|bulkCreate)\s*\(",
)

ATOMIC_MARKERS = re.compile(
    r"\b(?:upsert|onConflict|onConflictDoNothing|onConflictDoUpdate|ON\s+CONFLICT|"
    r"ignoreDuplicates|skipDuplicates|updateMany|findOrCreate|get_or_create|"
    r"FOR\s+UPDATE|forUpdate|pg_advisory|advisory_lock|withLock)\b",
    re.IGNORECASE,
)

UNIQUE_VIOLATION_MARKERS = re.compile(
    r"\b(?:P2002|23505|ER_DUP_ENTRY|UniqueViolation|IntegrityError|duplicate\s+key|"
    r"unique\s+constraint|isUniqueViolation|ConditionalCheckFailed)\b",
    re.IGNORECASE,
)

RECEIVER_NOISE = re.compile(
    r"(repositories|repository|repos|repo|models|model|services|service|dao|store|"
    r"client|prisma|session|this)",
    re.IGNORECASE,
)

GENERIC_RECEIVERS = frozenset({"db", "tx", "trx", "conn", "connection", "orm", ""})

WINDOW_LINES = 12
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


def entity_of(receiver: str) -> str:
    parts = [part for part in receiver.split(".") if part]
    for candidate in reversed(parts):
        if candidate.lower() in GENERIC_RECEIVERS:
            continue
        stripped = RECEIVER_NOISE.sub("", candidate)
        normalized = re.sub(r"[^a-z]", "", stripped.lower())
        if normalized:
            return normalized.rstrip("s")
    return ""


def collect(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    path = tool_input.get("file_path", "") or ""
    return [(path, text) for _, text in payload_fragments(tool, tool_input)]


def _write_after(
    lines: list[str], index: int, read_entity: str
) -> tuple[int, str] | None:
    end = min(index + 1 + WINDOW_LINES, len(lines))
    for offset in range(index + 1, end):
        window = "\n".join(lines[index : offset + 1])
        if ATOMIC_MARKERS.search(window):
            return None
        if line_or_prev_has_suppression(lines, offset):
            return None
        write = WRITE_CALL.search(lines[offset])
        if write and entity_of(write.group("receiver")) == read_entity:
            return offset, write.group("method")
    return None


def _hit_at(lines: list[str], index: int) -> str | None:
    line = lines[index]
    read = READ_CALL.search(line)
    if not read or line_or_prev_has_suppression(lines, index):
        return None
    read_entity = entity_of(read.group("receiver"))
    if not read_entity:
        return None
    found = _write_after(lines, index, read_entity)
    if found is None:
        return None
    offset, write_method = found
    candidate = lines[offset]
    return (
        f"L{index + 1}->L{offset + 1}: {read.group('method')} decides, "
        f"{write_method} writes, entity `{read_entity}`: "
        f"{line.strip()[:70]} ... {candidate.strip()[:70]}"
    )


def find(text: str) -> list[str]:
    if UNIQUE_VIOLATION_MARKERS.search(text):
        return []
    lines = text.splitlines()
    hits = (_hit_at(lines, index) for index in range(len(lines)))
    return [hit for hit in hits if hit is not None]


DETECTED_INTRO = "A read that decides a write, followed by that write:"

WHY = (
    "Another actor runs between the two statements and takes the same branch, so\n"
    "both callers write. A double-click, a retry, a queue redelivery, or a second\n"
    "replica is enough. See ~/.claude/standards/concurrency.md, Race Taxonomy."
)

FIX = (
    "Pick a rung of the correctness ladder:\n"
    "  1. Unique constraint plus a handled unique violation. The database decides.\n"
    "  2. upsert, ON CONFLICT, or findOrCreate. One statement, decided by the engine.\n"
    "  3. An update guarded by the expected state, then handle the zero-rows result.\n"
    "  4. A row lock held across the read and the write, when the row already exists.\n"
    "A transaction alone does not fix this at read committed, because there is no\n"
    "row to lock until one of the actors creates it."
)

BYPASS_WHEN = (
    "The read and the write target genuinely unrelated rows, or a unique constraint\n"
    "already covers the write and the violation is handled further up the stack."
)


def render_findings(findings: list[tuple[str, list[str]]]) -> str:
    lines = [DETECTED_INTRO]
    for path, hits in findings:
        lines.append(f"{path}:")
        lines.extend(f"  {hit}" for hit in hits[:MAX_FINDINGS])
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
                "Rewrite using an atomic alternative. Set "
                f"{ENV_ENFORCE}=1 to make this a blocking check."
            ),
        )
    )
    _audit(
        hook=HOOK_ID,
        decision="warn",
        tool=tool,
        reason="check-then-act sequence",
        command_excerpt=detected[:240],
    )
    return 0


def _block(tool: str, detected: str) -> int:
    print(
        block(
            hook=HOOK_ID,
            rule_anchor="standards/concurrency.md#race-taxonomy",
            detected=detected,
            why=WHY,
            fix=FIX,
            bypass_when=BYPASS_WHEN,
            decision="FIX-AND-RETRY",
            env_var=ENV_DISABLE,
            safety="the race stays in the code and fails under concurrent load.",
        ),
        file=sys.stderr,
    )
    _audit(
        hook=HOOK_ID,
        decision="block",
        tool=tool,
        reason="check-then-act sequence",
        command_excerpt=detected[:240],
    )
    return 2


def main() -> int:
    if _skip():
        return 0

    payload = read_hook_payload("check-then-act-blocker")

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
