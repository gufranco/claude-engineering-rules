#!/usr/bin/env python3
"""
banned-phrases-blocker.py

PreToolUse hook that blocks banned conversational phrases in external output.
Rule source: ~/.claude/CLAUDE.md "Banned Phrases".

Coverage:
  - Bash commands that publish text: gh pr/issue/api, glab mr/issue/api, git commit -m,
    slack send, curl to webhooks.
  - Write/Edit on Markdown files (.md) outside ~/.claude/.

The bypass is intended for quoting other people's text (review responses, citations).

Bypass:
  BANNED_PHRASES_DISABLE=1
"""

from __future__ import annotations

import json
import os
import re
import sys

PUBLISHING_BASH_PATTERNS = [
    re.compile(r"\bgh\s+(?:pr|issue|api|release|gist)\b"),
    re.compile(r"\bglab\s+(?:mr|issue|api|release)\b"),
    re.compile(r"\bgit\s+commit\b"),
    re.compile(r"\bgit\s+tag\b"),
    re.compile(r"\bslack(?:-cli)?\s+(?:send|post|chat)\b"),
    re.compile(r"\bcurl\b.*\b(?:slack|discord|teams|telegram|hooks\.)"),
]

OPENERS = [
    "Great question!", "Sure!", "Absolutely!", "Of course!",
    "That's a great point", "That is a great point",
    "Perfect!", "Excellent!", "Wonderful!",
]
CLOSERS = [
    "Let me know if you need anything else",
    "Let me know if you have any questions",
    "Hope this helps", "Hope that helps",
    "Feel free to ask", "Feel free to reach out",
    "Happy to help",
]
HEDGES = [
    "It's worth noting", "It is worth noting",
    "It should be noted", "It's important to mention",
    "It is important to mention", "It is important to note",
    "Keep in mind that",
]
TRANSITIONS = [
    "That said,", "With that in mind,", "Having said that,", "On that note,",
]
FLUFF = [
    "robust", "comprehensive", "seamless", "elegant",
    "powerful", "streamlined", "cutting-edge", "leverage",
    "best-in-class", "world-class", "game-changing",
    "synergy", "synergies",
]


def build_pattern(phrases: list[str], boundary: bool = True) -> re.Pattern:
    escaped = [re.escape(p) for p in phrases]
    body = "|".join(escaped)
    if boundary:
        return re.compile(rf"\b(?:{body})\b", re.IGNORECASE)
    return re.compile(rf"(?:{body})", re.IGNORECASE)


CATEGORIES = [
    ("opener", build_pattern(OPENERS, boundary=False)),
    ("closer", build_pattern(CLOSERS, boundary=False)),
    ("hedge", build_pattern(HEDGES, boundary=False)),
    ("transition", build_pattern(TRANSITIONS, boundary=False)),
    ("fluff adjective", build_pattern(FLUFF, boundary=True)),
]

SKIPPED_DOCS = (
    "/.claude/CLAUDE.md",
    "/.claude/rules/",
    "/.claude/standards/",
    "/.claude/checklists/",
    "/.claude/hooks/",
    "/.claude/skills/",
    "CHANGELOG.md",
)


def is_publishing_bash(cmd: str) -> bool:
    return any(p.search(cmd) for p in PUBLISHING_BASH_PATTERNS)


def is_skipped_md_path(path: str) -> bool:
    if not path:
        return False
    return any(seg in path for seg in SKIPPED_DOCS)


def collect(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    fp = tool_input.get("file_path", "") or ""
    if tool == "Bash":
        c = tool_input.get("command", "")
        if isinstance(c, str) and is_publishing_bash(c):
            out.append(("bash command", c))
    elif tool == "Write" and fp.lower().endswith(".md") and not is_skipped_md_path(fp):
        c = tool_input.get("content", "")
        if isinstance(c, str):
            out.append((fp, c))
    elif tool == "Edit" and fp.lower().endswith(".md") and not is_skipped_md_path(fp):
        c = tool_input.get("new_string", "")
        if isinstance(c, str):
            out.append((fp, c))
    elif tool == "MultiEdit" and fp.lower().endswith(".md") and not is_skipped_md_path(fp):
        for i, edit in enumerate(tool_input.get("edits", []) or []):
            if isinstance(edit, dict):
                c = edit.get("new_string", "")
                if isinstance(c, str):
                    out.append((f"{fp} [{i}]", c))
    return out


def find(text: str) -> list[str]:
    hits: list[str] = []
    for label, pat in CATEGORIES:
        m = pat.search(text)
        if m:
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            snippet = text[start:end].replace("\n", " | ")
            hits.append(f"{label} {m.group(0)!r}: ...{snippet}...")
    return hits


def main() -> int:
    if os.environ.get("BANNED_PHRASES_DISABLE") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    items = collect(tool, tool_input)
    if not items:
        return 0

    findings: list[str] = []
    for label, text in items:
        hits = find(text)
        if hits:
            findings.append(f"  - {label}:")
            findings.extend(f"      {h}" for h in hits[:5])

    if not findings:
        return 0

    print(
        "Blocked: banned phrase detected in external output. "
        "Rule: ~/.claude/CLAUDE.md \"Banned Phrases\".\n"
        + "\n".join(findings)
        + "\n\nFix: rewrite without openers ('Great question!'), closers ('Let me know if'), "
        "hedges ('It's worth noting'), transitions ('That said,'), or fluff adjectives "
        "('robust', 'comprehensive', 'seamless'). State the point directly.\n"
        "Bypass (when quoting someone else's text): set BANNED_PHRASES_DISABLE=1.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
