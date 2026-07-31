#!/usr/bin/env python3
"""
transaction-scope-guard.py

PreToolUse hook that keeps transaction scope tight.
Rule source: ~/.claude/standards/database.md "Transactions and Atomic Writes",
~/.claude/standards/concurrency.md, ~/.claude/checklists/checklist.md category 19.

Two detections:

  1. Network, email, queue, or sleep calls inside a transaction callback.
     A transaction holds row locks and a pooled connection for its whole life.
     An HTTP call inside one turns a third-party timeout into a database
     incident, and a retry of that call into a lock held for minutes.

  2. Array-mode transactions spanning more than one model. The array form runs
     independent statements; when statement B depends on statement A having
     succeeded, a failure in A still executes B in some drivers, which leaves
     partial state. Interactive mode is required for dependent writes.

Skipped: test files, migrations, seeds, fixtures, and this repo's own hooks.

Modes:
  default                      warn only, exit 0
  TRANSACTION_SCOPE_ENFORCE=1  block, exit 2

Bypass:
  TRANSACTION_SCOPE_DISABLE=1
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

HOOK_ID = "transaction-scope-guard"
ENV_DISABLE = "TRANSACTION_SCOPE_DISABLE"
ENV_ENFORCE = "TRANSACTION_SCOPE_ENFORCE"

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

TX_CALLBACK_OPEN = re.compile(r"(?:\$transaction|\.transaction|runInTransaction)\s*\(")

IO_CALLS = re.compile(
    r"\b(?:"
    r"fetch|axios|got|superagent|undici|ky|"
    r"sendEmail|sendMail|sendSms|sendNotification|notify|"
    r"stripe|twilio|sendgrid|mailgun|postmark|nodemailer|transporter|"
    r"s3Client|sqsClient|snsClient|sesClient|dynamoClient|"
    r"producer|publisher|webhook"
    r")\b\s*[.(]"
)

SLEEP_CALLS = re.compile(r"\b(?:sleep|setTimeout|setInterval|delay|wait)\s*\(")

ARRAY_TX_OPEN = re.compile(r"(?:\$transaction|\.transaction)\s*\(\s*\[")

MODEL_CALL = re.compile(r"\b(?:db|prisma|client|tx)\.(?P<model>[a-zA-Z_]\w*)\.\w+\s*\(")

MAX_FINDINGS = 6


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
    """Return the character span of a call whose opening paren is at the index.

    Returns None when the call never closes, which happens on a partial Edit
    payload. Callers treat that as "nothing to analyze" rather than guessing.
    """
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


def find_io_in_transactions(text: str) -> list[str]:
    hits: list[str] = []
    lines = text.splitlines()

    for match in TX_CALLBACK_OPEN.finditer(text):
        open_paren = text.index("(", match.start())
        span = span_of_call(text, open_paren)
        if span is None:
            continue
        start, end = span
        body = text[start:end]
        if body.lstrip("( \n\t").startswith("["):
            continue

        for io_match in IO_CALLS.finditer(body):
            absolute = start + io_match.start()
            line_no = line_of(text, absolute)
            if line_or_prev_has_suppression(lines, line_no - 1):
                continue
            snippet = (
                lines[line_no - 1].strip()[:80] if line_no - 1 < len(lines) else ""
            )
            hits.append(f"L{line_no}: I/O inside a transaction: {snippet}")

        for sleep_match in SLEEP_CALLS.finditer(body):
            absolute = start + sleep_match.start()
            line_no = line_of(text, absolute)
            if line_or_prev_has_suppression(lines, line_no - 1):
                continue
            snippet = (
                lines[line_no - 1].strip()[:80] if line_no - 1 < len(lines) else ""
            )
            hits.append(f"L{line_no}: a timer holds the transaction open: {snippet}")

    return hits


def find_array_mode_transactions(text: str) -> list[str]:
    hits: list[str] = []

    for match in ARRAY_TX_OPEN.finditer(text):
        open_paren = text.index("(", match.start())
        span = span_of_call(text, open_paren)
        if span is None:
            continue
        start, end = span
        body = text[start:end]
        models = {model.group("model") for model in MODEL_CALL.finditer(body)}
        if len(models) < 2:
            continue
        line_no = line_of(text, start)
        listed = ", ".join(sorted(models))
        hits.append(
            f"L{line_no}: array-mode transaction spanning {len(models)} models: {listed}"
        )

    return hits


def find(text: str) -> list[str]:
    return find_io_in_transactions(text) + find_array_mode_transactions(text)


DETECTED_INTRO = "Transaction scope problems:"

WHY = (
    "A transaction holds row locks and a pooled connection until it commits.\n"
    "Network or timer calls inside one turn a third-party stall into lock\n"
    "contention and connection-pool exhaustion. Array-mode transactions run\n"
    "independent statements, so a dependent second write is not protected by\n"
    "the failure of the first. See ~/.claude/standards/database.md and\n"
    "~/.claude/standards/concurrency.md."
)

FIX = (
    "  - Move the I/O before the transaction, or after it commits.\n"
    "  - When the effect must be tied to the commit, write an outbox row inside\n"
    "    the transaction and publish it from a separate worker.\n"
    "  - When the external call must happen first and can fail, use a compensating\n"
    "    action rather than a longer transaction.\n"
    "  - Replace array-mode transactions that carry dependent writes with the\n"
    "    interactive form, so a failure in the first statement prevents the second."
)

BYPASS_WHEN = (
    "The call named is in-process and does no I/O, such as a helper whose name\n"
    "collides with a client, or the array-mode statements are genuinely independent."
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
                    "Shrink the transaction to database work only. Set "
                    f"{ENV_ENFORCE}=1 to make this a blocking check."
                ),
            ),
            file=sys.stderr,
        )
        _audit(
            hook=HOOK_ID,
            decision="warn",
            tool=tool,
            reason="transaction scope",
            command_excerpt=detected[:240],
        )
        return 0

    print(
        block(
            hook=HOOK_ID,
            rule_anchor="standards/database.md#transactions-and-atomic-writes",
            detected=detected,
            why=WHY,
            fix=FIX,
            bypass_when=BYPASS_WHEN,
            decision="FIX-AND-RETRY",
            env_var=ENV_DISABLE,
            safety="long transactions and partial writes reach production unflagged.",
        ),
        file=sys.stderr,
    )
    _audit(
        hook=HOOK_ID,
        decision="block",
        tool=tool,
        reason="transaction scope",
        command_excerpt=detected[:240],
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
