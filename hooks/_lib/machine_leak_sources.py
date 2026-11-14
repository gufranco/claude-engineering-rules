from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from _lib.commit_scope import add_scope, within
from _lib.machine_leak import Line, added_lines

MESSAGE_LABEL = "commit message"
PUBLISHED_LABEL = "pull request or issue text"
COMMAND_LABEL = "command text"
SEPARATORS = frozenset({"&&", "||", ";", "|", "&"})
GIT_GLOBAL_WITH_VALUE = frozenset({"-C", "-c", "--git-dir", "--work-tree"})
COMMIT_TEXT = ("-m", "--message")
COMMIT_FILES = ("-F", "--file")
GH_TEXT = ("-b", "--body", "-t", "--title", "-n", "--notes")
GH_FILES = ("--body-file", "--notes-file")
GH_FIELDS = ("-f", "--field", "-F", "--raw-field")
STDIN = "-"
GIT_TIMEOUT_S = 10
MAX_PENDING_FILES = 2000
MAX_FILE_BYTES = 512 * 1024


def _segments(tokens: list[str]) -> list[list[str]]:
    groups: list[list[str]] = [[]]
    for token in tokens:
        groups = (
            [*groups, []]
            if token in SEPARATORS
            else [*groups[:-1], [*groups[-1], token]]
        )
    return [group for group in groups if group]


def _values(args: list[str], flags: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for index, arg in enumerate(args):
        if arg in flags and index + 1 < len(args):
            found = [*found, args[index + 1]]
        long_form = next(
            (f for f in flags if f.startswith("--") and arg.startswith(f"{f}=")), None
        )
        short_form = next(
            (f for f in flags if len(f) == 2 and arg.startswith(f) and len(arg) > 2),
            None,
        )
        if long_form:
            found = [*found, arg.split("=", 1)[1]]
        elif short_form and not arg.startswith("--"):
            found = [*found, arg[2:]]
    return found


def _numbered(label: str, text: str) -> list[Line]:
    return [
        (label, n, line) for n, line in enumerate(text.splitlines(), 1) if line.strip()
    ]


def _file_text(name: str, cwd: str) -> str:
    if name == STDIN:
        return ""
    try:
        return Path(cwd, os.path.expanduser(name)).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _git_args(words: list[str]) -> list[str]:
    index = 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in GIT_GLOBAL_WITH_VALUE else 1
    return words[index:]


def _commit_lines(words: list[str], cwd: str) -> list[Line]:
    args = _git_args(words)
    if args[:1] != ["commit"]:
        return []
    texts = _values(args, COMMIT_TEXT)
    files = [_file_text(name, cwd) for name in _values(args, COMMIT_FILES)]
    return [
        line for text in (*texts, *files) for line in _numbered(MESSAGE_LABEL, text)
    ]


def _gh_lines(words: list[str], cwd: str) -> list[Line]:
    is_api = words[1:2] == ["api"]
    fields = (
        [v.split("=", 1)[1] for v in _values(words, GH_FIELDS) if "=" in v]
        if is_api
        else []
    )
    file_flags = GH_FILES if is_api else (*GH_FILES, "-F")
    texts = [*_values(words, GH_TEXT), *fields]
    files = [_file_text(name, cwd) for name in _values(words, file_flags)]
    return [
        line for text in (*texts, *files) for line in _numbered(PUBLISHED_LABEL, text)
    ]


def command_text_lines(command: str, cwd: str) -> list[Line]:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return [(COMMAND_LABEL, 1, command)]
    lines: list[Line] = []
    for words in _segments(tokens):
        binary = os.path.basename(words[0])
        if binary == "git":
            lines = [*lines, *_commit_lines(words, cwd)]
        elif binary == "gh":
            lines = [*lines, *_gh_lines(words, cwd)]
    return lines


def _git(root: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", root, *args],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_S,
    )


def _pending(root: str) -> list[str]:
    untracked = _git(root, "ls-files", "--others", "--exclude-standard").stdout
    changed = _git(root, "diff", "--name-only").stdout
    return [*untracked.splitlines(), *changed.splitlines()][:MAX_PENDING_FILES]


def _file_lines(root: str, name: str) -> list[Line]:
    path = Path(root, name)
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        return []
    shown = _git(root, "show", f"HEAD:{name}")
    before = shown.stdout if shown.returncode == 0 else ""
    after = path.read_text(encoding="utf-8", errors="replace")
    return added_lines(name, before, after)


def added_in_command(command: str, cwd: str) -> list[Line]:
    whole, paths = add_scope(command)
    if not whole and not paths:
        return []
    top = _git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return []
    root = top.stdout.strip()
    names = [n for n in _pending(root) if whole or within(n, paths)]
    return [line for name in names for line in _file_lines(root, name)]
