#!/usr/bin/env python3
"""Block force-push when an open CHANGES_REQUESTED review exists.

Platform coverage: GitHub via `gh pr view --json reviews`. GitLab and
Bitbucket Cloud are out of scope because they expose review or
approval state through different endpoints; the `/respond` skill
documents the equivalents in the platform-* reference files.

Force-pushing during active review drops the reviewer's comment context
and marks all inline comments as outdated without resolving them. The
hook detects git push with --force or --force-with-lease, looks up the
current branch's PR, and blocks if any CHANGES_REQUESTED review is open.

The lookup uses gh pr view. If gh is unavailable, the hook allows the
push (fail-open) rather than block on infrastructure problems.

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.

Bypass: set FORCE_PUSH_DURING_REVIEW_DISABLE=1 in the environment.
"""

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
try:
    from audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


GIT_PUSH_PATTERN = re.compile(r"\bgit\s+push\b")
FORCE_FLAGS = re.compile(r"--force(?:-with-lease)?\b|(?:^|\s)-f(?:\s|$)")
FORCE_REFSPEC = re.compile(r"\+[^\s]+:?[^\s]*")


def is_force_push(command: str) -> bool:
    if not GIT_PUSH_PATTERN.search(command):
        return False
    if FORCE_FLAGS.search(command):
        return True
    push_idx = command.find("git push")
    if push_idx >= 0:
        tail = command[push_idx + len("git push") :]
        if FORCE_REFSPEC.search(tail):
            return True
    return False


def current_branch() -> str | None:
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch or None


def changes_requested_reviewer() -> str | None:
    """Returns the login of a reviewer who has CHANGES_REQUESTED open.

    Returns None if no such reviewer exists, or if the lookup fails.
    The hook fail-opens on lookup failure to avoid blocking on infrastructure
    problems.
    """
    branch = current_branch()
    if not branch:
        return None

    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                "--json",
                "reviews",
                "--jq",
                '.reviews[] | select(.state == "CHANGES_REQUESTED") | .author.login',
            ],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "NO_COLOR": "1"},
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None

    if result.returncode != 0:
        return None

    logins = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not logins:
        return None
    return logins[0]


def main() -> None:
    if os.environ.get("FORCE_PUSH_DURING_REVIEW_DISABLE") == "1":
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = data.get("tool_input", data.get("input", {}))
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    if not is_force_push(command):
        sys.exit(0)

    blocker = changes_requested_reviewer()
    if blocker is None:
        sys.exit(0)

    print(
        "BLOCKED: force-push during open CHANGES_REQUESTED review.\n"
        f"Reviewer `{blocker}` has an open blocking review on the current "
        "branch's PR. Force-pushing now drops their comment context and marks "
        "their inline comments as outdated without resolving them.\n"
        "Address the feedback first, push without force, or set "
        "FORCE_PUSH_DURING_REVIEW_DISABLE=1 in the environment if the "
        "force-push is the resolution.\n"
        f"Command: {command[:240]}",
        file=sys.stderr,
    )
    _audit(
        hook="force-push-during-review",
        decision="block",
        tool="Bash",
        reason="force-push with open CHANGES_REQUESTED review",
        blocker=blocker,
        command_excerpt=command[:240],
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
