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

try:
    from _lib.audit_log import record as _audit_record
except Exception:  # noqa: BLE001
    _audit_record = None  # type: ignore[assignment]

HOOK_NAME = "symlink-commit-blocker"
ENV_DISABLE = "SYMLINK_COMMIT_DISABLE"
SYMLINK_MODE = "120000"
GIT_TIMEOUT_SECONDS = 5
COMMIT_PATTERN = re.compile(r"\bgit\s+commit\b")


def _read_command() -> tuple[str, str]:
    data = read_hook_payload(HOOK_NAME)
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


def _staged_links(repo: str) -> set[str]:
    fields = _names(
        _git(
            repo, "diff", "--cached", "--raw", "--no-renames", "-z", "--diff-filter=AMT"
        )
    )
    pairs = zip(fields[0::2], fields[1::2])
    return {path for meta, path in pairs if meta.split()[1:2] == [SYMLINK_MODE]}


def _links_on_disk(base: str, names: list[str]) -> set[str]:
    return {name for name in names if os.path.islink(os.path.join(base, name))}


def _pending_links(command: str, repo: str, top: str) -> set[str]:
    whole, paths = add_scope(command)
    everything = whole or commits_all(command)
    if not (everything or paths):
        return set()
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
    return _links_on_disk(top, tracked) | _links_on_disk(repo, untracked)


def _offenders(command: str, cwd: str) -> list[str]:
    repo = repo_dir(command, cwd)
    top = (_git(repo, "rev-parse", "--show-toplevel") or "").strip()
    if not top:
        return []
    return sorted(_staged_links(repo) | _pending_links(command, repo, top))


def _audit(command: str) -> None:
    if _audit_record is None:
        return
    _audit_record(
        hook=HOOK_NAME,
        decision="block",
        decision_class="block",
        reason="commit would record a symbolic link",
        tool="Bash",
        command_excerpt=command[:200],
    )


def _block_message(offenders: list[str]) -> str:
    detected = "\n".join(
        [f"{len(offenders)} symbolic link(s) would be committed:"]
        + [f"  {name}" for name in offenders]
    )
    return _block(
        hook=HOOK_NAME,
        rule_anchor="standards/no-committed-symlinks.md",
        detected=detected,
        why=(
            "A committed symlink breaks on Windows checkouts, in archives and in "
            "tools that do not follow links, and it hides which file is the real one."
        ),
        fix=(
            "Replace the link with what it stood for:\n"
            "  shared source: point the build at the shared directory\n"
            "  one copy of a file: commit the file itself\n"
            "  bad:  ln -s ../shared/audio.c src/audio.c && git add src/audio.c\n"
            "  good: SOURCEDIRS += ../shared in the Makefile\n"
            "Unstage it with: git rm --cached <link>"
        ),
        bypass_when=(
            "The repository is a vendored upstream that ships the link and must "
            "stay byte-identical. Confirm with the user first."
        ),
        decision="STOP-AND-ASK",
        env_var=ENV_DISABLE,
        safety="later symlinks in the same session will not be blocked.",
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
