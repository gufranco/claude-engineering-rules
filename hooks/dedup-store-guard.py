#!/usr/bin/env python3
"""
dedup-store-guard.py

PreToolUse hook that rejects in-memory deduplication stores.
Rule source: ~/.claude/standards/idempotency.md "Storage",
~/.claude/rules/architecture-defaults.md "Deduplication Specifics",
~/.claude/checklists/checklist.md category 18.

    const processedEvents = new Set<string>();

    export async function handleWebhook(event: StripeEvent) {
      if (processedEvents.has(event.id)) return;
      processedEvents.add(event.id);
      await applyEffect(event);
    }

The set is empty after every deploy, every crash, and every scale-out. The
second replica has never seen any of the IDs the first replica processed, so
the duplicate the code appears to prevent is delivered anyway.

Detected: a module-level Set, Map, array, or dict whose name reads as a
deduplication ledger, such as `processedEvents`, `seenMessageIds`, or
`handledDeliveryIds`.

Silent for function-local collections, for single-flight promise maps, which
are process-local coordination rather than a dedup ledger, and for durable
stores.

Skipped: test files, migrations, seeds, fixtures, and this repo's own hooks.

Modes:
  default              warn only, exit 0
  DEDUP_STORE_ENFORCE=1  block, exit 2

Bypass:
  DEDUP_STORE_DISABLE=1
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

HOOK_ID = "dedup-store-guard"
ENV_DISABLE = "DEDUP_STORE_DISABLE"
ENV_ENFORCE = "DEDUP_STORE_ENFORCE"

SOURCE_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py")

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

DEDUP_NAME = re.compile(
    r"(?:processed|seen|handled|dedup|deduped|duplicate|dupe|idempoten|delivered|"
    r"consumed|acked|acknowledged|alreadyseen|alreadyprocessed|emitted|notified|sent)",
    re.IGNORECASE,
)

SINGLE_FLIGHT_NAME = re.compile(r"(?:inflight|pending|ongoing|running)", re.IGNORECASE)

JS_DECLARATION = re.compile(
    r"^(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)"
    r"(?:\s*:\s*[^=]+)?\s*=\s*(?P<init>new\s+Set\b|new\s+Map\b|\[\s*\])"
)

PY_DECLARATION = re.compile(
    r"^(?P<name>[A-Za-z_][\w]*)\s*(?::\s*[^=]+)?=\s*(?P<init>set\s*\(|dict\s*\(|\{\s*\}|\[\s*\])"
)

MEMBERSHIP_USE = re.compile(
    r"\.(?:has|includes|add|set|append|push)\s*\(|\bin\s+(?P<name>[A-Za-z_][\w$]*)"
)

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


def is_module_level(line: str) -> bool:
    return bool(line) and not line[0].isspace()


def is_used_for_membership(text: str, name: str) -> bool:
    pattern = re.compile(
        rf"\b{re.escape(name)}\s*\.\s*(?:has|includes|add|set|append|push)\s*\(|"
        rf"\bin\s+{re.escape(name)}\b"
    )
    return bool(pattern.search(text))


def find(text: str) -> list[str]:
    lines = text.splitlines()
    hits: list[str] = []

    for index, line in enumerate(lines):
        if not is_module_level(line):
            continue
        if line_or_prev_has_suppression(lines, index):
            continue

        match = JS_DECLARATION.match(line) or PY_DECLARATION.match(line)
        if not match:
            continue

        name = match.group("name")
        if SINGLE_FLIGHT_NAME.search(name):
            continue
        if not DEDUP_NAME.search(name):
            continue
        if not is_used_for_membership(text, name):
            continue

        hits.append(
            f"L{index + 1}: in-memory deduplication store `{name}`: {line.strip()[:80]}"
        )

    return hits[:MAX_FINDINGS]


DETECTED_INTRO = "Deduplication state held in process memory:"

WHY = (
    "A process-local collection is empty after every deploy, every crash, and on\n"
    "every replica that did not handle the first delivery. The duplicate the code\n"
    "appears to prevent is processed anyway, and the failure only appears under\n"
    "the conditions that matter. See ~/.claude/standards/idempotency.md, Storage."
)

FIX = (
    "  - Insert the dedup key into the same database transaction as the business\n"
    "    write, with a unique constraint on the key. A unique violation means the\n"
    "    work already happened.\n"
    "  - Or use Redis with persistence and a TTL longer than the sender's retry\n"
    "    window: SET key 1 NX EX <ttl>, and treat a null reply as a duplicate.\n"
    "  - The TTL must exceed the maximum redelivery window of the producer, which\n"
    "    is commonly three days for payment webhooks."
)

BYPASS_WHEN = (
    "The collection coordinates work inside one process rather than recording that\n"
    "a business effect already happened, such as a single-flight promise map."
)


def render_findings(findings: list[tuple[str, list[str]]]) -> str:
    lines = [DETECTED_INTRO]
    for path, hits in findings:
        lines.append(f"{path}:")
        lines.extend(f"  {hit}" for hit in hits)
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
                    "Move the dedup record to a durable store. Set "
                    f"{ENV_ENFORCE}=1 to make this a blocking check."
                ),
            ),
            file=sys.stderr,
        )
        _audit(
            hook=HOOK_ID,
            decision="warn",
            tool=tool,
            reason="in-memory dedup store",
            command_excerpt=detected[:240],
        )
        return 0

    print(
        block(
            hook=HOOK_ID,
            rule_anchor="standards/idempotency.md#storage",
            detected=detected,
            why=WHY,
            fix=FIX,
            bypass_when=BYPASS_WHEN,
            decision="FIX-AND-RETRY",
            env_var=ENV_DISABLE,
            safety="duplicate side effects ship, and only under restart or scale-out.",
        ),
        file=sys.stderr,
    )
    _audit(
        hook=HOOK_ID,
        decision="block",
        tool=tool,
        reason="in-memory dedup store",
        command_excerpt=detected[:240],
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
