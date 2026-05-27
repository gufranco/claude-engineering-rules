#!/usr/bin/env python3
"""Block accidental mutations to PR review state.

Platform coverage: GitHub via `gh pr review` and `gh api ... reviews/...`
patterns. GitLab and Bitbucket Cloud are out of scope because their
review-state mutation APIs use different verbs and endpoints; the
`/respond` skill handles them separately via the platform-* reference
files.

Three patterns are blocked on GitHub:

  1. The PR author requesting changes on their own PR. Common confusion;
     authors should not block their own PR.
  2. Dismissing a review the running user did not author.
  3. Deleting a review the running user did not author.

The hook does not need to determine the actual reviewer identity at
runtime. The hook blocks the *form* of these actions, requiring an
explicit env-var acknowledgment for the rare case where the action is
intended. Defense in depth: the skill should never need this fallback.

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.

Bypass: set REVIEW_STATE_GUARD_DISABLE=1 in the environment.
"""

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


REQUEST_CHANGES_PATTERN = re.compile(
    r"gh\s+pr\s+review\b[^\n]*--event\s+REQUEST_CHANGES",
    re.IGNORECASE,
)

DISMISS_VIA_API = re.compile(
    r"gh\s+api\b[^\n]*pulls/[^/]+/reviews/\d+/dismissals\b",
    re.IGNORECASE,
)

DISMISS_VIA_PR_REVIEW = re.compile(
    r"gh\s+pr\s+review\b[^\n]*--event\s+DISMISS",
    re.IGNORECASE,
)

DELETE_REVIEW = re.compile(
    r"gh\s+api\b[^\n]*-X\s+DELETE\b[^\n]*pulls/[^/]+/reviews/\d+",
    re.IGNORECASE,
)

DELETE_REVIEW_ALT = re.compile(
    r"gh\s+api\b[^\n]*--method\s+DELETE\b[^\n]*pulls/[^/]+/reviews/\d+",
    re.IGNORECASE,
)


def detect_violation(command: str) -> tuple[str, str] | None:
    if REQUEST_CHANGES_PATTERN.search(command):
        return (
            "REQUEST_CHANGES",
            "Posting REQUEST_CHANGES on a PR review is reserved for reviewers. "
            "If you are the PR author, do not block your own PR. If you are a "
            "reviewer, confirm the action with the user before posting.",
        )

    if DISMISS_VIA_API.search(command) or DISMISS_VIA_PR_REVIEW.search(command):
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


import sys as _sys, os as _os
_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.profile import should_run  # noqa: E402
except ImportError:
    def should_run(_id: str) -> bool:
        return True


def main() -> None:
    if not should_run("review-state-guard"):
        _sys.exit(0)
    if os.environ.get("REVIEW_STATE_GUARD_DISABLE") == "1":
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = data.get("tool_input", data.get("input", {}))
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    result = detect_violation(command)
    if result is None:
        sys.exit(0)

    kind, explanation = result
    print(
        f"BLOCKED: review-state mutation ({kind}).\n"
        f"{explanation}\n"
        "If the action is intentional and you have user approval, set "
        "REVIEW_STATE_GUARD_DISABLE=1 in the environment.\n"
        f"Command: {command[:240]}",
        file=sys.stderr,
    )
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
