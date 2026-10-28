from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import dataclass
from enum import Enum

from _lib.shell_segments import strip_heredoc_bodies


class Channel(str, Enum):
    PR_CREATE = "gh pr create"
    PR_EDIT = "gh pr edit"
    ISSUE_CREATE = "gh issue create"
    ISSUE_EDIT = "gh issue edit"
    ISSUE_COMMENT = "gh issue comment"
    THREAD_REPLY = "pull request thread reply"
    API_ISSUE_COMMENT = "issue comment through gh api"
    MR_CREATE = "glab mr create"
    MR_UPDATE = "glab mr update"
    GLAB_ISSUE_CREATE = "glab issue create"
    GLAB_ISSUE_NOTE = "glab issue note"
    TRACKER_ISSUE = "tracker issue"
    TRACKER_COMMENT = "tracker comment"


PULL_REQUEST_CHANNELS = frozenset(
    {Channel.PR_CREATE, Channel.PR_EDIT, Channel.THREAD_REPLY, Channel.MR_CREATE}
    | {Channel.MR_UPDATE}
)


@dataclass(frozen=True, slots=True)
class Attachment:
    path: str
    alt: str


@dataclass(frozen=True, slots=True)
class Publication:
    channel: Channel
    attachments: tuple[Attachment, ...]
    text: str
    repo: str
    base: str
    unreadable: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Flags:
    body: tuple[str, ...]
    body_file: tuple[str, ...]


SUBSTITUTION = re.compile(r"\$\([^()]*\)|`[^`\n]*`")
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=\S*")
PREFIX_WORDS = frozenset({"env", "command", "exec", "builtin", "nohup", "time"})
SEPARATORS = frozenset({"&&", "||", ";", "|", "&", "|&"})
REPLIES_ENDPOINT = re.compile(r"pulls/\d+/comments/\d+/replies")
REVIEW_COMMENT_ENDPOINT = re.compile(r"pulls/\d+/comments(?:$|[?\s])")
ISSUE_COMMENT_ENDPOINT = re.compile(r"issues/\d+/comments(?:$|[?\s])")
BODY_READ_LIMIT = 1024 * 1024
HELP_FLAGS = frozenset({"--help", "-h"})

GH_FLAGS = _Flags(body=("--body", "-b"), body_file=("--body-file", "-F"))
GLAB_FLAGS = _Flags(body=("--description", "-d", "--message", "-m"), body_file=())
GH_CHANNELS = {
    ("pr", "create"): Channel.PR_CREATE,
    ("pr", "edit"): Channel.PR_EDIT,
    ("issue", "create"): Channel.ISSUE_CREATE,
    ("issue", "edit"): Channel.ISSUE_EDIT,
    ("issue", "comment"): Channel.ISSUE_COMMENT,
}
GLAB_CHANNELS = {
    ("mr", "create"): Channel.MR_CREATE,
    ("mr", "update"): Channel.MR_UPDATE,
    ("issue", "create"): Channel.GLAB_ISSUE_CREATE,
    ("issue", "note"): Channel.GLAB_ISSUE_NOTE,
}
EDIT_CHANNELS = frozenset({Channel.PR_EDIT, Channel.ISSUE_EDIT, Channel.MR_UPDATE})


def _segments(command: str) -> list[list[str]]:
    flat = SUBSTITUTION.sub("SUBST", strip_heredoc_bodies(command))
    found: list[list[str]] = []
    for line in flat.splitlines():
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        try:
            tokens = list(lexer)
        except ValueError:
            tokens = line.split()
        current: list[str] = []
        for token in tokens:
            if token in SEPARATORS:
                found = [*found, current]
                current = []
            else:
                current = [*current, token]
        found = [*found, current]
    return [segment for segment in found if segment]


def _head(segment: list[str]) -> list[str]:
    index = 0
    while index < len(segment) and (
        ASSIGNMENT.fullmatch(segment[index]) or segment[index] in PREFIX_WORDS
    ):
        index += 1
    return segment[index:]


def _values(args: list[str], names: tuple[str, ...]) -> tuple[str, ...]:
    found: list[str] = []
    for index, arg in enumerate(args):
        if arg in names and index + 1 < len(args):
            found = [*found, args[index + 1]]
            continue
        prefix = next((n for n in names if arg.startswith(f"{n}=")), None)
        if prefix is not None:
            found = [*found, arg[len(prefix) + 1 :]]
    return tuple(found)


def _read(path: str, cwd: str) -> str | None:
    resolved = os.path.expanduser(path)
    if cwd and not os.path.isabs(resolved):
        resolved = os.path.join(cwd, resolved)
    try:
        with open(resolved, encoding="utf-8", errors="replace") as handle:
            return handle.read(BODY_READ_LIMIT)
    except OSError:
        return None


def _body_text(
    args: list[str], flags: _Flags, command: str, cwd: str
) -> tuple[str, tuple[str, ...]]:
    texts = list(_values(args, flags.body))
    unreadable: list[str] = []
    for path in _values(args, flags.body_file):
        content = command if path == "-" else _read(path, cwd)
        if content is None:
            unreadable = [*unreadable, path]
        else:
            texts = [*texts, content]
    if "<<" in command:
        texts = [*texts, command]
    return "\n".join(texts), tuple(unreadable)


def _attachment(value: str) -> Attachment:
    path, _, alt = value.partition("#")
    return Attachment(path=path, alt=alt)


def _carries_text(channel: Channel, args: list[str], flags: _Flags) -> bool:
    if channel not in EDIT_CHANNELS:
        return True
    names = (*flags.body, *flags.body_file, "--attach")
    return bool(_values(args, names))


def _cli_publication(
    args: list[str], channel: Channel, flags: _Flags, command: str, cwd: str
) -> Publication | None:
    if any(arg in HELP_FLAGS for arg in args) or not _carries_text(
        channel, args, flags
    ):
        return None
    text, unreadable = _body_text(args, flags, command, cwd)
    return Publication(
        channel=channel,
        attachments=tuple(_attachment(v) for v in _values(args, ("--attach",))),
        text=text,
        repo=next(iter(_values(args, ("--repo", "-R"))), ""),
        base=next(iter(_values(args, ("--base", "-B"))), ""),
        unreadable=unreadable,
    )


def _field_bodies(
    args: list[str], command: str, cwd: str
) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    unreadable: list[str] = []
    for value in _values(args, ("-f", "-F", "--field", "--raw-field")):
        name, _, content = value.partition("=")
        if name != "body":
            continue
        if not content.startswith("@"):
            texts = [*texts, content]
            continue
        read = command if content == "@-" else _read(content[1:], cwd)
        if read is None:
            unreadable = [*unreadable, content[1:]]
        else:
            texts = [*texts, read]
    return texts, unreadable


def _input_bodies(
    args: list[str], command: str, cwd: str
) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    unreadable: list[str] = []
    for path in _values(args, ("--input",)):
        content = command if path == "-" else _read(path, cwd)
        if content is None:
            unreadable = [*unreadable, path]
            continue
        try:
            parsed = json.loads(content)
        except ValueError:
            parsed = None
        body = parsed.get("body") if isinstance(parsed, dict) else None
        texts = [*texts, body if isinstance(body, str) else content]
    return texts, unreadable


def _api_channel(args: list[str]) -> Channel | None:
    joined = " ".join(args)
    if REPLIES_ENDPOINT.search(joined):
        return Channel.THREAD_REPLY
    if REVIEW_COMMENT_ENDPOINT.search(joined) and "in_reply_to" in joined:
        return Channel.THREAD_REPLY
    if ISSUE_COMMENT_ENDPOINT.search(joined) and _api_writes(args):
        return Channel.API_ISSUE_COMMENT
    return None


def _api_writes(args: list[str]) -> bool:
    lowered = [arg.lower() for arg in args]
    payload = ("--input", "-f", "-F", "--field", "--raw-field")
    if any(arg in payload for arg in args):
        return True
    return any(
        arg in ("-x", "--method")
        and index + 1 < len(lowered)
        and lowered[index + 1] in ("post", "patch", "put")
        for index, arg in enumerate(lowered)
    )


def _api_publication(args: list[str], command: str, cwd: str) -> Publication | None:
    channel = _api_channel(args)
    if channel is None:
        return None
    fields, field_unreadable = _field_bodies(args, command, cwd)
    inputs, input_unreadable = _input_bodies(args, command, cwd)
    heredoc = [command] if "<<" in command else []
    return Publication(
        channel=channel,
        attachments=(),
        text="\n".join([*fields, *inputs, *heredoc]),
        repo="",
        base="",
        unreadable=tuple([*field_unreadable, *input_unreadable]),
    )


def _segment_publication(
    segment: list[str], command: str, cwd: str
) -> Publication | None:
    words = _head(segment)
    binary = os.path.basename(words[0]) if words else ""
    args = words[1:]
    if binary == "gh" and args[:1] == ["api"]:
        return _api_publication(args[1:], command, cwd)
    if binary not in ("gh", "glab") or len(args) < 2:
        return None
    table, flags = (
        (GH_CHANNELS, GH_FLAGS) if binary == "gh" else (GLAB_CHANNELS, GLAB_FLAGS)
    )
    channel = table.get((args[0], args[1]))
    if channel is None:
        return None
    return _cli_publication(args[2:], channel, flags, command, cwd)


def publications(command: str, cwd: str) -> list[Publication]:
    found: list[Publication] = []
    for segment in _segments(command):
        publication = _segment_publication(segment, command, cwd)
        if publication is not None:
            found = [*found, publication]
    return found


TRACKER_TOOL = re.compile(r"^mcp__linear[^_]*__(save_issue|save_comment)$")
PATCH_TEXT_KEYS = ("text", "new_string")


def _patch_texts(patch: object) -> list[str]:
    if not isinstance(patch, list):
        return []
    return [
        value
        for operation in patch
        if isinstance(operation, dict)
        for key in PATCH_TEXT_KEYS
        if isinstance(value := operation.get(key), str)
    ]


def tracker_publication(tool_name: str, tool_input: object) -> Publication | None:
    match = TRACKER_TOOL.match(tool_name)
    if match is None or not isinstance(tool_input, dict):
        return None
    issue = match.group(1) == "save_issue"
    field = "description" if issue else "body"
    texts = [tool_input.get(field)] if isinstance(tool_input.get(field), str) else []
    texts = [*texts, *_patch_texts(tool_input.get("patch"))]
    return Publication(
        channel=Channel.TRACKER_ISSUE if issue else Channel.TRACKER_COMMENT,
        attachments=(),
        text="\n".join(str(text) for text in texts),
        repo="",
        base="",
        unreadable=(),
    )
