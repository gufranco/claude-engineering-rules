#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.hook_input import read_hook_payload  # noqa: E402

try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


try:
    from _lib.bypass import is_bypassed  # type: ignore
except Exception:  # pragma: no cover

    def is_bypassed(_id: str) -> bool:  # type: ignore
        return False


try:
    from _lib.hook_profile import should_run  # type: ignore
except Exception:  # pragma: no cover

    def should_run(_id: str) -> bool:  # type: ignore
        return True


HOOK_ID = "pr-comment-discipline"
ENV_VAR = "PR_COMMENT_DISCIPLINE_DISABLE"
RULE_ANCHOR = "~/.claude/rules/pr-comment-discipline.md"

PR_COMMENT = re.compile(r"\bgh\s+pr\s+comment\b")
PR_REVIEW = re.compile(r"\bgh\s+pr\s+review\b")
GH_API = re.compile(r"\bgh\s+api\b")
GLAB_MR_NOTE = re.compile(r"\bglab\s+mr\s+note\b")
GLAB_API = re.compile(r"\bglab\s+api\b")
CURL = re.compile(r"\bcurl\b")

REVIEWS_ENDPOINT = re.compile(r"(?:^|[/\s'\"])pulls/\d+/reviews(?:$|[?'\"\s])")
REVIEW_COMMENTS_ENDPOINT = re.compile(r"(?:^|[/\s'\"])pulls/\d+/comments(?:$|[?'\"\s])")
REPLIES_ENDPOINT = re.compile(r"pulls/\d+/comments/\d+/replies")
ISSUE_COMMENTS_ENDPOINT = re.compile(r"(?:^|[/\s'\"])issues/\d+/comments(?:$|[?'\"\s])")
COMMIT_COMMENTS_ENDPOINT = re.compile(r"commits/[0-9a-fA-F]{7,40}/comments")
GLAB_DISCUSSIONS = re.compile(r"merge_requests/\d+/discussions(?:$|[?'\"\s])")
GLAB_DISCUSSION_NOTES = re.compile(r"discussions/[^/\s'\"]+/notes")
BB_PR_COMMENTS = re.compile(r"/pullrequests/\d+/comments(?:$|[?'\"\s])")

from _lib.shell_segments import strip_heredoc_bodies  # noqa: E402

REVIEW_BODY_FLAGS = ("--body", "--body-file", "-b", "-F")
REVIEW_BODY_PREFIXES = ("--body=", "--body-file=", "-b=", "-F=")
PAYLOAD_FLAGS = ("--input", "--data", "--data-binary", "--data-raw", "-d")
FIELD_FLAGS = ("-f", "--field", "--raw-field", "-F")

WRITE_METHODS = ("post", "put", "patch")
HELP_FLAGS = frozenset({"--help", "-h"})


def _tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return command.split()


SEPARATORS = frozenset({"&&", "||", ";", "|", "&", "|&"})


def _segments(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return [command.split()]
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in SEPARATORS:
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def _command_segments(command: str) -> list[list[str]]:
    lines = strip_heredoc_bodies(command).splitlines()
    return [segment for line in lines for segment in _segments(line)]


def _review_has_body(segment: list[str]) -> bool:
    return any(
        token in REVIEW_BODY_FLAGS or token.startswith(REVIEW_BODY_PREFIXES)
        for token in segment
    )


def _resolve(path: str, cwd: str) -> str:
    expanded = os.path.expanduser(path)
    if cwd and not os.path.isabs(expanded):
        return os.path.join(cwd, expanded)
    return expanded


def _writes(command: str, tool: re.Pattern[str]) -> bool:
    return any(
        _is_write(segment, " ".join(segment))
        for segment in _segments(command)
        if tool.search(" ".join(segment))
    )


def _is_write(tokens: list[str], command: str) -> bool:
    lowered = [t.lower() for t in tokens]
    for index, token in enumerate(lowered):
        if token in ("-x", "--method", "--request"):
            if index + 1 < len(lowered) and lowered[index + 1] in WRITE_METHODS:
                return True
        for method in WRITE_METHODS:
            if token in (f"-x{method}", f"--method={method}", f"--request={method}"):
                return True
    if re.search(r"-X\s*(?:POST|PUT|PATCH)\b", command, re.IGNORECASE):
        return True
    return any(flag in lowered for flag in PAYLOAD_FLAGS + FIELD_FLAGS)


def _payload_chunks(
    tokens: list[str], command: str, cwd: str = ""
) -> tuple[list[str], bool]:
    chunks: list[str] = []
    unreadable = False
    for index, token in enumerate(tokens):
        if token.lower() not in PAYLOAD_FLAGS or index + 1 >= len(tokens):
            continue
        value = tokens[index + 1]
        path = value[1:] if value.startswith("@") else value
        if path == "-":
            continue
        resolved = _resolve(path, cwd)
        if os.path.isfile(resolved):
            try:
                with open(resolved, encoding="utf-8", errors="replace") as handle:
                    chunks = [*chunks, handle.read()]
            except OSError as error:
                sys.stderr.write(f"{HOOK_ID}: cannot read {resolved}: {error}\n")
                unreadable = True
            continue
        if value.lstrip().startswith(("{", "[")):
            chunks = [*chunks, value]
            continue
        unreadable = True
    return [*chunks, command], unreadable


def _iter_json_objects(text: str):
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = text[start : index + 1]
                try:
                    parsed = json.loads(candidate)
                except ValueError:
                    parsed = None
                if isinstance(parsed, dict):
                    yield parsed


def _has_nonempty_body(chunks: list[str]) -> bool:
    for chunk in chunks:
        for parsed in _iter_json_objects(chunk):
            if "body" not in parsed:
                continue
            body = parsed.get("body")
            return isinstance(body, str) and body.strip() != ""
    for chunk in chunks:
        for match in re.finditer(
            r"(?:^|\s)(?:-f|-F|--field|--raw-field)\s+body=(\S*)", chunk
        ):
            if match.group(1).strip():
                return True
        for match in re.finditer(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', chunk):
            if match.group(1).strip():
                return True
    return False


def _mentions_reply_parent(chunks: list[str]) -> bool:
    joined = "\n".join(chunks)
    return bool(
        re.search(r"in_reply_to", joined)
        or re.search(r'"parent"\s*:', joined)
        or re.search(r"parent(?:\.id)?=", joined)
    )


VIOLATIONS: dict[str, str] = {
    "PRC001": "`gh pr comment` publishes a conversation comment, which has no "
    "thread and no reader who asked for it.",
    "PRC002": "`gh pr review` with a body publishes a review summary. Submit the "
    "review event on its own and put the findings in inline comments.",
    "PRC003": "The review payload carries a non-empty top-level `body`. "
    'Set it to "" and keep the findings in the `comments` array.',
    "PRC004": "A POST to `pulls/<n>/comments` without `in_reply_to` starts a "
    "standalone thread. Reply with `in_reply_to`, or open inline "
    "findings through the reviews endpoint.",
    "PRC005": "`issues/<n>/comments` is the pull-request conversation channel. "
    "Use `gh issue comment` when the target is a real issue.",
    "PRC006": "A GitLab MR note is a merge-request-level comment. Reply inside a "
    "discussion instead, or answer with a code change.",
    "PRC007": "A commit comment cannot be replied to and must not be created. "
    "Say it in the commit message instead.",
    "PRC008": "A POST to the discussions endpoint opens a new merge-request "
    "discussion. Post into an existing one instead.",
    "PRC009": "A Bitbucket comment without `parent.id` is a "
    "pull-request-level comment. Set `parent.id` to reply.",
    "PRC010": "The review payload file could not be read, so its `body` cannot "
    "be checked. Point --input at a readable file, or pass the "
    "payload through a heredoc.",
}

BLOCK_GUIDANCE = (
    "The only comment this configuration publishes on a pull request is a "
    "reply inside a thread a person opened. A review body, a conversation "
    "comment, and a commit comment are answered by changing the code and "
    "naming the point in the commit. A bot thread is resolved in silence.\n\n"
    "Reply into an inline thread with:\n"
    "  gh api repos/<o>/<r>/pulls/<n>/comments/<comment-id>/replies "
    "-X POST --input <file>\n\n"
    "Close an unrepliable item with:\n"
    "  gh api graphql -f query='mutation($id: ID!) { minimizeComment("
    "input: {subjectId: $id, classifier: RESOLVED}) { minimizedComment "
    "{ isMinimized } } }' -F id=<node-id>\n\n"
    "Bypass, for the rare case the rule genuinely does not cover:\n"
)


def _violation(code: str) -> tuple[str, str]:
    return (code, VIOLATIONS[code])


def _review_violation(
    unreadable: bool, extra: list[str], payload: list[str]
) -> tuple[str, str] | None:
    if unreadable and not extra:
        return _violation("PRC010")
    if _has_nonempty_body(payload):
        return _violation("PRC003")
    return None


def _api_violation(
    segment: list[str], extra: list[str], cwd: str
) -> tuple[str, str] | None:
    text = " ".join(segment)
    if REPLIES_ENDPOINT.search(text):
        return None
    chunks, unreadable = _payload_chunks(segment, text, cwd)
    payload = [*chunks, *extra]
    if REVIEWS_ENDPOINT.search(text):
        return _review_violation(unreadable, extra, payload)
    if REVIEW_COMMENTS_ENDPOINT.search(text) and not _mentions_reply_parent(payload):
        return _violation("PRC004")
    if ISSUE_COMMENTS_ENDPOINT.search(text):
        return _violation("PRC005")
    if COMMIT_COMMENTS_ENDPOINT.search(text):
        return _violation("PRC007")
    return None


def _runs(pattern: re.Pattern[str], segments: list[list[str]]) -> bool:
    return any(
        pattern.search(" ".join(segment)) and not HELP_FLAGS.intersection(segment)
        for segment in segments
    )


def _cli_violation(segments: list[list[str]]) -> tuple[str, str] | None:
    if _runs(PR_COMMENT, segments):
        return _violation("PRC001")
    if any(
        PR_REVIEW.search(" ".join(segment)) and _review_has_body(segment)
        for segment in segments
    ):
        return _violation("PRC002")
    if _runs(GLAB_MR_NOTE, segments):
        return _violation("PRC006")
    return None


def _gh_api_violation(
    command: str, segments: list[list[str]], cwd: str
) -> tuple[str, str] | None:
    heredoc = [command] if "<<" in command else []
    for segment in segments:
        text = " ".join(segment)
        if not GH_API.search(text) or not _is_write(segment, text):
            continue
        violation = _api_violation(segment, heredoc, cwd)
        if violation is not None:
            return violation
    return None


def _curl_violation(command: str, executed: str, cwd: str) -> tuple[str, str] | None:
    if not (CURL.search(executed) and _writes(command, CURL)):
        return None
    if not BB_PR_COMMENTS.search(command):
        return None
    payload, _unreadable = _payload_chunks(_tokens(command), command, cwd)
    if _mentions_reply_parent(payload):
        return None
    return _violation("PRC009")


def find_violation(command: str, cwd: str = "") -> tuple[str, str] | None:
    segments = _command_segments(command)
    executed = strip_heredoc_bodies(command)
    violation = _cli_violation(segments) or _gh_api_violation(command, segments, cwd)
    if violation is not None:
        return violation
    if GLAB_API.search(executed) and _writes(command, GLAB_API):
        if GLAB_DISCUSSION_NOTES.search(command):
            return None
        if GLAB_DISCUSSIONS.search(command):
            return _violation("PRC008")
    return _curl_violation(command, executed, cwd)


def _skip_run() -> bool:
    if not should_run(HOOK_ID):
        return True
    if os.environ.get(ENV_VAR) == "1":
        _audit(hook=HOOK_ID, decision="bypass", bypass_env=ENV_VAR)
        return True
    return is_bypassed(HOOK_ID)


def _block(code: str, explanation: str, command: str) -> int:
    print(
        f"Blocked [{code}]: this command publishes a pull-request comment "
        "outside a thread.\n"
        f"Rule: {RULE_ANCHOR}\n\n"
        f"{explanation}\n\n"
        f"{BLOCK_GUIDANCE}"
        f"  export {ENV_VAR}=1",
        file=sys.stderr,
    )
    _audit(
        hook=HOOK_ID,
        decision="block",
        tool="Bash",
        reason=code,
        command_excerpt=command[:240],
    )
    return 2


def main() -> int:
    if _skip_run():
        return 0
    payload = read_hook_payload("pr-comment-discipline")
    if payload.get("tool_name", "") != "Bash":
        return 0
    command = (payload.get("tool_input", {}) or {}).get("command", "") or ""
    if not command:
        return 0
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else ""
    violation = find_violation(command, cwd)
    if violation is None:
        return 0
    code, explanation = violation
    return _block(code, explanation, command)


if __name__ == "__main__":
    sys.exit(main())
