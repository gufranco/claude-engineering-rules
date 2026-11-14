from __future__ import annotations

import os
import re
import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from _lib.shell_segments import unquoted_segments

FIXED_TEMP_ROOTS = ("/tmp", "/private/tmp")
MAC_PRIVATE = "/private"
ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_]\w*)=(.*)$", re.S)
VARIABLE = re.compile(r"\$\{?([A-Za-z_]\w*)\}?")
EXPORT = "export"
MKTEMP_MARKER = "mktemp"
MKTEMP_NAME = "mktemp-dir"
TARGET_FLAGS = ("-t", "--target-directory")
TARGET_PREFIX = "--target-directory="
MAX_PARENT_DEPTH = 64

Env = Mapping[str, str]


@dataclass(frozen=True, slots=True)
class Link:
    source: str
    destination: str


def temp_roots(env: Env) -> tuple[str, ...]:
    tmpdir = env.get("TMPDIR", "").rstrip("/")
    owned = (tmpdir, f"{MAC_PRIVATE}{tmpdir}") if tmpdir else ()
    return (*FIXED_TEMP_ROOTS, *owned)


def _within(path: str, root: str) -> bool:
    return path == root or path.startswith(f"{root}/")


def is_temporary(path: str, env: Env) -> bool:
    return any(_within(path, root) for root in temp_roots(env))


def _in_work_tree(path: str) -> bool:
    parents = [Path(path), *Path(path).parents][:MAX_PARENT_DEPTH]
    return any((folder / ".git").exists() for folder in parents)


def is_real(path: str, env: Env) -> bool:
    if is_temporary(path, env):
        return False
    home = env.get("HOME", "")
    return (bool(home) and _within(path, home)) or _in_work_tree(path)


def _expand(word: str, values: Env) -> str:
    home = values.get("HOME", "")
    tilde = f"{home}{word[1:]}" if word == "~" or word.startswith("~/") else word
    return VARIABLE.sub(lambda m: values.get(m.group(1), m.group(0)), tilde)


def _absolute(word: str, base: str) -> str:
    return os.path.normpath(word if os.path.isabs(word) else os.path.join(base, word))


def _words(text: str) -> list[str]:
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return []


def _assigned(segment: str, values: Env) -> dict[str, str]:
    match = ASSIGNMENT.match(segment)
    if match is None:
        return {}
    name, raw = match.group(1), match.group(2).strip()
    if raw.startswith("$(") and MKTEMP_MARKER in raw:
        return {name: os.path.join(temp_roots(values)[0], MKTEMP_NAME)}
    words = _words(segment.strip().removeprefix(EXPORT))
    if len(words) != 1:
        return {}
    return {name: _expand(words[0].split("=", 1)[1], values)}


def _operands(args: list[str]) -> tuple[list[str], str | None]:
    operands: list[str] = []
    target: str | None = None
    pending = False
    for arg in args:
        if pending:
            target, pending = arg, False
        elif arg in TARGET_FLAGS:
            pending = True
        elif arg.startswith(TARGET_PREFIX):
            target = arg.removeprefix(TARGET_PREFIX)
        elif not arg.startswith("-"):
            operands = [*operands, arg]
    return operands, target


def _placement(
    operands: list[str], target: str | None, cwd: str
) -> tuple[list[str], str]:
    if target is not None:
        return operands, target
    if len(operands) > 1:
        return operands[:-1], operands[-1]
    return operands, cwd


def _links(args: list[str], values: Env, cwd: str) -> list[Link]:
    operands, target = _operands(args)
    expanded = [_expand(word, values) for word in operands]
    folder = _expand(target, values) if target is not None else None
    sources, place = _placement(expanded, folder, cwd)
    if "$" in place or any("$" in source for source in sources):
        return []
    return [Link(source, _absolute(place, cwd)) for source in sources]


def _resolved(link: Link, symbolic: bool, cwd: str) -> Link:
    base = os.path.dirname(link.destination) if symbolic else cwd
    return Link(_absolute(link.source, base), link.destination)


def _symbolic(args: list[str]) -> bool:
    flags = [a for a in args if a.startswith("-") and not a.startswith("--")]
    return "--symbolic" in args or any("s" in flag for flag in flags)


def planned_links(command: str, cwd: str, env: Env) -> list[Link]:
    values: dict[str, str] = dict(env)
    here = cwd
    found: list[Link] = []
    for segment in unquoted_segments(command):
        values = {**values, **_assigned(segment, values)}
        words = _words(segment)
        if words[:1] == ["cd"] and len(words) > 1:
            here = _absolute(_expand(words[1], values), here)
        elif words and os.path.basename(words[0]) == "ln":
            symbolic = _symbolic(words[1:])
            raw = _links(words[1:], values, here)
            found = [*found, *(_resolved(link, symbolic, here) for link in raw)]
    return found


def escaping_links(command: str, cwd: str, env: Env) -> list[Link]:
    return [
        link
        for link in planned_links(command, cwd, env)
        if is_temporary(link.destination, env) and is_real(link.source, env)
    ]
