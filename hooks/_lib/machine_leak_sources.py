from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path

from _lib.commit_scope import add_scope, within
from _lib.machine_leak import Line, added_lines
from _lib.shell_segments import (
    HEREDOC_START,
    operator_segments,
    strip_heredoc_bodies,
    unquoted_segments,
)

MESSAGE_LABEL = "commit message"
PUBLISHED_LABEL = "pull request or issue text"
COMMAND_LABEL = "command text"
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
COMMIT_OPENER = re.compile(r"\bgit\b.*\bcommit\b")
GH_OPENER = re.compile(r"\bgh\b")


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


def heredoc_bodies(command: str) -> list[tuple[str, str]]:
    bodies: list[tuple[str, str]] = []
    pending: tuple[str, ...] = ()
    opener = ""
    for line in command.splitlines():
        if pending:
            ended = line.strip() == pending[0]
            pending = pending[1:] if ended else pending
            bodies = bodies if ended else [*bodies, (opener, line)]
            continue
        opener = line
        pending = tuple(m.group(1) for m in HEREDOC_START.finditer(line))
    return bodies


def _stdin_for(bodies: list[tuple[str, str]], pattern: re.Pattern[str]) -> str:
    return "\n".join(line for opener, line in bodies if pattern.search(opener))


def _file_text(name: str, cwd: str, stdin: str) -> str:
    if name == STDIN:
        return stdin
    try:
        return Path(cwd, os.path.expanduser(name)).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _git_args(words: list[str]) -> list[str]:
    index = 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in GIT_GLOBAL_WITH_VALUE else 1
    return words[index:]


def _commit_lines(words: list[str], cwd: str, stdin: str) -> list[Line]:
    args = _git_args(words)
    if args[:1] != ["commit"]:
        return []
    texts = _values(args, COMMIT_TEXT)
    files = [_file_text(name, cwd, stdin) for name in _values(args, COMMIT_FILES)]
    return [
        line for text in (*texts, *files) for line in _numbered(MESSAGE_LABEL, text)
    ]


def _gh_lines(words: list[str], cwd: str, stdin: str) -> list[Line]:
    is_api = words[1:2] == ["api"]
    fields = (
        [v.split("=", 1)[1] for v in _values(words, GH_FIELDS) if "=" in v]
        if is_api
        else []
    )
    file_flags = GH_FILES if is_api else (*GH_FILES, "-F")
    texts = [*_values(words, GH_TEXT), *fields]
    files = [_file_text(name, cwd, stdin) for name in _values(words, file_flags)]
    return [
        line for text in (*texts, *files) for line in _numbered(PUBLISHED_LABEL, text)
    ]


def _fallback(stripped: str, stdin: str) -> list[Line]:
    heads = ("git", "gh")
    segments = [s.strip() for s in unquoted_segments(stripped)]
    publishing = [s for s in segments if s.split(" ", 1)[0] in heads]
    return [(COMMAND_LABEL, 1, s) for s in publishing] + _numbered(COMMAND_LABEL, stdin)


def _segment_words(stripped: str) -> list[list[str]] | None:
    header = HEREDOC_START.sub("", stripped)
    try:
        parsed = [shlex.split(s, posix=True) for s, _op in operator_segments(header)]
    except ValueError:
        return None
    return [words for words in parsed if words]


def command_text_lines(command: str, cwd: str) -> list[Line]:
    bodies = heredoc_bodies(command)
    commit_in, gh_in = _stdin_for(bodies, COMMIT_OPENER), _stdin_for(bodies, GH_OPENER)
    stripped = strip_heredoc_bodies(command)
    segments = _segment_words(stripped)
    if segments is None:
        return _fallback(stripped, "\n".join(filter(None, (commit_in, gh_in))))
    lines: list[Line] = []
    for words in segments:
        binary = os.path.basename(words[0])
        if binary == "git":
            lines = [*lines, *_commit_lines(words, cwd, commit_in)]
        elif binary == "gh":
            lines = [*lines, *_gh_lines(words, cwd, gh_in)]
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
