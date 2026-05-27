#!/usr/bin/env python3
"""Block bulk resolution of review threads.

The /respond skill requires each review thread to be resolved
individually, after its own action. Bulk-resolving via a loop or a
multi-threadId payload is a documented anti-pattern: it erases the
reviewer's ability to verify which concerns were addressed.

Platform coverage: GitHub via `gh api graphql resolveReviewThread`,
plus GitLab via `gh/glab api -X PUT ... resolved=true` patterns.
Bitbucket Cloud is out of scope because Bitbucket has no native
thread-resolution concept.

Detection:
  - Require an actual gh/glab API call invoking resolveReviewThread
    (GitHub) or PUT ... resolved=true (GitLab). Bare mentions in
    echo, comments, or test fixtures are ignored.
  - Count occurrences of resolveReviewThread in the command string.
  - Block when count > 1 (multi-call payload) or when the command
    runs inside a for/while/xargs loop.
  - Allow single resolve calls outside loops.

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.

Bypass: set BULK_RESOLVE_DISABLE=1 in the environment.
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


RESOLVE_MUTATION = re.compile(r"resolveReviewThread\b")
# Non-greedy so multiple gh api ... resolveReviewThread calls on the
# same line each count as one match.
GH_API_RESOLVE = re.compile(
    r"(?:gh|glab)\s+api[^\n]*?resolveReviewThread",
    re.IGNORECASE,
)
GLAB_RESOLVE = re.compile(
    r"(?:gh|glab)\s+api[^\n]*?-X\s+PUT[^\n]*?resolved=true",
    re.IGNORECASE,
)
FOR_LOOP_PATTERN = re.compile(r"\bfor\s+\w+\s+in\b")
WHILE_LOOP_PATTERN = re.compile(r"\bwhile\s+")
XARGS_PATTERN = re.compile(r"\|\s*xargs\b")


import sys as _sys, os as _os
_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.profile import should_run  # noqa: E402
except ImportError:
    def should_run(_id: str) -> bool:
        return True


def main() -> None:
    if not should_run("bulk-resolve-blocker"):
        _sys.exit(0)
    if os.environ.get("BULK_RESOLVE_DISABLE") == "1":
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = data.get("tool_input", data.get("input", {}))
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    github_calls = len(GH_API_RESOLVE.findall(command))
    gitlab_calls = len(GLAB_RESOLVE.findall(command))
    occurrences = github_calls + gitlab_calls

    # Skip if there is no actual resolve API call. A bare mention of
    # resolveReviewThread elsewhere in the command (echo, comment, test
    # fixture) is not a bulk operation.
    if occurrences == 0:
        sys.exit(0)

    in_loop = bool(
        FOR_LOOP_PATTERN.search(command)
        or WHILE_LOOP_PATTERN.search(command)
        or XARGS_PATTERN.search(command)
    )

    if occurrences > 1 or in_loop:
        platform = "GitHub" if github_calls else "GitLab"
        print(
            "BLOCKED: bulk resolution of review threads.\n"
            "Each review thread must be resolved individually after its own "
            "action. Bulk-resolving erases the reviewer's ability to verify "
            "which concerns were addressed.\n"
            "Either run one resolve mutation per thread, or set "
            "BULK_RESOLVE_DISABLE=1 in the environment if you have manually "
            "verified every thread.\n"
            f"Detected {occurrences} {platform} resolve call(s) in the "
            f"command{' inside a loop' if in_loop else ''}.\n"
            f"Command: {command[:240]}",
            file=sys.stderr,
        )
        _audit(
            hook="bulk-resolve-blocker",
            decision="block",
            tool="Bash",
            reason="bulk-resolve detected",
            occurrences=occurrences,
            in_loop=in_loop,
            command_excerpt=command[:240],
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
