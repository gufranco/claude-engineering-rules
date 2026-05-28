#!/usr/bin/env python3
"""
banned-phrases-blocker.py

PreToolUse hook that blocks banned conversational phrases in external output
and meta-question openers in subagent prompts.
Rule sources:
  - ~/.claude/CLAUDE.md "Banned Phrases" (openers, closers, hedges, transitions, fluff).
  - ~/.claude/rules/design-philosophy.md "Strategic vs Tactical Programming"
    (tactical hyperbole: "quick fix", "temporary workaround", "cleanup later").
  - ~/.claude/rules/smart-questions.md "Briefing Subagents" + "Ship the Question"
    (Agent/Task prompts must not start with a meta-question).

Coverage:
  - Bash commands that publish text: gh pr/issue/api, glab mr/issue/api, git commit -m,
    slack send, curl to webhooks.
  - Write/Edit on Markdown files (.md) outside ~/.claude/.
  - Agent/Task tool `prompt` field: leading meta-question phrases.

The bypass is intended for quoting other people's text (review responses, citations).

Bypass:
  BANNED_PHRASES_DISABLE=1
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
try:
    from audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


PUBLISHING_BASH_PATTERNS = [
    re.compile(r"\bgh\s+(?:pr|issue|api|release|gist)\b"),
    re.compile(r"\bglab\s+(?:mr|issue|api|release)\b"),
    re.compile(r"\bgit\s+commit\b"),
    re.compile(r"\bgit\s+tag\b"),
    re.compile(r"\bslack(?:-cli)?\s+(?:send|post|chat)\b"),
    re.compile(r"\bcurl\b.*\b(?:slack|discord|teams|telegram|hooks\.)"),
]

OPENERS = [
    "Great question!",
    "Sure!",
    "Absolutely!",
    "Of course!",
    "That's a great point",
    "That is a great point",
    "Perfect!",
    "Excellent!",
    "Wonderful!",
]
CLOSERS = [
    "Let me know if you need anything else",
    "Let me know if you have any questions",
    "Hope this helps",
    "Hope that helps",
    "Feel free to ask",
    "Feel free to reach out",
    "Happy to help",
]
HEDGES = [
    "It's worth noting",
    "It is worth noting",
    "It should be noted",
    "It's important to mention",
    "It is important to mention",
    "It is important to note",
    "Keep in mind that",
]
TRANSITIONS = [
    "That said,",
    "With that in mind,",
    "Having said that,",
    "On that note,",
]
FLUFF = [
    "robust",
    "comprehensive",
    "seamless",
    "elegant",
    "powerful",
    "streamlined",
    "cutting-edge",
    "leverage",
    "best-in-class",
    "world-class",
    "game-changing",
    "synergy",
    "synergies",
]
TACTICAL = [
    "quick fix",
    "quick win",
    "temporary fix",
    "temporary workaround",
    "temporary hack",
    "band-aid",
    "bandaid",
    "we'll fix later",
    "we will fix later",
    "cleanup later",
    "clean up later",
    "fix it later",
]

AGENT_META_QUESTIONS = [
    "Can you find",
    "Can you check",
    "Can you look",
    "Could you find",
    "Could you check",
    "Could you look",
    "Help me with",
    "Help me find",
    "Quick question",
    "Anyone good at",
    "Anyone know",
    "Any expert",
    "Should I ask",
    "Can I ask",
    "Just wondering",
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
    ("tactical hyperbole", build_pattern(TACTICAL, boundary=False)),
]

AGENT_META_LEADING = re.compile(
    r"^\s*(?:" + "|".join(re.escape(p) for p in AGENT_META_QUESTIONS) + r")\b",
    re.IGNORECASE,
)
AGENT_TOOL_NAMES = ("Agent", "Task")

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
    elif (
        tool == "MultiEdit"
        and fp.lower().endswith(".md")
        and not is_skipped_md_path(fp)
    ):
        for i, edit in enumerate(tool_input.get("edits", []) or []):
            if isinstance(edit, dict):
                c = edit.get("new_string", "")
                if isinstance(c, str):
                    out.append((f"{fp} [{i}]", c))
    return out


def find_agent_meta_question(prompt: str) -> str | None:
    """Detect a meta-question opener in a subagent prompt.

    Only fires when the prompt's first non-whitespace tokens match one of
    the banned meta-question phrases. Mid-prompt occurrences are allowed
    because they may be quoted examples.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    m = AGENT_META_LEADING.match(prompt)
    if not m:
        return None
    return m.group(0).strip()


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


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main() -> int:
    if not should_run("banned-phrases-blocker"):
        _sys.exit(0)
    if os.environ.get("BANNED_PHRASES_DISABLE") == "1":
        _audit(
            hook="banned-phrases-blocker",
            decision="bypass",
            bypass_env="BANNED_PHRASES_DISABLE",
        )
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    if tool in AGENT_TOOL_NAMES:
        prompt = tool_input.get("prompt", "")
        hit = find_agent_meta_question(prompt)
        if hit:
            print(
                "Blocked: subagent prompt starts with a meta-question. "
                f"Leading phrase: {hit!r}. "
                'Rule: ~/.claude/rules/smart-questions.md "Briefing Subagents" '
                'and "Ship the Question".\n'
                "Fix: replace the meta-prompt with the actual instruction. "
                "Include scope, file:line refs from prior investigation, prior "
                "attempts, expected output shape, and a response-length cap.\n"
                "Bypass (rare; only when quoting another message): "
                "BANNED_PHRASES_DISABLE=1.",
                file=sys.stderr,
            )
            _audit(
                hook="banned-phrases-blocker",
                decision="block",
                tool=tool,
                reason="agent meta-question",
                command_excerpt=hit[:240],
            )
            return 2

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
        'Rule: ~/.claude/CLAUDE.md "Banned Phrases".\n'
        + "\n".join(findings)
        + "\n\nFix: rewrite without openers ('Great question!'), closers ('Let me know if'), "
        "hedges ('It's worth noting'), transitions ('That said,'), fluff adjectives "
        "('robust', 'comprehensive', 'seamless'), or tactical hyperbole "
        "('quick fix', 'temporary workaround', 'cleanup later'). State the point directly. "
        "Tactical hyperbole signals weak engineering and is permanent once published.\n"
        "Bypass (when quoting someone else's text): set BANNED_PHRASES_DISABLE=1.",
        file=sys.stderr,
    )
    _audit(
        hook="banned-phrases-blocker",
        decision="block",
        tool=tool,
        reason="banned phrase",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
