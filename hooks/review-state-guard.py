#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


from _lib.cli_invocations import Invocation, invocations  # noqa: E402

SHORT_FLAG_CLUSTER = re.compile(r"-[a-zA-Z]+")

REQUEST_CHANGES_VIA_API = re.compile(
    r"gh\s+api\b[^\n]*pulls/[^/\s]+/reviews\b(?!/)[^\n]*event[\"']?\s*[=:]\s*[\"']?REQUEST_CHANGES"
    r"|gh\s+api\b[^\n]*event[\"']?\s*[=:]\s*[\"']?REQUEST_CHANGES[^\n]*pulls/[^/\s]+/reviews\b(?!/)",
    re.IGNORECASE,
)

DISMISS_VIA_API = re.compile(
    r"gh\s+api\b[^\n]*pulls/[^/]+/reviews/\d+/dismissals\b",
    re.IGNORECASE,
)


def _requests_changes(call: Invocation) -> bool:
    if call.args[:2] != ("pr", "review"):
        return False
    flags = call.args[2:]
    return any(
        arg == "--request-changes"
        or (SHORT_FLAG_CLUSTER.fullmatch(arg) is not None and "r" in arg[1:])
        for arg in flags
    )


DELETE_REVIEW = re.compile(
    r"gh\s+api\b[^\n]*-X\s+DELETE\b[^\n]*pulls/[^/]+/reviews/\d+",
    re.IGNORECASE,
)

DELETE_REVIEW_ALT = re.compile(
    r"gh\s+api\b[^\n]*--method\s+DELETE\b[^\n]*pulls/[^/]+/reviews/\d+",
    re.IGNORECASE,
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


def detect_violation(command: str) -> tuple[str, str] | None:
    if REQUEST_CHANGES_VIA_API.search(command) or any(
        _requests_changes(call) for call in invocations(command, "gh")
    ):
        return (
            "REQUEST_CHANGES",
            "Posting REQUEST_CHANGES on a PR review is reserved for reviewers. "
            "If you are the PR author, do not block your own PR. If you are a "
            "reviewer, confirm the action with the user before posting.",
        )

    if DISMISS_VIA_API.search(command):
        return (
            "DISMISS",
            "Dismissing a review mutes another contributor's blocking signal. "
            "The /respond skill never dismisses a review the running user did "
            "not author.",
        )

    if DELETE_REVIEW.search(command) or DELETE_REVIEW_ALT.search(command):
        return (
            "DELETE",
            "Deleting a review removes the audit trail of another contributor's "
            "feedback. Never delete a review the running user did not author.",
        )

    return None


from _lib.hook_profile import should_run  # noqa: E402


def _exit_when_disabled() -> None:
    if not should_run("review-state-guard"):
        sys.exit(0)
    if os.environ.get("REVIEW_STATE_GUARD_DISABLE") == "1":
        sys.exit(0)
    if is_bypassed("review-state-guard"):
        sys.exit(0)


def _block_message(kind: str, explanation: str, command: str) -> str:
    return (
        f"BLOCKED: review-state mutation ({kind}).\n"
        f"{explanation}\n"
        "If the action is intentional and you have user approval, set "
        "REVIEW_STATE_GUARD_DISABLE=1 in the environment.\n"
        f"Command: {command[:240]}"
    )


def main() -> None:
    _exit_when_disabled()

    data = read_hook_payload("review-state-guard")

    tool_input = data.get("tool_input", data.get("input", {}))
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    result = detect_violation(command)
    if result is None:
        sys.exit(0)

    kind, explanation = result
    print(_block_message(kind, explanation, command), file=sys.stderr)
    _audit(
        hook="review-state-guard",
        decision="block",
        tool="Bash",
        reason=f"review-state mutation: {kind}",
        command_excerpt=command[:240],
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
