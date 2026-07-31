#!/usr/bin/env python3
"""
check-then-act-blocker.py

PreToolUse hook that flags a read which decides a write, followed by that write.
Rule source: ~/.claude/standards/concurrency.md "Race Taxonomy" and
~/.claude/rules/architecture-defaults.md "Hard Rules".

    const existing = await db.seat.findFirst({ where: { showId, row } });
    if (!existing) {
      await db.seat.create({ data: { showId, row, userId } });
    }

The await on the read yields. A second actor enters, sees no row, and both
create. The window between the two statements is the bug, and nothing in the
code makes it visible.

Detected: an existence-deciding read followed within WINDOW_LINES by a create
on the same entity, when no atomic alternative appears nearby.

Silent when the payload carries an atomic marker: upsert, ON CONFLICT, a unique
violation handled by code, a row lock, or an advisory lock.

Skipped: test files, migrations, seeds, fixtures, and this repo's own hooks.

Known blind spots, accepted deliberately. Entity matching is textual, so a read
and a write separated by an intermediate variable assignment are matched only
when the receiver names agree. Static detection of check-then-act is undecidable
in general; this hook targets the ORM call shapes that appear in practice.

Modes:
  default                   warn only, exit 0
  CHECK_THEN_ACT_ENFORCE=1  block, exit 2

Bypass:
  CHECK_THEN_ACT_DISABLE=1
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))

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
    """Reduce a call receiver to a comparable entity name.

    `db.user`, `tx.user`, `userRepository`, and `this.userRepo` all reduce to
    `user`, so a read and a write on the same entity match without a parser.
    Returns an empty string when the receiver carries no entity information.
    """
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


def find(text: str) -> list[str]:
    if UNIQUE_VIOLATION_MARKERS.search(text):
        return []

    lines = text.splitlines()
    hits: list[str] = []

    for index, line in enumerate(lines):
        read = READ_CALL.search(line)
        if not read:
            continue
        if line_or_prev_has_suppression(lines, index):
            continue

        read_entity = entity_of(read.group("receiver"))
        if not read_entity:
            continue

        end = min(index + 1 + WINDOW_LINES, len(lines))
        for offset in range(index + 1, end):
            candidate = lines[offset]
            window = "\n".join(lines[index : offset + 1])
            if ATOMIC_MARKERS.search(window):
                break
            if line_or_prev_has_suppression(lines, offset):
                break

            write = WRITE_CALL.search(candidate)
            if not write:
                continue
            if entity_of(write.group("receiver")) != read_entity:
                continue

            hits.append(
                f"L{index + 1}->L{offset + 1}: {read.group('method')} decides, "
                f"{write.group('method')} writes, entity `{read_entity}`: "
                f"{line.strip()[:70]} ... {candidate.strip()[:70]}"
            )
            break

    return hits


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


def main() -> int:
    if not should_run(HOOK_ID):
        return 0
    if os.environ.get(ENV_DISABLE) == "1":
        _audit(hook=HOOK_ID, decision="bypass", bypass_env=ENV_DISABLE)
        return 0
    if is_bypassed(HOOK_ID):
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    findings: list[tuple[str, list[str]]] = []
    for path, text in collect(tool, tool_input):
        if is_skipped(path):
            continue
        hits = find(text)
        if hits:
            findings.append((path, hits))

    if not findings:
        return 0

    detected = render_findings(findings)

    if os.environ.get(ENV_ENFORCE) != "1":
        print(
            warn(
                hook=HOOK_ID,
                purpose=f"{detected}\n\n{WHY}\n\n{FIX}",
                next_action=(
                    "Rewrite using an atomic alternative. Set "
                    f"{ENV_ENFORCE}=1 to make this a blocking check."
                ),
            ),
            file=sys.stderr,
        )
        _audit(
            hook=HOOK_ID,
            decision="warn",
            tool=tool,
            reason="check-then-act sequence",
            command_excerpt=detected[:240],
        )
        return 0

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


if __name__ == "__main__":
    sys.exit(main())
