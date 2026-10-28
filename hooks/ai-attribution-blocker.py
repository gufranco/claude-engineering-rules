#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


PATTERNS = [
    re.compile(
        r"Co-authored-by:\s*.*\b(Claude|Anthropic|AI|GPT|Copilot|Cursor)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bGenerated\s+(?:by|with)\s+(?:Claude|AI|GPT|Copilot|an?\s+AI)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bAI[- ]assisted\b", re.IGNORECASE),
    re.compile(r"\bWritten\s+by\s+(?:Claude|AI|GPT)\b", re.IGNORECASE),
    re.compile(r"Authored[- ]by[- ]Claude", re.IGNORECASE),
    re.compile(r"\[Claude(?:\s+Code)?\]", re.IGNORECASE),
    re.compile(r"^\s*Claude-Session:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"claude\.ai/code/session_", re.IGNORECASE),
]

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.outgoing_commits import (  # noqa: E402
    PushInvocation,
    find_pushes,
    outgoing_messages,
)


def _snippet(text: str, idx: int) -> str:
    start = max(0, idx - 40)
    end = min(len(text), idx + 60)
    return text[start:end].replace("\n", " | ")


def find_violations(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for pat in PATTERNS:
        m = pat.search(text)
        if m:
            out.append((m.group(0), _snippet(text, m.start())))
    return out


SKIPPED_DOC_SEGMENTS = (
    "/.claude/CLAUDE.md",
    "/.claude/rules/",
    "/.claude/standards/",
    "/.claude/checklists/",
    "/.claude/hooks/",
    "/.claude/skills/",
)

SKIPPED_TEST_SEGMENTS = (
    "/tests/",
    "/test/",
    "/__tests__/",
    ".test.",
    ".spec.",
)


def is_skipped_path(path: str) -> bool:
    if not path:
        return False
    if any(seg in path for seg in SKIPPED_DOC_SEGMENTS):
        return True
    p = path.lower()
    if any(seg in p for seg in SKIPPED_TEST_SEGMENTS):
        return True
    return False


def collect_texts(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    fp = tool_input.get("file_path", "") or ""
    if tool in ("Write", "Edit", "MultiEdit") and is_skipped_path(fp):
        return out
    if tool == "Write":
        c = tool_input.get("content", "")
        if isinstance(c, str):
            out.append(("content", c))
    elif tool == "Edit":
        c = tool_input.get("new_string", "")
        if isinstance(c, str):
            out.append(("new_string", c))
    elif tool == "MultiEdit":
        for i, edit in enumerate(tool_input.get("edits", []) or []):
            if isinstance(edit, dict):
                c = edit.get("new_string", "")
                if isinstance(c, str):
                    out.append((f"edits[{i}].new_string", c))
    elif tool == "Bash":
        c = tool_input.get("command", "")
        if isinstance(c, str):
            out.append(("command", c))
    return out


from _lib.hook_profile import should_run  # noqa: E402


def main() -> int:
    if not should_run("ai-attribution-blocker"):
        sys.exit(0)
    if os.environ.get("AI_ATTRIBUTION_DISABLE") == "1":
        _audit(
            hook="ai-attribution-blocker",
            decision="bypass",
            bypass_env="AI_ATTRIBUTION_DISABLE",
        )
        return 0
    if is_bypassed("ai-attribution-blocker"):
        return 0

    payload = read_hook_payload("ai-attribution-blocker")

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    cwd = str(payload.get("cwd") or os.getcwd())
    findings = _findings(collect_texts(tool, tool_input)) + _push_findings(
        tool, tool_input, cwd
    )

    if not findings:
        return 0
    return _block(tool, findings)


def _findings(texts: list[tuple[str, str]]) -> list[str]:
    return [
        f"  - {match!r} in {field}: ...{snippet}..."
        for field, text in texts
        for match, snippet in find_violations(text)
    ]


def _push_findings(tool: str, tool_input: dict, cwd: str) -> list[str]:
    command = tool_input.get("command", "")
    if tool != "Bash" or not isinstance(command, str):
        return []
    return [
        finding for push in find_pushes(command, cwd) for finding in _outgoing(push)
    ]


def _outgoing(push: PushInvocation) -> list[str]:
    messages = outgoing_messages(push)
    if messages is None:
        return [
            f"  - could not read outgoing commits in {push.directory}; "
            "the push stays blocked until they can be checked"
        ]
    return [
        f"  - {match!r} in outgoing commits of {push.directory}: ...{snippet}..."
        for match, snippet in find_violations(messages)
    ]


def _block(tool: str, findings: list[str]) -> int:
    print(
        "Blocked: AI attribution detected. "
        "Rule: ~/.claude/CLAUDE.md (No AI attribution) and ~/.claude/rules/git-workflow.md.\n"
        + "\n".join(findings)
        + "\n\nFix: remove the attribution line. Never add Co-authored-by or 'Generated by AI' "
        "to commits, PR descriptions, or code. For an outgoing commit, reword it "
        "with git rebase -i before pushing.\n"
        "Bypass (rare): set AI_ATTRIBUTION_DISABLE=1 in the environment.",
        file=sys.stderr,
    )
    _audit(
        hook="ai-attribution-blocker",
        decision="block",
        tool=tool,
        reason="AI attribution detected",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
