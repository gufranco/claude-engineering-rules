#!/usr/bin/env python3
"""subagent-brief-quality

PreToolUse hook that validates the structure of Agent/Task subagent prompts.

Rule source: ~/.claude/rules/smart-questions.md "Briefing Subagents".

Required elements in a well-formed Agent prompt:

  1. Specific reference: a file path, `file:line`, function name, or error code.
  2. Response-length cap: a word/sentence/paragraph budget.
  3. Output shape: a noun naming what the agent must return.
  4. Not a meta-prompt: the first line is the actual instruction.

Severity ladder:
  - Two or more failures: block (exit 2).
  - Exactly one failure: advisory audit, exit 0.
  - All four satisfied: silent pass.

Bypass:
  SUBAGENT_BRIEF_DISABLE=1
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


AGENT_TOOL_NAMES = ("Agent", "Task")

FILE_LINE_PATTERN = re.compile(
    r"""(?ix)
    (?:
        [\w./-]+\.(?:ts|tsx|js|jsx|py|go|rs|java|kt|rb|php|cs|cpp|c|h|hpp|swift|m|mm|sh|bash|zsh|yml|yaml|json|toml|sql|md|html|css|scss|sass|vue|svelte|prisma|proto)
        (?::\d+)?
        |
        \b[\w/-]+/[\w./-]+
        |
        \b\w+\(\s*\)
        |
        \berror\s+code\s+[A-Z]\d+\b
        |
        \b[A-Z]\d{3,5}\b
    )
    """
)

LENGTH_CAP_PATTERN = re.compile(
    r"""(?ix)
    (?:
        under\s+\d+\s+(?:words?|chars?|characters?|sentences?|paragraphs?|tokens?|lines?)
        |
        (?:no\s+more\s+than|at\s+most|max(?:imum)?|fewer\s+than|less\s+than|up\s+to)\s+\d+\s+(?:words?|chars?|characters?|sentences?|paragraphs?|tokens?|lines?)
        |
        \d+\s+(?:words?|chars?|characters?|sentences?|paragraphs?|tokens?|lines?)\s+(?:max|maximum|limit|cap|or\s+less)
        |
        one\s+(?:sentence|paragraph|line)
        |
        single\s+(?:sentence|paragraph|line)
        |
        brief(?:ly)?\b
        |
        be\s+terse\b
        |
        short\s+(?:answer|report|response|summary)
    )
    """
)

OUTPUT_SHAPE_KEYWORDS = (
    "report",
    "return",
    "produce",
    "output",
    "list",
    "table",
    "summary",
    "findings",
    "result",
    "answer",
    "punch list",
    "checklist",
    "diff",
    "patch",
    "plan",
)
OUTPUT_SHAPE_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in OUTPUT_SHAPE_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

META_LEADING_PATTERN = re.compile(
    r"""^\s*(?:
        Can\s+you\s+(?:find|check|look|help)\b
        |
        Could\s+you\s+(?:find|check|look|help)\b
        |
        Help\s+me\s+(?:with|find)\b
        |
        Quick\s+question\b
        |
        Anyone\s+(?:good|know)\b
        |
        Any\s+expert\b
        |
        Should\s+I\s+ask\b
        |
        Can\s+I\s+ask\b
        |
        Just\s+wondering\b
        |
        Hi[!.,]?\s*$
        |
        Hello[!.,]?\s*$
    )""",
    re.IGNORECASE | re.VERBOSE,
)

from _lib.bypass import is_bypassed  # noqa: E402


def evaluate(prompt: str) -> dict[str, bool]:
    return {
        "specific_reference": bool(FILE_LINE_PATTERN.search(prompt)),
        "length_cap": bool(LENGTH_CAP_PATTERN.search(prompt)),
        "output_shape": bool(OUTPUT_SHAPE_PATTERN.search(prompt)),
        "not_meta": META_LEADING_PATTERN.match(prompt) is None,
    }


def failure_messages(checks: dict[str, bool]) -> list[str]:
    msgs: list[str] = []
    if not checks["specific_reference"]:
        msgs.append(
            "missing specific reference: include a file path, file:line, "
            "function name, or error code"
        )
    if not checks["length_cap"]:
        msgs.append(
            "missing response-length cap: add a word/sentence/paragraph budget "
            "(e.g., 'Under 200 words', 'one paragraph')"
        )
    if not checks["output_shape"]:
        msgs.append(
            "missing output shape: name what the agent should produce "
            "(report, list, table, findings, summary, diff)"
        )
    if not checks["not_meta"]:
        msgs.append(
            "leading meta-prompt: ship the actual instruction in the first line, "
            "not 'Can you', 'Help me', or a bare 'Hi'"
        )
    return msgs


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.hook_profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main() -> int:
    if not should_run("subagent-brief-quality"):
        _sys.exit(0)
    if os.environ.get("SUBAGENT_BRIEF_DISABLE") == "1":
        _audit(
            hook="subagent-brief-quality",
            decision="bypass",
            bypass_env="SUBAGENT_BRIEF_DISABLE",
        )
        return 0
    if is_bypassed("subagent-brief-quality"):
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get("tool_name", "")
    if tool not in AGENT_TOOL_NAMES:
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    prompt = tool_input.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip():
        return 0

    checks = evaluate(prompt)
    failures = failure_messages(checks)

    if not failures:
        return 0

    if len(failures) == 1:
        _audit(
            hook="subagent-brief-quality",
            decision="advise",
            tool=tool,
            reason="one heuristic failed",
            command_excerpt=failures[0][:240],
        )
        return 0

    print(
        "Blocked: subagent prompt fails "
        f"{len(failures)} of 4 quality heuristics. "
        'Rule: ~/.claude/rules/smart-questions.md "Briefing Subagents".\n'
        + "\n".join(f"  - {m}" for m in failures)
        + "\n\nFix: rewrite the prompt with scope, file:line refs from prior "
        "investigation, prior attempts with errors, expected output shape, "
        "and a response-length cap. Example: 'Find callers of createUser at "
        "services/userService.ts:42. Report file:line. Under 200 words.'\n"
        "Bypass (rare; only when the prompt format is intentional): "
        "SUBAGENT_BRIEF_DISABLE=1.",
        file=sys.stderr,
    )
    _audit(
        hook="subagent-brief-quality",
        decision="block",
        tool=tool,
        reason="multiple heuristics failed",
        command_excerpt=" | ".join(failures)[:240],
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
