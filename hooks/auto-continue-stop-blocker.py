#!/usr/bin/env python3
"""
auto-continue-stop-blocker.py

Stop hook. Blocks the "checkpoint and wait" pattern when the model
tries to end its turn without either (a) calling AskUserQuestion for
a real blocking decision or (b) finishing every task in the active
plan. Forces the model to keep executing.

Rule source: ~/.claude/CLAUDE.md "Execute, don't ask" and the feedback
memory "no checkpoint stops, push through the plan".

Input (PreStop event JSON on stdin):
  - session_id
  - transcript_path
  - stop_hook_active  (true if this hook already fired this turn; we
                       must return 0 to break the loop)

Output:
  - exit 0: allow stop
  - exit 2: block stop, message on stderr shown to the model

Bypass:
  AUTO_CONTINUE_DISABLE=1
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Phrases that indicate the model is parking the work instead of
# either asking a real question or finishing the plan.
CHECKPOINT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bstopping\s+(?:here|at\s+this|as\s+a)\b", re.IGNORECASE),
        "stopping for permission instead of continuing",
    ),
    (
        re.compile(r"natural\s+(?:check|stop)\s?point", re.IGNORECASE),
        "describing the moment as a checkpoint",
    ),
    (
        re.compile(r"tell\s+me\s+(?:when|to)\s+continue", re.IGNORECASE),
        "asking permission to continue",
    ),
    (
        re.compile(r"say\s+(?:go|continue|next)\b", re.IGNORECASE),
        "waiting for a go signal",
    ),
    (
        re.compile(r"if\s+you\s+want\s+me\s+to\s+continue", re.IGNORECASE),
        "conditional continuation",
    ),
    (
        re.compile(
            r"or\s+which\s+(?:phase|step|module)\s+to\s+jump\s+to", re.IGNORECASE
        ),
        "offering to skip ahead instead of pushing forward",
    ),
    (re.compile(r"\bnext\s+batch[:.]", re.IGNORECASE), "next-batch deferral"),
    (
        re.compile(r"awaiting\s+your\s+(?:direction|input|answer)", re.IGNORECASE),
        "passive deferral",
    ),
    (
        re.compile(r"give\s+me\s+the\s+go-?ahead", re.IGNORECASE),
        "explicit ask for go-ahead",
    ),
    (
        re.compile(
            r"continuing\s+in\s+(?:subsequent|later|future)\s+turns?", re.IGNORECASE
        ),
        "deferring to a later turn",
    ),
    (
        re.compile(r"resume\s+in\s+the\s+next\s+session", re.IGNORECASE),
        "deferring to the next session",
    ),
    (
        re.compile(r"would\s+you\s+like\s+me\s+to\s+continue", re.IGNORECASE),
        "asking if the user wants continuation",
    ),
    (
        re.compile(
            r"\bI('|\s+a)?ll\s+(?:continue|resume)\s+(?:in|on)\s+(?:the\s+)?next",
            re.IGNORECASE,
        ),
        "promising continuation later",
    ),
    (
        re.compile(r"\bdone:\s.*\.\s*Next\s+(?:batch|step|phase)\b", re.IGNORECASE),
        "DONE summary that promises a next batch",
    ),
]


def read_transcript_messages(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    return out


def last_assistant_turn(messages: list[dict]) -> dict | None:
    for entry in reversed(messages):
        if entry.get("type") == "assistant":
            return entry
    return None


def extract_text_and_tool_uses(entry: dict) -> tuple[str, list[str]]:
    msg = entry.get("message", {}) or {}
    content = msg.get("content", [])
    text_parts: list[str] = []
    tool_uses: list[str] = []
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                t = block.get("text")
                if isinstance(t, str):
                    text_parts.append(t)
            elif block_type == "tool_use":
                name = block.get("name")
                if isinstance(name, str):
                    tool_uses.append(name)
    elif isinstance(content, str):
        text_parts.append(content)
    return ("\n".join(text_parts), tool_uses)


def find_violations(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for pat, label in CHECKPOINT_PATTERNS:
        m = pat.search(text)
        if m:
            snippet = text[max(0, m.start() - 30) : m.end() + 60].replace("\n", " | ")
            out.append((m.group(0), f"{label}: ...{snippet}..."))
    return out


def main() -> int:
    if os.environ.get("AUTO_CONTINUE_DISABLE") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    # Break the recursion loop. If this hook already blocked once and the
    # model still wants to stop, let it stop.
    if payload.get("stop_hook_active"):
        return 0

    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return 0

    messages = read_transcript_messages(transcript_path)
    last = last_assistant_turn(messages)
    if not last:
        return 0

    text, tool_uses = extract_text_and_tool_uses(last)

    # If the model is calling AskUserQuestion, the stop is legitimate.
    if "AskUserQuestion" in tool_uses:
        return 0

    # If the model called ExitPlanMode (plan-mode handoff), that's legitimate.
    if "ExitPlanMode" in tool_uses:
        return 0

    findings = find_violations(text)
    if not findings:
        return 0

    bullet_lines = "\n".join(
        f"  - {match!r}\n      {snippet}" for match, snippet in findings
    )

    print(
        "Blocked: turn-ending pattern detected without a genuine blocking question.\n"
        "Rule: ~/.claude/CLAUDE.md 'Execute, don't ask'.\n\n"
        f"{bullet_lines}\n\n"
        "Keep executing. Do not write checkpoint summaries between phases. Stop only when:\n"
        "  1. you call AskUserQuestion for a real blocking decision the user has not\n"
        "     yet answered; or\n"
        "  2. every task in the active plan is verifiably complete; or\n"
        "  3. a hard failure (hook block you cannot bypass, tool unavailable, etc.) leaves\n"
        "     no forward action and you state that specific blocker plainly.\n\n"
        "The user's default answer to 'should I continue?' is yes. Stop asking.\n\n"
        "Bypass (rare; emergencies only): export AUTO_CONTINUE_DISABLE=1 in the parent shell.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
