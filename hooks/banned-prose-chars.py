#!/usr/bin/env python3
"""
banned-prose-chars.py

PreToolUse hook that blocks tool calls whose payloads contain characters
banned by ~/.claude/rules/code-style.md "Writing Style":

  - Em dashes (U+2014)
  - Emojis and decorative Unicode (multiple ranges)
  - Box-drawing characters (U+2500-U+257F)

Scans:
  - Write.content
  - Edit.new_string
  - MultiEdit.edits[].new_string
  - Bash.command  (catches `gh api --field body=...`, `git commit -m ...`,
                   `cat <<'EOF' ... EOF` heredocs, etc.)

Other tool inputs pass through unchecked. Read.* is never scanned: the rule
forbids producing these characters, not seeing them.

Exit codes:
  0 - allow
  2 - block; stderr explains which character + a snippet of context

Bypass:
  BANNED_PROSE_CHARS_DISABLE=1 to skip (intended for one-off cases where the
  user explicitly asks to preserve banned characters in existing content).
"""

from __future__ import annotations

import json
import os
import re
import sys

EM_DASH = "\u2014"

BOX_DRAWING_RE = re.compile(r"[\u2500-\u257F]")

EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # symbols, pictographs, supplemental
    "\U00002600-\U000027BF"  # misc symbols + dingbats
    "\U0001F1E6-\U0001F1FF"  # regional indicator (flags)
    "\U0000FE0F"             # variation selector-16 (emoji presentation)
    "\U0000200D"             # zero-width joiner (used in compound emoji)
    "]"
)


def _snippet(text: str, idx: int) -> str:
    start = max(0, idx - 40)
    end = min(len(text), idx + 41)
    return text[start:end].replace("\n", "\u23CE")  # show newlines as a marker


def find_violations(text: str) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []

    if EM_DASH in text:
        idx = text.index(EM_DASH)
        findings.append(("em dash (U+2014)", _snippet(text, idx)))

    box_match = BOX_DRAWING_RE.search(text)
    if box_match:
        findings.append(
            ("box-drawing character", _snippet(text, box_match.start()))
        )

    emoji_match = EMOJI_RE.search(text)
    if emoji_match:
        findings.append(("emoji / decorative unicode", _snippet(text, emoji_match.start())))

    return findings


def collect_texts(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
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


def main() -> int:
    if os.environ.get("BANNED_PROSE_CHARS_DISABLE") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    texts = collect_texts(tool, tool_input)
    if not texts:
        return 0

    all_findings: list[str] = []
    for field, text in texts:
        for kind, snippet in find_violations(text):
            all_findings.append(f"  - {kind} in {field}: ...{snippet}...")

    if not all_findings:
        return 0

    print(
        "Blocked: payload contains characters banned by "
        "~/.claude/rules/code-style.md \"Writing Style\".\n"
        + "\n".join(all_findings)
        + "\n\nFix:\n"
        "  - Replace em dashes with a period, comma, colon, or rewrite.\n"
        "  - Remove emojis and decorative unicode.\n"
        "  - Use Mermaid in fenced code blocks instead of box-drawing diagrams.\n"
        "\nBypass (one-off, when explicitly preserving existing content): "
        "set BANNED_PROSE_CHARS_DISABLE=1 in the environment.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
