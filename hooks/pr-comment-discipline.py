#!/usr/bin/env python3
"""
pr-comment-discipline.py

PreToolUse hook on Bash. Blocks every command that publishes a comment
on a pull request outside an existing thread.

Permitted, and therefore never blocked:
  - A reply into an inline review thread:
      gh api repos/<o>/<r>/pulls/<n>/comments/<id>/replies -X POST
  - A review submission whose top-level body is empty, which is how
    inline findings reach a pull request someone else authored:
      gh api repos/<o>/<r>/pulls/<n>/reviews -X POST --input <file>
  - A review event with no body at all:
      gh pr review <n> --approve
  - Any pull-request description edit. A description is not a comment.
  - A reply into a GitLab discussion, or a Bitbucket comment carrying
    parent.id.

Blocked:
  - gh pr comment
  - gh pr review with --body or --body-file
  - gh api POST to pulls/<n>/reviews with a non-empty top-level body
  - gh api POST to pulls/<n>/comments without in_reply_to
  - gh api POST to issues/<n>/comments, which is the pull-request
    conversation channel. Real issues are commented with
    `gh issue comment`, which this hook leaves alone.
  - gh api POST to commits/<sha>/comments
  - glab mr note, and a POST that creates a new GitLab discussion
  - curl POST to a Bitbucket pullrequests/<id>/comments without parent

The author of a thread cannot be read from a command string, so the
"never reply to a bot" half of the rule has no mechanical backstop and
stays a judgment obligation.

Bypass:
  PR_COMMENT_DISCIPLINE_DISABLE=1  (parent-shell export, not inline)

Source rule: ~/.claude/rules/pr-comment-discipline.md
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))

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

BODY_FLAGS = ("--body", "--body-file")
PAYLOAD_FLAGS = ("--input", "--data", "--data-binary", "--data-raw", "-d")
FIELD_FLAGS = ("-f", "--field", "--raw-field", "-F")

WRITE_METHODS = ("post", "put", "patch")


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


def _writes(command: str, tool: re.Pattern[str]) -> bool:
    return any(
        _is_write(segment, " ".join(segment))
        for segment in _segments(command)
        if tool.search(" ".join(segment))
    )


def _is_write(tokens: list[str], command: str) -> bool:
    """True when the invocation sends a write request.

    `gh api` defaults to GET, so a write needs an explicit method or a
    payload flag. `curl` follows the same logic. Anything carrying a
    body is a write regardless of how the method was spelled.
    """
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


def _payload_chunks(tokens: list[str], command: str) -> list[str]:
    """Best-effort read of the request body a command would send.

    Reads a file referenced by --input or --data @file when it exists,
    falls back to the inline value, and finally appends the whole
    command so an inline heredoc still contributes. Chunks stay
    separate so a nested `body` in one chunk cannot be mistaken for the
    top-level `body` of another.
    """
    chunks: list[str] = []
    for index, token in enumerate(tokens):
        if token.lower() not in PAYLOAD_FLAGS:
            continue
        if index + 1 >= len(tokens):
            continue
        value = tokens[index + 1]
        path = value[1:] if value.startswith("@") else value
        if path == "-":
            continue
        try:
            expanded = os.path.expanduser(path)
            if os.path.isfile(expanded):
                with open(expanded, encoding="utf-8", errors="replace") as handle:
                    chunks.append(handle.read())
                continue
        except OSError:
            pass
        chunks.append(value)
    chunks.append(command)
    return chunks


def _iter_json_objects(text: str):
    """Yield every balanced brace-delimited substring that parses as a dict.

    A heredoc body sits inside the command string rather than in a file,
    so the payload has to be recovered from the surrounding text.
    """
    depth = 0
    start = -1
    for index, char in enumerate(text):
        if char == "{":
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
    """True when a review payload carries a non-empty top-level body.

    A parsed object decides on its own. Only when nothing parses does
    the text fallback run, and that fallback errs toward blocking.
    """
    for chunk in chunks:
        for parsed in _iter_json_objects(chunk):
            if "body" not in parsed:
                continue
            body = parsed.get("body")
            return isinstance(body, str) and body.strip() != ""
    for chunk in chunks:
        for match in re.finditer(
            r"(?:^|\s)(?:-f|--field|--raw-field)\s+body=(\S*)", chunk
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


def find_violation(command: str) -> tuple[str, str] | None:
    """Return (code, explanation) for the first banned shape found."""
    tokens = _tokens(command)
    lowered = [t.lower() for t in tokens]

    if PR_COMMENT.search(command):
        return (
            "PRC001",
            "`gh pr comment` publishes a conversation comment, which has no "
            "thread and no reader who asked for it.",
        )

    if PR_REVIEW.search(command) and any(
        token in BODY_FLAGS or token.startswith(("--body=", "--body-file="))
        for token in lowered
    ):
        return (
            "PRC002",
            "`gh pr review` with a body publishes a review summary. Submit the "
            "review event on its own and put the findings in inline comments.",
        )

    if GLAB_MR_NOTE.search(command):
        return (
            "PRC006",
            "A GitLab MR note is a merge-request-level comment. Reply inside a "
            "discussion instead, or answer with a code change.",
        )

    if GH_API.search(command) and _writes(command, GH_API):
        if REPLIES_ENDPOINT.search(command):
            return None
        payload = _payload_chunks(tokens, command)
        if REVIEWS_ENDPOINT.search(command):
            if _has_nonempty_body(payload):
                return (
                    "PRC003",
                    "The review payload carries a non-empty top-level `body`. "
                    'Set it to "" and keep the findings in the `comments` array.',
                )
            return None
        if REVIEW_COMMENTS_ENDPOINT.search(command) and not _mentions_reply_parent(
            payload
        ):
            return (
                "PRC004",
                "A POST to `pulls/<n>/comments` without `in_reply_to` starts a "
                "standalone thread. Reply with `in_reply_to`, or open inline "
                "findings through the reviews endpoint.",
            )
        if ISSUE_COMMENTS_ENDPOINT.search(command):
            return (
                "PRC005",
                "`issues/<n>/comments` is the pull-request conversation channel. "
                "Use `gh issue comment` when the target is a real issue.",
            )
        if COMMIT_COMMENTS_ENDPOINT.search(command):
            return (
                "PRC007",
                "A commit comment cannot be replied to and must not be created. "
                "Say it in the commit message instead.",
            )

    if GLAB_API.search(command) and _writes(command, GLAB_API):
        if GLAB_DISCUSSION_NOTES.search(command):
            return None
        if GLAB_DISCUSSIONS.search(command):
            return (
                "PRC008",
                "A POST to the discussions endpoint opens a new merge-request "
                "discussion. Post into an existing one instead.",
            )

    if CURL.search(command) and _writes(command, CURL):
        if BB_PR_COMMENTS.search(command):
            payload = _payload_chunks(tokens, command)
            if not _mentions_reply_parent(payload):
                return (
                    "PRC009",
                    "A Bitbucket comment without `parent.id` is a "
                    "pull-request-level comment. Set `parent.id` to reply.",
                )

    return None


def main() -> int:
    if not should_run(HOOK_ID):
        return 0
    if os.environ.get(ENV_VAR) == "1":
        _audit(hook=HOOK_ID, decision="bypass", bypass_env=ENV_VAR)
        return 0
    if is_bypassed(HOOK_ID):
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name", "") != "Bash":
        return 0

    command = (payload.get("tool_input", {}) or {}).get("command", "") or ""
    if not command:
        return 0

    violation = find_violation(command)
    if violation is None:
        return 0

    code, explanation = violation
    print(
        f"Blocked [{code}]: this command publishes a pull-request comment "
        "outside a thread.\n"
        f"Rule: {RULE_ANCHOR}\n\n"
        f"{explanation}\n\n"
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


if __name__ == "__main__":
    sys.exit(main())
