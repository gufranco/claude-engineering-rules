#!/usr/bin/env python3
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.audit_log import record as _audit  # noqa: E402


from _lib.hook_profile import should_run  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.shell_segments import strip_heredoc_bodies, unquoted_segments  # noqa: E402
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


def _merges(segment: str) -> bool:
    if HELP_FLAG.search(f" {segment}"):
        return False
    return any(pattern.search(segment) for pattern in MERGE_PATTERNS)


def is_merge_command(command: str) -> bool:
    return any(
        _merges(strip_heredoc_bodies(segment)) for segment in unquoted_segments(command)
    )


BLOCK_MESSAGE = (
    "BLOCKED: merging a pull request is not permitted while a morning "
    "sweep is running.\n"
    "The /morning skill reviews, replies, and fixes. It never merges.\n"
    "To merge deliberately, finish the sweep first, then use /deploy land.\n"
    "The lock clears when the sweep ends, or on its own time-to-live.\n"
    "See: skills/morning/SKILL.md\n"
)


def _disabled() -> bool:
    if os.environ.get("PR_MERGE_BLOCKER_DISABLE") == "1":
        return True
    if is_bypassed("pr-merge-blocker"):
        return True
    return not should_run("pr-merge-blocker")


def _block(command: str) -> int:
    sys.stderr.write(f"{BLOCK_MESSAGE}Command: {command[:240]}\n")
    _audit(
        hook="pr-merge-blocker",
        decision="block",
        tool="Bash",
        reason="pull request merge during an active morning session",
        command_excerpt=command[:240],
    )
    return 2


def main() -> int:
    if _disabled():
        return 0
    data = read_hook_payload("pr-merge-blocker")
    tool_input = data.get("tool_input", data.get("input", {})) or {}
    command = tool_input.get("command", "")
    if not command:
        return 0
    if not is_merge_command(command):
        return 0
    if not is_locked(LOCK_NAME):
        return 0
    return _block(command)


if __name__ == "__main__":
    sys.exit(main())
