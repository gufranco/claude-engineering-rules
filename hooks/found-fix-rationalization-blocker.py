#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\bnot\s+introduced\s+by\s+(?:this|these|my|the)\s+"
            r"(?:pr|mr|change|task|commit|work|patch|fix|push)\b",
            re.IGNORECASE,
        ),
        "'not introduced by this <thing>' is a banned inaction rationalization",
    ),
    (
        re.compile(
            r"\bpre[-\s]?existing\b[^.\n]*?\b"
            r"(?:not\s+(?:mine|introduced|in\s+scope|from\s+this|my\s+(?:task|change|pr|mr)))",
            re.IGNORECASE,
        ),
        "'pre-existing, not mine' is a banned inaction rationalization",
    ),
    (
        re.compile(
            r"\borthogonal\s+to\s+(?:this|the)\s+"
            r"(?:task|work|change|pr|mr|commit|fix|push)\b",
            re.IGNORECASE,
        ),
        "'orthogonal to this <thing>' is a banned inaction rationalization",
    ),
    (
        re.compile(
            r"\bout\s+of\s+scope\s+(?:for|of)\s+(?:this|the)\s+"
            r"(?:task|pr|mr|change|commit|work|fix|push)\b",
            re.IGNORECASE,
        ),
        "'out of scope of this <thing>' is a banned inaction rationalization",
    ),
    (
        re.compile(
            r"\bleave\s+(?:this\s+|it\s+)?for\s+(?:a\s+)?"
            r"(?:later|future|next|subsequent|follow[-\s]?up)\b",
            re.IGNORECASE,
        ),
        "'leave for later/future' defers a flagged issue; fix now",
    ),
    (
        re.compile(
            r"\bleave\s+for\s+(?:a|the)?\s*"
            r"(?:future|later|next|subsequent|follow[-\s]?up)\s+"
            r"(?:task|pr|mr|commit|change|work|fix)\b",
            re.IGNORECASE,
        ),
        "'leave for a future task/PR' defers a flagged issue; fix now",
    ),
    (
        re.compile(
            r"\bnot\s+blocking\s+(?:the|this)\s+"
            r"(?:run|build|pipeline|ci|merge|deploy)\b",
            re.IGNORECASE,
        ),
        "'not blocking the run' treats annotations as non-blocking; they are blocking by rule",
    ),
    (
        re.compile(
            r"\b(?:deprecation|annotation|warning|notice|alert)\s+"
            r"(?:will\s+be|to\s+be)\s+"
            r"(?:addressed|fixed|handled|resolved)\s+"
            r"(?:later|in\s+(?:a\s+)?(?:future|next|subsequent|follow[-\s]?up))",
            re.IGNORECASE,
        ),
        "Deferring a deprecation/annotation/warning is banned; fix in the same task",
    ),
    (
        re.compile(
            r"\b(?:filed?|filing|opened?|opening|logged?|raised?|created?)\s+"
            r"(?:a|an|the|another)?\s*(?:new\s+|separate\s+|follow[-\s]?up\s+)?"
            r"(?:issue|ticket|task|card)\b"
            r"|\bfiled\s+as\b"
            r"|\btrack(?:ed|ing)?\s+(?:it\s+)?in\s+(?:a|an|the)?\s*"
            r"(?:issue|ticket|task|card|[A-Z]{2,}-\d+)\b",
            re.IGNORECASE,
        ),
        "a tracker item does not fix the problem; fix it in this change",
    ),
    (
        re.compile(
            r"\b(?:will|to)\s+(?:follow[-\s]?up|fix|address|handle|do|land)\b"
            r"[^.\n]{0,40}?\b(?:in\s+)?(?:a\s+|the\s+|another\s+)?"
            r"(?:follow[-\s]?up|separate|later|next|subsequent|future)\b"
            r"[^.\n]{0,20}?\b(?:pr|mr|change|commit|patch|branch|pass|task)\b",
            re.IGNORECASE,
        ),
        "a follow-up change does not fix the problem; fix it in this change",
    ),
    (
        re.compile(
            r"\b(?:fixing|fix|addressing|handling|doing|landing)\b"
            r"[^.\n]{0,30}?\bin\s+(?:a\s+|the\s+|another\s+)?"
            r"(?:follow[-\s]?up|separate|later|next|subsequent|future)\s+"
            r"(?:pr|mr|change|commit|patch|branch|pass|task)\b",
            re.IGNORECASE,
        ),
        "a follow-up change does not fix the problem; fix it in this change",
    ),
]


SKIPPED_PATH_SEGMENTS = (
    "/.claude/rules/found-fix.md",
    "/rules/found-fix.md",
    "/.claude/standards/found-fix.md",
    "/hooks/found-fix-rationalization-blocker.py",
    "/tests/hooks/found-fix-rationalization-blocker/",
    "/memory/feedback_found_fix",
    "/CHANGELOG.md",
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.git_invocation import strip_git_global_options  # noqa: E402
from _lib.shell_segments import mask_literal_text  # noqa: E402
from _lib.published_text import is_scratch_path, published_text  # noqa: E402


def is_skipped_path(path: str) -> bool:
    if not path:
        return False
    return any(seg in path for seg in SKIPPED_PATH_SEGMENTS)


PUBLISHING_BASH_PATTERNS = (
    re.compile(r"\bgit\s+commit\b"),
    re.compile(r"\bgit\s+tag\b.*-m\b"),
    re.compile(r"\bgit\s+notes\s+(?:add|append)\b"),
    re.compile(r"\bgh\s+pr\s+(?:create|edit|comment|review)\b"),
    re.compile(r"\bgh\s+release\s+(?:create|edit)\b"),
    re.compile(r"\bgh\s+issue\s+(?:create|edit|comment)\b"),
    re.compile(r"\bglab\s+mr\s+(?:create|update|note)\b"),
    re.compile(r"\bglab\s+release\s+create\b"),
    re.compile(r"\bglab\s+issue\s+(?:create|update|note)\b"),
)


def bash_command_publishes(command: str) -> bool:
    matched = strip_git_global_options(mask_literal_text(command))
    return any(pat.search(matched) for pat in PUBLISHING_BASH_PATTERNS)


EDIT_TOOLS = ("Write", "Edit", "MultiEdit")


def _multiedit_fields(tool_input: dict) -> list[tuple[str, str]]:
    edits = [
        (i, edit.get("new_string", ""))
        for i, edit in enumerate(tool_input.get("edits", []) or [])
        if isinstance(edit, dict)
    ]
    return [(f"edits[{i}].new_string", c) for i, c in edits if isinstance(c, str)]


def _edit_fields(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    if tool == "MultiEdit":
        return _multiedit_fields(tool_input)
    field = "content" if tool == "Write" else "new_string"
    c = tool_input.get(field, "")
    return [(field, c)] if isinstance(c, str) else []


def collect_texts(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    fp = tool_input.get("file_path", "") or ""
    if tool == "Bash":
        c = tool_input.get("command", "")
        return (
            [("command", c)] if isinstance(c, str) and bash_command_publishes(c) else []
        )
    if tool not in EDIT_TOOLS or is_skipped_path(fp) or is_scratch_path(fp):
        return []
    return [
        (field, published_text(fp, c)) for field, c in _edit_fields(tool, tool_input)
    ]


def find_violations(text: str) -> list[tuple[str, str, str]]:
    violations: list[tuple[str, str, str]] = []
    for pat, reason in PATTERNS:
        for m in pat.finditer(text):
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            snippet = text[start:end].replace("\n", " ")
            violations.append((m.group(0), reason, snippet))
    return violations


from _lib.hook_profile import should_run  # noqa: E402


def _disabled() -> bool:
    if not should_run("found-fix-rationalization-blocker"):
        return True
    if os.environ.get("FOUND_FIX_RATIONALIZATION_DISABLE") == "1":
        _audit(
            hook="found-fix-rationalization-blocker",
            decision="bypass",
            bypass_env="FOUND_FIX_RATIONALIZATION_DISABLE",
        )
        return True
    return is_bypassed("found-fix-rationalization-blocker")


def _findings(texts: list[tuple[str, str]]) -> list[str]:
    return [
        f"  - {match!r} ({reason})\n    in {field}: ...{snippet}..."
        for field, text in texts
        for match, reason, snippet in find_violations(text)
    ]


def _report(tool: str, findings: list[str]) -> int:
    print(
        "Blocked: 'found, did not fix' rationalization detected in artifact.\n"
        "Rule: ~/.claude/rules/found-fix.md.\n"
        "A problem surfaced by a verification surface is in scope for the\n"
        "current task regardless of when it was introduced. Fix it, then\n"
        "rewrite the artifact without the inaction language.\n\n"
        + "\n".join(findings)
        + "\n\nFix: address the underlying issue, then write the commit/PR\n"
        "body in terms of what changed and why. Do not justify inaction\n"
        "on a flagged issue.\n\n"
        "Bypass (rare; when writing about the rule itself or a postmortem\n"
        "that legitimately discusses these phrases):\n"
        "  export FOUND_FIX_RATIONALIZATION_DISABLE=1",
        file=sys.stderr,
    )
    _audit(
        hook="found-fix-rationalization-blocker",
        decision="block",
        tool=tool,
        reason="found-fix rationalization detected",
        command_excerpt=" | ".join(f[:120] for f in findings)[:240]
        if findings
        else None,
    )
    return 2


def main() -> int:
    if _disabled():
        return 0
    payload = read_hook_payload("found-fix-rationalization-blocker")
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    findings = _findings(collect_texts(tool, tool_input))
    if not findings:
        return 0
    return _report(tool, findings)


if __name__ == "__main__":
    sys.exit(main())
