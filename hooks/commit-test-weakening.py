#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.assertion_weakening import TEST_CASE_RE, weakening_findings  # noqa: E402
from _lib.audit_log import record as _audit_record  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload, tool_input_of  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402
from _lib.output import block as _block  # noqa: E402
from _lib.staged_blobs import commit_request  # noqa: E402
from _lib.test_paths import is_test_file  # noqa: E402

HOOK_NAME = "commit-test-weakening"
ENV_DISABLE = "COMMIT_TEST_WEAKENING_DISABLE"
GIT_TIMEOUT_SECONDS = 20
UNREADABLE = "git could not compare the test files with the last commit"


def _git(directory: str, *args: str) -> subprocess.CompletedProcess[bytes] | None:
    try:
        return subprocess.run(
            ["git", "-C", directory, *args],
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _names(done: subprocess.CompletedProcess[bytes]) -> set[str]:
    return {name for name in done.stdout.decode("utf-8", "replace").split("\0") if name}


def _changed_tests(root: str) -> list[str] | None:
    tracked = _git(root, "diff", "HEAD", "--name-only", "-z", "--no-renames")
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if any(done is None or done.returncode != 0 for done in (tracked, untracked)):
        return None
    names = _names(tracked) | _names(untracked)
    return sorted(name for name in names if is_test_file(Path(name)))


def _committed(root: str, name: str) -> str:
    shown = _git(root, "show", f"HEAD:{name}")
    if shown is None or shown.returncode != 0:
        return ""
    return shown.stdout.decode("utf-8", "replace")


def _current(root: str, name: str) -> str:
    target = Path(root) / name
    return (
        target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
    )


def findings(directory: str) -> list[str]:
    top = _git(directory, "rev-parse", "--show-toplevel")
    head = _git(directory, "rev-parse", "--verify", "-q", "HEAD^{commit}")
    if any(done is None or done.returncode != 0 for done in (top, head)):
        return []
    root = top.stdout.decode().strip()
    names = _changed_tests(root)
    if names is None:
        return [UNREADABLE]
    sides = [(_committed(root, name), _current(root, name)) for name in names]
    suites = [pair for pair in sides if any(TEST_CASE_RE.search(text) for text in pair)]
    before = "\n".join(old for old, _ in suites)
    after = "\n".join(new for _, new in suites)
    return weakening_findings(before, after)


def _message(found: list[str]) -> str:
    return _block(
        hook=HOOK_NAME,
        rule_anchor="rules/testing.md",
        detected="Across every changed test file, against the last commit:\n"
        + "\n".join(f"  {finding}" for finding in found),
        why=(
            "A test or assertion is never weakened, skipped or deleted to make a change "
            "pass, whatever tool made the edit. A move nets to zero, so only a real loss "
            "reaches this block."
        ),
        fix=(
            "Restore the removed tests or assertions, or the skip marker that was added.\n"
            "A test moved to another file keeps its counts; check the new file is in the "
            "working tree."
        ),
        bypass_when=(
            "The user agreed that the behavior these tests covered was removed on purpose."
        ),
        decision="STOP-AND-ASK",
        env_var=ENV_DISABLE,
        safety="later commits in the session are not compared until the bypass expires.",
    )


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1" or is_bypassed(HOOK_NAME):
        return 0
    if not should_run(HOOK_NAME):
        return 0
    data = read_hook_payload(HOOK_NAME)
    command = tool_input_of(data).get("command", "")
    cwd = data.get("cwd")
    request = commit_request(
        command if isinstance(command, str) else "",
        cwd if isinstance(cwd, str) and cwd else os.getcwd(),
    )
    found = findings(request.directory) if request is not None else []
    if not found:
        return 0
    sys.stderr.write(_message(found))
    _audit_record(
        hook=HOOK_NAME,
        decision="block",
        decision_class="block",
        reason="commit weakens the test files",
        tool="Bash",
        command_excerpt=str(command)[:200],
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
