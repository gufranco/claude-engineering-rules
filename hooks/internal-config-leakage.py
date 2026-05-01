#!/usr/bin/env python3
"""
internal-config-leakage.py

PreToolUse hook that blocks references to internal Claude config in external output.
Rule source: ~/.claude/standards/code-review.md "No Internal Config Leakage".

External output channels covered:
  - Bash commands that publish text: gh pr/issue/api, glab mr/issue/api, git commit -m, git tag,
    git notes, slack-cli send.
  - Write/Edit on Markdown files (.md), since these end up in PRs and docs.

Internal references blocked:
  - ~/.claude/, .claude/rules, .claude/standards, .claude/checklists, .claude/skills, .claude/hooks
  - rules/index.yml, checklist.md, "category 12" / "category #12" / "cat 12" style references
  - "checklists/checklist.md", "rules/<name>.md", "standards/<name>.md"

Skipped:
  - Bash commands that don't publish (cat, grep, find, ls, sed, awk, less, head, tail, wc, cd, source)
  - Hook files themselves (~/.claude/hooks/**)
  - This README and CLAUDE.md (where the rule is documented)

Bypass:
  CONFIG_LEAKAGE_DISABLE=1
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
    re.compile(r"\bgit\s+notes\b"),
    re.compile(r"\bslack(?:-cli)?\s+(?:send|post|chat)\b"),
    re.compile(r"\bcurl\b.*\b(?:slack|discord|teams|telegram)\b"),
]

LEAK_PATTERNS = [
    (re.compile(r"~/\.claude\b"), "~/.claude path reference"),
    (re.compile(r"\.claude/(?:rules|standards|checklists|skills|hooks)/"), ".claude/<dir>/ reference"),
    (re.compile(r"\b(?:rules|standards|checklists)/[a-z0-9_\-]+\.md\b"), "internal markdown reference"),
    (re.compile(r"\bchecklist\.md\b"), "checklist.md reference"),
    (re.compile(r"\brules/index\.yml\b"), "rules/index.yml reference"),
    (re.compile(r"\bcategor(?:y|ies)\s*#?\s*\d+\b", re.IGNORECASE), "category number reference"),
    (re.compile(r"\bcat\.?\s*\d+\b(?!\s*(?:bytes|MB|KB|GB|files|items))"), "cat <n> shorthand"),
    (re.compile(r"checklist[s]?\s+(?:item|category)", re.IGNORECASE), "checklist item/category mention"),
]

SKIPPED_DOCS = (
    "/.claude/CLAUDE.md",
    "/.claude/rules/",
    "/.claude/standards/",
    "/.claude/checklists/",
    "/.claude/hooks/",
    "/.claude/skills/",
    "/.claude/specs/",
)


def is_publishing_bash(cmd: str) -> bool:
    return any(p.search(cmd) for p in PUBLISHING_BASH_PATTERNS)


def is_skipped_md_path(path: str) -> bool:
    if not path:
        return False
    return any(seg in path for seg in SKIPPED_DOCS)


def collect(tool: str, tool_input: dict) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    fp = tool_input.get("file_path", "") or ""
    if tool == "Bash":
        c = tool_input.get("command", "")
        if isinstance(c, str) and is_publishing_bash(c):
            out.append(("bash", "command", c))
    elif tool == "Write" and fp.lower().endswith(".md") and not is_skipped_md_path(fp):
        c = tool_input.get("content", "")
        if isinstance(c, str):
            out.append((fp, "content", c))
    elif tool == "Edit" and fp.lower().endswith(".md") and not is_skipped_md_path(fp):
        c = tool_input.get("new_string", "")
        if isinstance(c, str):
            out.append((fp, "new_string", c))
    elif tool == "MultiEdit" and fp.lower().endswith(".md") and not is_skipped_md_path(fp):
        for i, edit in enumerate(tool_input.get("edits", []) or []):
            if isinstance(edit, dict):
                c = edit.get("new_string", "")
                if isinstance(c, str):
                    out.append((fp, f"edits[{i}].new_string", c))
    return out


def find(text: str) -> list[str]:
    hits: list[str] = []
    for pat, label in LEAK_PATTERNS:
        m = pat.search(text)
        if m:
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            snippet = text[start:end].replace("\n", " | ")
            hits.append(f"{label}: ...{snippet}...")
    return hits


def main() -> int:
    if os.environ.get("CONFIG_LEAKAGE_DISABLE") == "1":
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
    for path, field, text in items:
        hits = find(text)
        if hits:
            findings.append(f"  - {field} ({path}):")
            findings.extend(f"      {h}" for h in hits[:5])

    if not findings:
        return 0

    print(
        "Blocked: internal Claude config leaking into external output. "
        "Rule: ~/.claude/standards/code-review.md \"No Internal Config Leakage\".\n"
        + "\n".join(findings)
        + "\n\nFix: rewrite the message so it reads as if a human engineer wrote it. State the "
        "engineering reason directly. Never reference `~/.claude/`, rule files, checklist categories, "
        "or standard file names in PR comments, commits, or external docs.\n"
        "Bypass (when writing about the config itself): set CONFIG_LEAKAGE_DISABLE=1.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
