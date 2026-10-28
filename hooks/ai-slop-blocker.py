#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.hook_input import read_hook_payload  # noqa: E402

from _lib.audit_log import record as _audit  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402


from _lib.hook_profile import should_run  # noqa: E402


from _lib.output import block as _block_message  # noqa: E402

from _lib.git_invocation import strip_git_global_options  # noqa: E402
from _lib.project_workspace import in_workspace, is_prompt_file  # noqa: E402
from _lib.ai_slop_detectors import CONTEXT_EXCLUSIONS, DETECTORS  # noqa: E402


HOOK_ID = "ai-slop-blocker"
ENV_VAR = "AI_SLOP_DISABLE"
RULE_ANCHOR = "~/.claude/rules/anti-slop.md"

PUBLISHING_BASH_PATTERNS = [
    re.compile(r"\bgh\s+(?:pr|issue|api|release|gist)\b"),
    re.compile(r"\bglab\s+(?:mr|issue|api|release)\b"),
    re.compile(r"\bgit\s+commit\b"),
    re.compile(r"\bgit\s+tag\b"),
    re.compile(r"\bslack(?:-cli)?\s+(?:send|post|chat)\b"),
    re.compile(r"\bcurl\b.*\b(?:slack|discord|teams|telegram|hooks\.)"),
]

SKIPPED_PATHS = (
    "/.claude/rules/anti-slop.md",
    "/.claude/standards/anti-slop.md",
    "/.claude/hooks/ai-slop-blocker.py",
    "/.claude/tests/hooks/ai-slop-blocker/",
    "/.claude/tests/fixtures/",
    "CHANGELOG.md",
)

FENCED_BLOCK = re.compile(r"```.*?```", re.S)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
INDENTED_BLOCK = re.compile(r"(?m)^(?: {4,}|\t)(?![-*+>]\s|\d+[.)]\s)\S.*$")
INLINE_CODE = re.compile(r"`[^`\n]*`")
LINK_TARGET = re.compile(r"\]\([^)\n]*\)")

RECORD_ONLY_CODES = frozenset({"SLOP015"})

VAULT_ENV = "SECOND_BRAIN_VAULT"


def under_vault(path: str) -> bool:
    vault = os.environ.get(VAULT_ENV, "").strip()
    if not vault:
        return False
    root = os.path.realpath(os.path.expanduser(vault))
    return os.path.realpath(path).startswith(root + os.sep)


def keeps_provenance(path: str) -> bool:
    if not path:
        return False
    return under_vault(path) or is_prompt_file(path) or in_workspace(Path(path))


def drop_record_findings(
    path: str, findings: list[tuple[str, str, str, str]]
) -> list[tuple[str, str, str, str]]:
    if not any(code in RECORD_ONLY_CODES for code, *_ in findings):
        return findings
    if not keeps_provenance(path):
        return findings
    return [f for f in findings if f[0] not in RECORD_ONLY_CODES]


AGENT_TOOL_NAMES = ("Agent", "Task")

COMMENT_BASH_PATTERNS = (
    re.compile(r"pulls/\d+/comments/\d+/replies"),
    re.compile(r"pulls/\d+/reviews"),
    re.compile(r"discussions/[^/\s'\"]+/notes"),
)

COMMENT_PAYLOAD_FLAGS = ("--input", "--body-file", "--data", "--data-raw", "-d")

COMMENT_FIELD_FLAGS = ("-f", "--field", "--raw-field")

COMMENT_ONLY_CODES = frozenset({"SLOP013", "SLOP014"})


MARKDOWN_MASKS = (
    FENCED_BLOCK,
    HTML_COMMENT,
    INDENTED_BLOCK,
    INLINE_CODE,
    LINK_TARGET,
)

COMMAND_MASKS = (FENCED_BLOCK, INLINE_CODE)


def mask_code(text: str, patterns: tuple[re.Pattern[str], ...]) -> str:
    def blank(match: re.Match[str]) -> str:
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))

    for pattern in patterns:
        text = pattern.sub(blank, text)
    return text


def is_publishing_bash(cmd: str) -> bool:
    matched = strip_git_global_options(cmd)
    return any(p.search(matched) for p in PUBLISHING_BASH_PATTERNS)


def is_skipped_path(path: str) -> bool:
    if not path:
        return False
    return any(seg in path for seg in SKIPPED_PATHS)


def is_comment_bash(cmd: str) -> bool:
    return any(p.search(cmd) for p in COMMENT_BASH_PATTERNS)


def comment_bodies(cmd: str, tokens: list[str]) -> list[str]:
    texts: list[str] = []
    for index, token in enumerate(tokens):
        lowered = token.lower()
        if index + 1 >= len(tokens):
            continue
        if lowered in COMMENT_FIELD_FLAGS:
            field = tokens[index + 1]
            if field.startswith("body="):
                texts.append(field[len("body=") :])
            continue
        if lowered not in COMMENT_PAYLOAD_FLAGS:
            continue
        value = tokens[index + 1]
        path = value[1:] if value.startswith("@") else value
        raw = value
        try:
            expanded = os.path.expanduser(path)
            if os.path.isfile(expanded):
                with open(expanded, encoding="utf-8", errors="replace") as handle:
                    raw = handle.read()
        except OSError as error:
            sys.stderr.write(f"ai-slop-blocker: cannot read {path}: {error}\n")
        texts.extend(extract_bodies(raw))
    texts.extend(extract_bodies(cmd))
    return [t for t in texts if t.strip()]


def extract_bodies(raw: str) -> list[str]:
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            found: list[str] = []
            body = parsed.get("body")
            if isinstance(body, str):
                found.append(body)
            for comment in parsed.get("comments", []) or []:
                if isinstance(comment, dict) and isinstance(comment.get("body"), str):
                    found.append(comment["body"])
            if found:
                return found
    return [raw]


Item = tuple[str, str, bool, bool]
Finding = tuple[str, str, str, str]


def _collect_bash(cmd: str) -> list[Item]:
    if is_comment_bash(cmd):
        try:
            tokens = shlex.split(cmd, posix=True)
        except ValueError:
            tokens = cmd.split()
        return [
            ("comment body", body, False, True) for body in comment_bodies(cmd, tokens)
        ]
    if is_publishing_bash(cmd):
        return [("bash command", cmd, False, False)]
    return []


def _multiedit_items(fp: str, edits: list[object]) -> list[Item]:
    return [
        (f"{fp} [{i}]", edit.get("new_string", ""), True, False)
        for i, edit in enumerate(edits)
        if isinstance(edit, dict) and isinstance(edit.get("new_string", ""), str)
    ]


def _collect_markdown(tool: str, fp: str, tool_input: dict) -> list[Item]:
    if tool == "MultiEdit":
        return _multiedit_items(fp, tool_input.get("edits", []) or [])
    field = {"Write": "content", "Edit": "new_string"}.get(tool)
    if field is None:
        return []
    content = tool_input.get(field, "")
    return [(fp, content, True, False)] if isinstance(content, str) else []


def collect(tool: str, tool_input: dict) -> list[Item]:
    fp = tool_input.get("file_path", "") or ""
    if tool == "Bash":
        return _collect_bash(str(tool_input.get("command") or ""))
    if is_skipped_path(fp) or not fp.lower().endswith((".md", ".markdown")):
        return []
    return _collect_markdown(tool, fp, tool_input)


def _matches(scanned: str, code: str, pattern: re.Pattern[str]) -> list[re.Match[str]]:
    exclusion = CONTEXT_EXCLUSIONS.get(code)
    return [
        m
        for m in pattern.finditer(scanned)
        if not (
            exclusion and exclusion.search(scanned[max(0, m.start() - 40) : m.end()])
        )
    ]


def _enough_hits(matches: list[re.Match[str]], min_hits: int) -> bool:
    if len(matches) < min_hits:
        return False
    return min_hits <= 1 or len({m.group(0).lower() for m in matches}) >= min_hits


def _finding(
    scanned: str, detector: tuple[str, str, str], matches: list[re.Match[str]]
) -> Finding:
    code, label, fix = detector
    first = matches[0]
    line_no = scanned.count("\n", 0, first.start()) + 1
    start = max(0, first.start() - 40)
    end = min(len(scanned), first.end() + 40)
    snippet = " ".join(scanned[start:end].split())
    hit_note = f" ({len(matches)} hits)" if len(matches) > 1 else ""
    return (code, f"{label}{hit_note}", f"line {line_no}: ...{snippet}...", fix)


def find(text: str, is_markdown: bool, is_comment: bool = False) -> list[Finding]:
    scanned = mask_code(text, MARKDOWN_MASKS if is_markdown else COMMAND_MASKS)
    findings: list[Finding] = []
    for code, label, pattern, fix, min_hits in DETECTORS:
        if code in COMMENT_ONLY_CODES and not is_comment:
            continue
        matches = _matches(scanned, code, pattern)
        if not _enough_hits(matches, min_hits):
            continue
        findings = [*findings, _finding(scanned, (code, label, fix), matches)]
    return findings


RENDER_WHY = (
    "Slop is text whose shape was chosen before its content. It clears every "
    "other gate: it compiles, it lints, it reads as competent, and nothing "
    "reports it, so the defect reaches the reader and is attributed to the "
    "author's judgment. The phrase blocklist in CLAUDE.md catches vocabulary; "
    "these are the grammatical and rhetorical shapes that survive paraphrase.\n"
    "Rule: ~/.claude/rules/anti-slop.md"
)

RENDER_FIX_TAIL = (
    "\n\nThen re-read the passage against the three deciding tests: could this "
    "sentence appear verbatim in a document about a different subject; does "
    "deleting it change the reader's next action; did the content choose the "
    "structure."
)

RENDER_BYPASS_WHEN = (
    "You are quoting someone else's text verbatim, such as a review reply that "
    "cites the comment it answers, or a document that catalogues these patterns "
    "as examples. Fenced and inline code is already excluded, so wrapping a "
    "quoted example in backticks is usually the better fix."
)


def _detected_and_fixes(
    all_findings: list[tuple[str, list[Finding]]],
) -> tuple[list[str], list[str]]:
    detected_lines: list[str] = []
    fix_lines: list[str] = []
    for label, findings in all_findings:
        detected_lines = [*detected_lines, f"{label}:"]
        for code, name, snippet, fix in findings:
            detected_lines = [*detected_lines, f"  {code} {name}", f"    {snippet}"]
            if not any(line.startswith(f"{code}: ") for line in fix_lines):
                fix_lines = [*fix_lines, f"{code}: {fix}"]
    return detected_lines, fix_lines


def render(all_findings: list[tuple[str, list[Finding]]]) -> str:
    detected_lines, fix_lines = _detected_and_fixes(all_findings)
    fix = "\n".join(fix_lines) + RENDER_FIX_TAIL
    return _block_message(
        hook=HOOK_ID,
        rule_anchor=RULE_ANCHOR,
        detected="\n".join(detected_lines),
        why=RENDER_WHY,
        fix=fix,
        bypass_when=RENDER_BYPASS_WHEN,
        decision="FIX-AND-RETRY",
        env_var=ENV_VAR,
        safety="later passages in the same session are not checked for slop tells.",
    )


def _scan(items: list[Item], path: str) -> list[tuple[str, list[Finding]]]:
    scanned = [
        (label, drop_record_findings(path, find(text, is_markdown, is_comment)))
        for label, text, is_markdown, is_comment in items
    ]
    return [(label, findings[:6]) for label, findings in scanned if findings]


def _block(tool: str, all_findings: list[tuple[str, list[Finding]]]) -> int:
    print(render(all_findings), file=sys.stderr)
    codes = sorted({code for _, f in all_findings for code, _, _, _ in f})
    _audit(
        hook=HOOK_ID,
        decision="block",
        tool=tool,
        reason="ai slop tell",
        command_excerpt=",".join(codes)[:240],
    )
    return 2


def main() -> int:
    if not should_run(HOOK_ID):
        return 0
    if os.environ.get(ENV_VAR) == "1":
        _audit(hook=HOOK_ID, decision="bypass", bypass_env=ENV_VAR)
        return 0
    if is_bypassed(HOOK_ID):
        return 0

    payload = read_hook_payload("ai-slop-blocker")

    tool = payload.get("tool_name", "")
    if tool in AGENT_TOOL_NAMES:
        return 0
    tool_input = payload.get("tool_input", {}) or {}

    items = collect(tool, tool_input)
    if not items:
        return 0

    all_findings = _scan(items, tool_input.get("file_path", "") or "")
    if not all_findings:
        return 0
    return _block(tool, all_findings)


if __name__ == "__main__":
    sys.exit(main())
