#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.hook_input import read_hook_payload, tool_input_of  # noqa: E402

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.commit_scope import add_scope, commits_all, repo_dir, within  # noqa: E402
from _lib.git_invocation import strip_git_global_options  # noqa: E402
from _lib.output import block as _block  # noqa: E402

from _lib.audit_log import record as _audit_record  # noqa: E402

HOOK_NAME = "large-file-blocker"
ENV_DISABLE = "LARGE_FILE_DISABLE"
MAX_SIZE_KB = 5120
GIT_TIMEOUT_SECONDS = 5
COMMIT_PATTERN = re.compile(r"\bgit\s+commit\b")


def _read_command() -> tuple[str, str]:
    data = read_hook_payload("large-file-blocker")
    cmd = tool_input_of(data).get("command", "")
    cwd = data.get("cwd")
    return (cmd if isinstance(cmd, str) else ""), (cwd if isinstance(cwd, str) else "")


def _git(repo: str, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    return result.stdout if result.returncode == 0 else None


def _names(output: str | None) -> list[str]:
    return [name for name in (output or "").split("\0") if name]


def _staged_sizes(repo: str) -> dict[str, int]:
    names = _names(_git(repo, "diff", "--cached", "--name-only", "-z"))
    sizes = [_git(repo, "cat-file", "-s", f":{name}") for name in names]
    return {
        name: int(size)
        for name, size in zip(names, sizes)
        if size is not None and size.strip().isdigit()
    }


def _working_sizes(base: str, names: list[str]) -> dict[str, int]:
    paths = {name: os.path.join(base, name) for name in names}
    return {
        name: os.path.getsize(path)
        for name, path in paths.items()
        if os.path.isfile(path)
    }


def _pending_sizes(command: str, repo: str, top: str) -> dict[str, int]:
    whole, paths = add_scope(command)
    everything = whole or commits_all(command)
    if not (everything or paths):
        return {}
    tracked = [
        name
        for name in _names(_git(repo, "diff", "--name-only", "-z"))
        if everything or within(name, paths)
    ]
    untracked = (
        [
            name
            for name in _names(
                _git(repo, "ls-files", "--others", "--exclude-standard", "-z")
            )
            if whole or within(name, paths)
        ]
        if (whole or paths)
        else []
    )
    return {**_working_sizes(top, tracked), **_working_sizes(repo, untracked)}


def _offenders(command: str, cwd: str) -> list[tuple[str, int]]:
    repo = repo_dir(command, cwd)
    top = (_git(repo, "rev-parse", "--show-toplevel") or "").strip()
    if not top:
        return []
    staged = _staged_sizes(repo)
    pending = _pending_sizes(command, repo, top)
    merged = {
        name: max(staged.get(name, 0), pending.get(name, 0))
        for name in {*staged, *pending}
    }
    limit = MAX_SIZE_KB * 1024
    return sorted(
        (name, max(1, (size + 1023) // 1024))
        for name, size in merged.items()
        if size > limit
    )


def _audit(command: str) -> None:
    _audit_record(
        hook=HOOK_NAME,
        decision="block",
        decision_class="block",
        reason="staged file exceeds size limit",
        tool="Bash",
        command_excerpt=command[:200],
    )


def _block_message(offenders: list[tuple[str, int]]) -> str:
    detected = "\n".join(
        [f"{MAX_SIZE_KB}KB threshold exceeded by {len(offenders)} staged file(s):"]
        + [f"  {name} ({size_kb / 1024:.1f} MB)" for name, size_kb in offenders]
    )
    return _block(
        hook=HOOK_NAME,
        rule_anchor="standards/git-workflow.md (Ignored Artifacts)",
        detected=detected,
        why="Large binaries in git history bloat clones, slow CI, and waste storage forever.",
        fix=(
            "Unstage the file:\n"
            "  bad:  git add huge.bin && git commit\n"
            "  good: git reset HEAD huge.bin && git rm --cached huge.bin\n"
            "Add the path to .gitignore, or move it to Git LFS for tracked binaries."
        ),
        bypass_when=(
            "Intentionally tracking a vetted large asset (BIOS, IWAD, golden frame). "
            "Confirm with the user before bypassing in shared repos."
        ),
        decision="STOP-AND-ASK",
        env_var=ENV_DISABLE,
        safety="future large files in the same session will not be blocked.",
    )


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1":
        return 0
    if is_bypassed(HOOK_NAME):
        return 0
    command, cwd = _read_command()
    if not COMMIT_PATTERN.search(strip_git_global_options(command)):
        return 0
    offenders = _offenders(command, cwd)
    if not offenders:
        return 0
    sys.stderr.write(_block_message(offenders))
    _audit(command)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
