#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.audit_log import record as _audit  # noqa: E402


from _lib.internal_config_leakage_patterns import (  # noqa: E402
    API_BODY_FLAGS,
    API_METHOD_FLAGS,
    CATEGORY_LEAK_PATTERNS,
    CONVENTIONAL_LABEL_PATTERN,
    CONVENTIONAL_LABEL_PATTERN_IN_GIT_MESSAGE,
    FORGE_CLIS,
    GIT_MESSAGE_BASH_PATTERNS,
    GIT_MESSAGE_FILE_FLAGS,
    GIT_MESSAGE_LONG_FLAGS,
    GIT_MESSAGE_SHORT_FLAG_PATTERN,
    GIT_WORD,
    HEREDOC_HEADER_PATTERN,
    NON_GIT_PUBLISHING_BASH_PATTERNS,
    NON_PUBLISHING_PREFIXES,
    PATH_LEAK_PATTERNS,
    PUBLISHING_BASH_PATTERNS,
    READ_ONLY_ACTIONS,
    REVIEW_PREAMBLE_WORDS,
    SECTION_HEADING_PATTERN,
    SEGMENT_OPERATOR,
    SEVERITY_TIER_PATTERN,
    SKILL_FLAG_HEAD_PATTERN,
    SKIPPED_DOCS,
)
from _lib.internal_config_leakage_payloads import (  # noqa: E402
    extract_publishing_text_blocks,
    extract_referenced_files,
    looks_like_publishing_json,
    read_payload_file,
)

from _lib.knowledge_notes import in_vault as _in_vault  # noqa: E402


from _lib import project_workspace as _workspace  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.git_invocation import strip_git_global_options  # noqa: E402
from _lib.cli_invocations import asks_for_help  # noqa: E402
from _lib.shell_segments import (  # noqa: E402
    command_head,
    strip_heredoc_bodies,
    unquoted_segments,
)

Item = tuple[str, str, str, str]

BLOCK_HEADER = (
    "Blocked: internal Claude config or templated scaffolding leaking into "
    'external output. Rule: ~/.claude/standards/code-review.md "No Internal '
    'Config Leakage".\n'
)

BLOCK_FIX = (
    "\n\nFix: rewrite the message so it reads as if a human engineer wrote it. "
    "State the engineering reason directly. Strip Conventional Comments labels "
    "(`issue (blocking):`, `nitpick:`, etc.), internal severity tiers (P0/P1/P2), "
    "skill invocation flags (--backend/--frontend/--local), and references to "
    "personal config paths.\n"
    "Bypass (when editing the config itself): export CONFIG_LEAKAGE_DISABLE=1 "
    "in a parent shell."
)

PREAMBLE_CONTENT_KINDS = ("payload", "markdown", "git-message-payload")
GIT_MESSAGE_KINDS = ("git-message", "git-message-payload")
FILE_TOOLS = ("Write", "Edit", "MultiEdit")
MAX_HITS_PER_ITEM = 6


def _segment_publishes(segment: str) -> bool:
    stripped = segment.lstrip()
    if not stripped or stripped.startswith(NON_PUBLISHING_PREFIXES):
        return False
    if _forge_read_only(segment):
        return False
    matched = strip_git_global_options(segment)
    return any(p.search(matched) for p in PUBLISHING_BASH_PATTERNS)


def _forge_read_only(segment: str) -> bool:
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return False
    base, effective = command_head(tokens)
    args = tuple(effective[1:])
    if base not in FORGE_CLIS or not args:
        return False
    if asks_for_help(args):
        return True
    if args[0] == "api":
        return not _api_writes(args[1:])
    return len(args) > 1 and args[1] in READ_ONLY_ACTIONS


def _api_writes(args: tuple[str, ...]) -> bool:
    for index, arg in enumerate(args):
        flag, _, inline = arg.partition("=")
        if flag in API_BODY_FLAGS:
            return True
        method = inline or (args[index + 1] if index + 1 < len(args) else "")
        if flag in API_METHOD_FLAGS and method.upper() != "GET":
            return True
        if arg.startswith("-X") and len(arg) > 2 and arg[2:].upper() != "GET":
            return True
    return False


def is_publishing_bash(cmd: str) -> bool:
    if not cmd:
        return False
    return any(
        _segment_publishes(strip_heredoc_bodies(segment))
        for segment in unquoted_segments(cmd)
    )


def is_git_message_bash(cmd: str) -> bool:
    if not cmd:
        return False
    if any(p.search(cmd) for p in NON_GIT_PUBLISHING_BASH_PATTERNS):
        return False
    matched = strip_git_global_options(cmd)
    return any(p.search(matched) for p in GIT_MESSAGE_BASH_PATTERNS)


def _feeds_git(line: str, position: int) -> bool:
    segment = SEGMENT_OPERATOR.split(line[:position])[-1]
    return GIT_WORD.search(segment) is not None


def split_heredoc_bodies(cmd: str) -> tuple[list[str], str]:
    bodies: list[str] = []
    remainder: list[str] = []
    lines = cmd.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        remainder.append(line)
        openers = list(HEREDOC_HEADER_PATTERN.finditer(line))
        i += 1
        for opener in openers:
            body: list[str] = []
            while i < len(lines) and lines[i].strip() != opener.group(2):
                body.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            if _feeds_git(line, opener.start()):
                bodies.append("\n".join(body))
    return bodies, "\n".join(remainder)


def _message_args(tokens: list[str]) -> tuple[bool, list[str]]:
    saw_flag = False
    texts: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--message="):
            saw_flag = True
            texts.append(tok[len("--message=") :])
        elif tok in GIT_MESSAGE_LONG_FLAGS or GIT_MESSAGE_SHORT_FLAG_PATTERN.match(tok):
            saw_flag = True
            if i + 1 < len(tokens):
                texts.append(tokens[i + 1])
                i += 1
        i += 1
    return saw_flag, texts


def _names_message_file(segment: str, tokens: list[str]) -> bool:
    if not any(p.search(segment) for p in GIT_MESSAGE_BASH_PATTERNS):
        return False
    pairs = zip(tokens, [*tokens[1:], ""])
    return any(
        tok.startswith("--file=")
        or (tok in GIT_MESSAGE_FILE_FLAGS and nxt not in ("", "-"))
        for tok, nxt in pairs
    )


def extract_git_message_texts(cmd: str) -> list[str] | None:
    bodies, without_heredocs = split_heredoc_bodies(cmd)
    texts = [body for body in bodies if body.strip()]
    saw_message_flag = False
    for segment in unquoted_segments(without_heredocs):
        if not GIT_WORD.search(segment):
            continue
        try:
            tokens = shlex.split(segment, comments=False, posix=True)
        except ValueError:
            return None
        saw, found = _message_args(tokens)
        named_file = _names_message_file(segment, tokens)
        saw_message_flag = saw_message_flag or saw or named_file
        texts = [*texts, *found]
    if not texts and not saw_message_flag:
        return None
    return texts


def is_skipped_md_path(path: str) -> bool:
    if not path:
        return False
    if any(seg in path for seg in SKIPPED_DOCS):
        return True
    return _in_vault(path) or _workspace.in_workspace(Path(path))


def _command_items(cmd: str, authors_git_message: bool) -> list[Item]:
    texts = extract_git_message_texts(cmd) if authors_git_message else None
    if texts is not None:
        return [
            ("bash", f"git message[{idx}]", "git-message", text)
            for idx, text in enumerate(texts)
        ]
    kind = "git-message" if authors_git_message else "command"
    return [("bash", "command", kind, cmd)]


def _referenced_payload_items(cmd: str, payload_kind: str) -> list[Item]:
    out: list[Item] = []
    for ref in extract_referenced_files(cmd):
        payload = read_payload_file(ref)
        if payload is None:
            continue
        blocks = extract_publishing_text_blocks(payload)
        if not blocks:
            out = [*out, ("bash-payload", ref, payload_kind, payload)]
            continue
        out = [
            *out,
            *((f"bash-payload:{ref}", lb, payload_kind, t) for lb, t in blocks),
        ]
    return out


def _collect_bash(cmd: object) -> list[Item]:
    if not isinstance(cmd, str) or not is_publishing_bash(cmd):
        return []
    authors_git_message = is_git_message_bash(cmd)
    payload_kind = "git-message-payload" if authors_git_message else "payload"
    return [
        *_command_items(cmd, authors_git_message),
        *_referenced_payload_items(cmd, payload_kind),
    ]


def _file_kind(fp: str) -> str | None:
    ext = fp.lower()
    if ext.endswith(".md"):
        return "markdown"
    if ext.endswith(".json"):
        return "json-maybe"
    return None


def _collect_write(fp: str, kind: str, content: str) -> list[Item]:
    if kind != "json-maybe":
        return [(fp, "content", "markdown", content)]
    if not looks_like_publishing_json(content):
        return []
    blocks = extract_publishing_text_blocks(content)
    if not blocks:
        return [(fp, "content", "payload", content)]
    return [(fp, label, "payload", text) for label, text in blocks]


def _collect_file(tool: str, tool_input: dict, fp: str) -> list[Item]:
    if is_skipped_md_path(fp):
        return []
    kind = _file_kind(fp)
    if kind is None:
        return []
    if tool == "Write":
        return _collect_write(fp, kind, str(tool_input.get("content") or ""))
    content_kind = "markdown" if kind == "markdown" else "payload"
    return [
        (fp, name, content_kind, text)
        for name, text in payload_fragments(tool, tool_input)
    ]


def collect(tool: str, tool_input: dict) -> list[tuple[str, str, str, str]]:
    if tool == "Bash":
        return _collect_bash(tool_input.get("command", ""))
    if tool in FILE_TOOLS:
        return _collect_file(tool, tool_input, tool_input.get("file_path", "") or "")
    return []


def _hit(text: str, label: str, m: re.Match[str]) -> str:
    start = max(0, m.start() - 30)
    end = min(len(text), m.end() + 30)
    snippet = text[start:end].replace("\n", " | ")
    return f"{label}: ...{snippet}..."


def _skill_flag_match(text: str, content_kind: str) -> re.Match[str] | None:
    if content_kind not in PREAMBLE_CONTENT_KINDS:
        return None
    head = text[:300]
    m = SKILL_FLAG_HEAD_PATTERN.search(head)
    if m is None:
        return None
    head_lower = head.lower()
    return m if any(w in head_lower for w in REVIEW_PREAMBLE_WORDS) else None


def _candidate_matches(
    text: str, content_kind: str
) -> list[tuple[str, re.Match[str] | None]]:
    label_pattern = (
        CONVENTIONAL_LABEL_PATTERN_IN_GIT_MESSAGE
        if content_kind in GIT_MESSAGE_KINDS
        else CONVENTIONAL_LABEL_PATTERN
    )
    return [
        *((label, pat.search(text)) for pat, label in PATH_LEAK_PATTERNS),
        *((label, pat.search(text)) for pat, label in CATEGORY_LEAK_PATTERNS),
        ("Conventional Comments label prefix", label_pattern.search(text)),
        (
            "internal severity tier (P0/P1/P2 scaffolding)",
            SEVERITY_TIER_PATTERN.search(text),
        ),
        ("internal section heading", SECTION_HEADING_PATTERN.search(text)),
        (
            "skill invocation flag in review preamble",
            _skill_flag_match(text, content_kind),
        ),
    ]


def find_leaks(text: str, content_kind: str) -> list[str]:
    return [
        _hit(text, label, m)
        for label, m in _candidate_matches(text, content_kind)
        if m is not None
    ]


from _lib.hook_profile import should_run  # noqa: E402
from _lib.edit_resolution import payload_fragments  # noqa: E402


def _should_skip() -> bool:
    if not should_run("internal-config-leakage"):
        return True
    if os.environ.get("CONFIG_LEAKAGE_DISABLE") == "1":
        _audit(
            hook="internal-config-leakage",
            decision="bypass",
            bypass_env="CONFIG_LEAKAGE_DISABLE",
        )
        return True
    return is_bypassed("internal-config-leakage")


def _findings(items: list[Item]) -> list[str]:
    findings: list[str] = []
    for source_label, path_or_field, content_kind, text in items:
        hits = find_leaks(text, content_kind)
        if hits:
            findings = [
                *findings,
                f"  - {path_or_field} ({source_label}):",
                *(f"      {h}" for h in hits[:MAX_HITS_PER_ITEM]),
            ]
    return findings


def _report(tool: str, findings: list[str]) -> None:
    print(BLOCK_HEADER + "\n".join(findings) + BLOCK_FIX, file=sys.stderr)
    _audit(
        hook="internal-config-leakage",
        decision="block",
        tool=tool,
        reason="claude config or templated scaffolding leakage",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )


def main() -> int:
    if _should_skip():
        return 0

    payload = read_hook_payload("internal-config-leakage")

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    findings = _findings(collect(tool, tool_input))
    if not findings:
        return 0

    _report(tool, findings)
    return 2


if __name__ == "__main__":
    sys.exit(main())
