from __future__ import annotations

import os
import re

from _lib.cli_invocations import invocations

LEADING_CD = re.compile(r"""\s*cd\s+(?:'([^']*)'|"([^"]*)"|(\S+))\s*(?:&&|;)""")
GIT_DASH_C = re.compile(r"""\bgit\s+-C\s+(?:'([^']*)'|"([^"]*)"|(\S+))""")
COMMIT_ALL = re.compile(r"\bcommit\b[^\n;&|]*\s(?:--all|-[a-zA-Z]*a[a-zA-Z]*)(?=\s|$)")
WHOLE_TREE_ADDS = frozenset({"-A", "--all", ".", ":/"})


def _first_group(match: re.Match[str]) -> str:
    return next(group for group in match.groups() if group is not None)


def repo_dir(command: str, cwd: str) -> str:
    base = cwd or os.getcwd()
    for pattern in (LEADING_CD, GIT_DASH_C):
        match = (
            pattern.match(command) if pattern is LEADING_CD else pattern.search(command)
        )
        if match:
            target = os.path.expandvars(os.path.expanduser(_first_group(match)))
            base = os.path.join(base, target)
    return base


def add_scope(command: str) -> tuple[bool, list[str]]:
    whole = False
    paths: list[str] = []
    for call in invocations(command, "git"):
        args = list(call.args)
        while args[:1] in (["-C"], ["-c"]) and len(args) > 1:
            args = args[2:]
        if args[:1] != ["add"]:
            continue
        rest = args[1:]
        whole = whole or any(a in WHOLE_TREE_ADDS for a in rest)
        paths = [*paths, *(a for a in rest if not a.startswith("-") and a != ".")]
    return whole, paths


def commits_all(command: str) -> bool:
    return COMMIT_ALL.search(command) is not None


def within(name: str, paths: list[str]) -> bool:
    cleaned = [p.removeprefix("./").rstrip("/") for p in paths]
    return any(name == p or name.startswith(f"{p}/") for p in cleaned)
