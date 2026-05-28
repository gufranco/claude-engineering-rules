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
    (
        re.compile(
            r"(?:^|\n|\s)proceed\??\s*$",
            re.IGNORECASE,
        ),
        "ending the message with 'Proceed?'",
    ),
    (
        re.compile(
            r"(?:^|\n|\s)continue\??\s*$",
            re.IGNORECASE,
        ),
        "ending the message with 'Continue?'",
    ),
    (
        re.compile(
            r"(?:^|\s)shall\s+I\s+(?:proceed|continue|move\s+on|start)\b", re.IGNORECASE
        ),
        "asking 'Shall I proceed/continue/move on/start'",
    ),
    (
        re.compile(
            r"(?:^|\s)should\s+I\s+(?:proceed|continue|move\s+on|start|begin|kick\s+off)\b",
            re.IGNORECASE,
        ),
        "asking 'Should I proceed/continue/move on/start/begin/kick off'",
    ),
    (
        re.compile(r"\bsound\s+good\??", re.IGNORECASE),
        "asking 'Sound good?'",
    ),
    (
        re.compile(
            r"\blet\s+me\s+know\s+(?:if|when|whether)\s+(?:you|I)\b", re.IGNORECASE
        ),
        "deferring with 'Let me know if/when/whether'",
    ),
    (
        re.compile(
            r"\bready\s+(?:for|to\s+(?:start|move|continue))\s+phase\b", re.IGNORECASE
        ),
        "advertising readiness for next phase instead of executing it",
    ),
    (
        re.compile(
            r"\b(?:want|do\s+you\s+want)\s+me\s+to\s+(?:start|begin|kick\s+off|run|execute|do)\b",
            re.IGNORECASE,
        ),
        "asking whether the user wants you to start/begin/execute",
    ),
    (
        re.compile(
            r"\bok(?:ay)?\s+to\s+(?:proceed|continue|start|move\s+on)\b", re.IGNORECASE
        ),
        "asking 'Okay to proceed/continue/start/move on'",
    ),
    (
        re.compile(r"\bmoving\s+on\??\s*$", re.IGNORECASE),
        "ending with 'Moving on?'",
    ),
    (
        re.compile(
            r"\bshould\s+I\s+continue\s+(?:immediately|now|with|into|to)\b",
            re.IGNORECASE,
        ),
        "asking 'Should I continue immediately/now/with/into/to'",
    ),
    (
        re.compile(
            r"\b(?:do|would)\s+you\s+want\s+to\s+(?:review|pause|stop|wait|check|see|look)\b",
            re.IGNORECASE,
        ),
        "asking if the user wants to review/pause before continuing",
    ),
    (
        re.compile(
            r"\bpause\s+(?:for|to)\s+(?:feedback|review|input|approval|confirmation)\b",
            re.IGNORECASE,
        ),
        "offering to pause for feedback/review/input/approval",
    ),
    (
        re.compile(r"\bcheckpoint\s*=\s*(?:save|pause|stop)", re.IGNORECASE),
        "offering a checkpoint option",
    ),
    (
        re.compile(r"\bsave\s+state\s+and\s+resume\b", re.IGNORECASE),
        "offering to save state and resume later",
    ),
    (
        re.compile(r"\b(?:review|pause|checkpoint)\s*=\s*", re.IGNORECASE),
        "presenting review/pause/checkpoint as a menu option",
    ),
    (
        re.compile(r"\bphase\s+\d+\s+complete\b.*\?", re.IGNORECASE | re.DOTALL),
        "concluding a phase with a question",
    ),
    (
        re.compile(
            r"\b(?:next|the\s+next)\s+phase\s+(?:is|will\s+be|requires|drafts)\b",
            re.IGNORECASE,
        ),
        "describing the next phase instead of executing it",
    ),
    (
        re.compile(
            r"\bestimated\s+\d+\s*[-to]+\s*\d+\s*(?:kb|mb|files|hours|minutes)\b",
            re.IGNORECASE,
        ),
        "estimating volume of next work as if to ask permission",
    ),
    (
        re.compile(
            r"\b(?:status|progress)\s+(?:report|update|summary)\b\s*(?:before|prior to)\s+continuing",
            re.IGNORECASE,
        ),
        "framing a status report as a pre-continuation gate",
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


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.hook_profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main() -> int:
    if not should_run("auto-continue-stop-blocker"):
        _sys.exit(0)
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
