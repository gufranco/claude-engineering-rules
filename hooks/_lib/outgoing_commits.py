from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass

from _lib.dangerous_command_push import command_cwd, git_push_directory
from _lib.shell_segments import command_head, unquoted_segments

GIT_TIMEOUT_SECONDS = 10
MAX_OUTGOING_COMMITS = 1000


@dataclass(frozen=True, slots=True)
class PushInvocation:
    directory: str
    sources: tuple[str, ...]


REDIRECTION = re.compile(r"^\d*(?:<|>|&>)")
BARE_REDIRECTION = re.compile(r"^\d*(?:<|>>?|&>>?)$")


def _without_redirections(push_args: list[str]) -> list[str]:
    targets = {
        index + 1 for index, arg in enumerate(push_args) if BARE_REDIRECTION.match(arg)
    }
    return [
        arg
        for index, arg in enumerate(push_args)
        if index not in targets and not REDIRECTION.match(arg)
    ]


def _refspec_sources(push_args: list[str]) -> tuple[str, ...]:
    words = _without_redirections(push_args)
    refspecs = [arg for arg in words if not arg.startswith("-")][1:]
    if not refspecs:
        return ("HEAD",)
    sources = (spec.lstrip("+").split(":", 1)[0] for spec in refspecs)
    return tuple(source for source in sources if source)


def _segment_push(segment: str, base: str, cwd: str) -> PushInvocation | None:
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return None
    head, args = command_head(tokens)
    if head != "git":
        return None
    pushes, directory = git_push_directory(args, base)
    if not pushes or directory is None:
        return None
    push_args = args[args.index("push") + 1 :]
    return PushInvocation(directory or cwd, _refspec_sources(push_args))


def find_pushes(command: str, cwd: str) -> tuple[PushInvocation, ...]:
    base = command_cwd(command)
    found = (
        _segment_push(segment, base, cwd) for segment in unquoted_segments(command)
    )
    return tuple(push for push in found if push is not None)


def _log_arguments(push: PushInvocation) -> list[str]:
    return [
        "git",
        "-C",
        push.directory,
        "log",
        f"--max-count={MAX_OUTGOING_COMMITS}",
        "--format=%B",
        *push.sources,
        "--not",
        "--remotes",
        "--",
    ]


def outgoing_messages(push: PushInvocation) -> str | None:
    if not push.sources:
        return ""
    try:
        result = subprocess.run(
            _log_arguments(push),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return result.stdout if result.returncode == 0 else None
