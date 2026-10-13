from __future__ import annotations

import os
import re
import shlex
import subprocess

from _lib.git_invocation import OPTIONS_WITH_SEPARATE_VALUE
from _lib.shell_segments import command_head, unquoted_segments

REPOSITORY_REDIRECTS = ("--git-dir", "--work-tree")

PROTECTED_REF = re.compile(
    r"(?:^|[\s:+])(?:refs/heads/)?(?:main|master|develop)(?=$|[\s;&|'\")])"
)


def names_protected_ref(text: str) -> bool:
    return PROTECTED_REF.search(text) is not None


def command_cwd(command: str) -> str:
    match = re.match(r"""\s*cd\s+(?:'([^']*)'|"([^"]*)"|(\S+))\s*(?:&&|;)""", command)
    if not match:
        return ""
    single_quoted, double_quoted, bare = match.groups()
    if single_quoted is not None:
        return single_quoted
    path = double_quoted if double_quoted is not None else bare
    return os.path.expandvars(os.path.expanduser(path))


def _apply_option(
    args: list[str], index: int, resolved: str | None
) -> tuple[int, str | None]:
    option = args[index]
    next_resolved = resolved
    if option.split("=", 1)[0] in REPOSITORY_REDIRECTS:
        next_resolved = None
    elif option == "-C" and index + 1 < len(args) and resolved is not None:
        target = os.path.expandvars(os.path.expanduser(args[index + 1]))
        next_resolved = os.path.join(resolved or os.getcwd(), target)
    step = 2 if option in OPTIONS_WITH_SEPARATE_VALUE else 1
    return index + step, next_resolved


def git_push_directory(args: list[str], directory: str) -> tuple[bool, str | None]:
    resolved: str | None = directory
    index = 1
    while index < len(args) and args[index].startswith("-"):
        index, resolved = _apply_option(args, index, resolved)
    return index < len(args) and args[index] == "push", resolved


def push_cwd(command: str) -> str | None:
    base = command_cwd(command)
    for segment in unquoted_segments(command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        head, args = command_head(tokens)
        if head != "git":
            continue
        pushes, directory = git_push_directory(args, base)
        if pushes:
            return directory
    return None


def repo_root(cwd: str = "") -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=cwd or None,
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        return ""


def current_branch(cwd: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=cwd or None,
        ).strip()
    except Exception:
        return ""
