#!/usr/bin/env python3
"""Block pull request merges while a `/morning` sweep is running.

`/morning` walks a queue of pull requests across several accounts and works
them on the user's behalf. The one thing it must never do is merge. Prose in
a skill file is not a control, so the prohibition lives here.

The block is session-scoped through `_lib/session_lock`. `/deploy land`
merges legitimately, and a global merge block would break it. The lock is
acquired when a `/morning` work loop starts and released when it ends, so
outside a sweep this hook is silent.

Deliberately out of scope, each for a reason:

  git merge            conflict resolution needs it, and it touches no remote
  gh pr update-branch  the branch-update lane is built on it
  gh pr review         approval is governed by per-item consent, not by this hook

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.
"""

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
    from _lib.hook_profile import should_run  # type: ignore
except ImportError:  # pragma: no cover

    def should_run(_id: str) -> bool:
        return True


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.session_lock import is_locked  # noqa: E402

LOCK_NAME = "morning"

HELP_FLAG = re.compile(r"\s--help\b|\s-h\b")

CLI_MERGE_SUBCOMMANDS = (
    re.compile(r"\bgh\s+pr\s+merge\b"),
    re.compile(r"\bglab\s+mr\s+merge\b"),
)

REST_MERGE_ENDPOINTS = (
    re.compile(r"\bpulls?/\d+/merge\b"),
    re.compile(r"\bmerge_requests/\d+/merge\b"),
    re.compile(r"\bpullrequests/\d+/merge\b"),
)

GRAPHQL_MERGE_MUTATIONS = (
    re.compile(r"\bmergePullRequest\b"),
    re.compile(r"\benablePullRequestAutoMerge\b"),
)

MERGE_PATTERNS = CLI_MERGE_SUBCOMMANDS + REST_MERGE_ENDPOINTS + GRAPHQL_MERGE_MUTATIONS


def is_merge_command(command: str) -> bool:
    """True when the command would merge a pull request on a remote."""
    if HELP_FLAG.search(command):
        return False
    return any(pattern.search(command) for pattern in MERGE_PATTERNS)


def main() -> int:
    if os.environ.get("PR_MERGE_BLOCKER_DISABLE") == "1":
        return 0
    if is_bypassed("pr-merge-blocker"):
        return 0
    if not should_run("pr-merge-blocker"):
        return 0

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        return 0

    tool_input = data.get("tool_input", data.get("input", {})) or {}
    command = tool_input.get("command", "")
    if not command:
        return 0

    if not is_merge_command(command):
        return 0

    if not is_locked(LOCK_NAME):
        return 0

    sys.stderr.write(
        "BLOCKED: merging a pull request is not permitted while a morning "
        "sweep is running.\n"
        "The /morning skill reviews, replies, and fixes. It never merges.\n"
        "To merge deliberately, finish the sweep first, then use /deploy land.\n"
        "The lock clears when the sweep ends, or on its own time-to-live.\n"
        "See: skills/morning/SKILL.md\n"
        f"Command: {command[:240]}\n"
    )
    _audit(
        hook="pr-merge-blocker",
        decision="block",
        tool="Bash",
        reason="pull request merge during an active morning session",
        command_excerpt=command[:240],
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
