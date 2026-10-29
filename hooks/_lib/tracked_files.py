from __future__ import annotations

import os
import re
import subprocess

from _lib.cli_invocations import invocations

TEST_SHAPED = re.compile(
    r"\.(?:test|spec)\.\w+$|(?:^|/)test_\w+\.py$|_test\.(?:py|go|rb)$"
    r"|(?:^|/)(?:__tests__|tests?)(?:/|$)"
)
GIT_RM = re.compile(r"\bgit\s+(?:-\S+\s+)*rm\b")
DELETERS = ("rm", "unlink", "trash")
GIT_TIMEOUT_SECONDS = 10


def _git(folder: str, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", folder, *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None


def never_committed(path: str) -> bool:
    if not os.path.exists(path):
        return False
    folder, name = os.path.split(os.path.abspath(path))
    listed = _git(folder, "ls-files", "--error-unmatch", "--", name)
    history = _git(folder, "log", "--all", "--format=%H", "-1", "--", name)
    if listed is None or history is None:
        return False
    return listed.returncode != 0 and not history.stdout.strip()


def removes_only_uncommitted_tests(command: str, cwd: str) -> bool:
    if GIT_RM.search(command):
        return False
    targets = [
        arg
        for name in DELETERS
        for call in invocations(command, name)
        for arg in call.args
        if not arg.startswith("-") and TEST_SHAPED.search(arg.rstrip("/"))
    ]
    return bool(targets) and all(
        never_committed(os.path.join(cwd, target)) for target in targets
    )
