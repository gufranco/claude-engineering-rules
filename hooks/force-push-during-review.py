#!/usr/bin/env python3
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.audit_log import record as _audit  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.git_invocation import (  # noqa: E402
    FORCE_PUSH_LONG,
    FORCE_PUSH_SHORT,
    FORCE_PUSH_WITH_LEASE,
    strip_git_global_options,
)

GIT_PUSH_PATTERN = re.compile(r"\bgit\s+push\b")
FORCE_FLAGS = re.compile(
    "|".join((FORCE_PUSH_LONG, FORCE_PUSH_SHORT, FORCE_PUSH_WITH_LEASE))
)
FORCE_REFSPEC = re.compile(r"\+[^\s]+:?[^\s]*")


def is_force_push(raw_command: str) -> bool:
    command = strip_git_global_options(raw_command)
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


LOOKUP_TIMEOUT_SECONDS = 10
NO_PULL_REQUEST = "no pull requests found"


class LookupFailed(Exception):
    pass


def _git(repo: str, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", repo, *args], capture_output=True, text=True, timeout=5
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def changes_requested_reviewer(repo: str) -> str | None:
    branch = _git(repo, "branch", "--show-current")
    remote = _git(repo, "remote", "get-url", "origin") or ""
    if not branch or "github.com" not in remote:
        return None
    query = '.latestReviews[] | select(.state == "CHANGES_REQUESTED") | .author.login'
    try:
        result = subprocess.run(
            ["gh", "pr", "view", "--json", "latestReviews", "--jq", query],
            capture_output=True,
            text=True,
            timeout=LOOKUP_TIMEOUT_SECONDS,
            cwd=repo,
            env={**os.environ, "NO_COLOR": "1"},
        )
    except (subprocess.SubprocessError, OSError) as error:
        raise LookupFailed(str(error)) from error
    if result.returncode != 0:
        if NO_PULL_REQUEST in result.stderr.lower():
            return None
        raise LookupFailed(result.stderr.strip() or f"gh exited {result.returncode}")
    logins = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return logins[0] if logins else None


from _lib.commit_scope import repo_dir  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402


def _disabled() -> bool:
    return (
        not should_run("force-push-during-review")
        or os.environ.get("FORCE_PUSH_DURING_REVIEW_DISABLE") == "1"
        or is_bypassed("force-push-during-review")
    )


def _blocking_reviewer(command: str, cwd: str) -> str | None:
    try:
        return changes_requested_reviewer(repo_dir(command, cwd))
    except LookupFailed as error:
        print(
            "BLOCKED: force-push, and the open review state could not be read: "
            f"{error}.\nCheck `gh auth status`, or set "
            "FORCE_PUSH_DURING_REVIEW_DISABLE=1 in the parent shell if the force-push "
            "is intended.",
            file=sys.stderr,
        )
        sys.exit(2)


def _block(command: str, blocker: str) -> None:
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


def main() -> None:
    if _disabled():
        sys.exit(0)
    data = read_hook_payload("force-push-during-review")
    tool_input = data.get("tool_input", data.get("input", {}))
    command = tool_input.get("command", "")
    if not command or not is_force_push(command):
        sys.exit(0)
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) else ""
    blocker = _blocking_reviewer(command, cwd)
    if blocker is None:
        sys.exit(0)
    _block(command, blocker)


if __name__ == "__main__":
    main()
