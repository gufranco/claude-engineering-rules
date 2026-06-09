#!/usr/bin/env python3
"""ai-disclosure-checks

PreToolUse hook on Write, Edit, MultiEdit. Catches AI-generated content
rendered without a disclosure label.

Rule source: ~/.claude/rules/ai-compliance-defaults.md and
~/.claude/standards/ai-compliance.md "AI Disclosure Tag Pattern".

Detected patterns:
  - JSX expression rendering a variable named like aiResponse, llmOutput,
    generated*, completion, modelOutput, etc. without a nearby disclosure
    label
  - Chatbot UI component instantiated without nearby "AI" / "powered by AI"
    text

Scope: .tsx, .jsx, .vue, .svelte files.

Bypass:
  AI_DISCLOSURE_DISABLE=1
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


SCAN_EXTS = (".tsx", ".jsx", ".vue", ".svelte")

SKIP_SEGMENTS = (
    "/__tests__/",
    "/__test__/",
    "/tests/",
    "/test/",
    "/.claude/hooks/",
    "/.claude/specs/",
    "/node_modules/",
    "/dist/",
    "/build/",
    "/.next/",
)

from _lib.bypass import is_bypassed  # noqa: E402



def is_skipped(path: str) -> bool:
    if not path.endswith(SCAN_EXTS):
        return True
    if any(seg in path for seg in SKIP_SEGMENTS):
        return True
    if any(
        part in os.path.basename(path) for part in (".test.", ".spec.", ".stories.")
    ):
        return True
    return False


AI_VARIABLE_PAT = re.compile(
    r"\{\s*(?:[a-zA-Z_$][\w$]*\.)?(aiResponse|aiAnswer|llmOutput|llmResponse|modelOutput|modelResponse|generated[A-Z]\w*|completion|chatResponse|assistantMessage)\b[^}]*\}",
    re.IGNORECASE,
)

DISCLOSURE_PAT = re.compile(
    r"\b(?:AI(?:-generated|\s+generated)?|generated\s+by\s+AI|powered\s+by\s+AI|aria-label\s*=\s*['\"]\s*(?:AI|generated)|AiDisclosure|AIBadge|AILabel|model[- ]generated)\b",
    re.IGNORECASE,
)

CHATBOT_COMPONENT_PAT = re.compile(
    r"<(?:[A-Z]\w*)?(?:Chat|Chatbot|ChatBot|AiChat|LlmChat)\b",
    re.IGNORECASE,
)


def find_undisclosed_ai_output(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for m in AI_VARIABLE_PAT.finditer(content):
        line_num = content[: m.start()].count("\n") + 1
        # Look in surrounding 500 chars for a disclosure tag
        start_lookback = max(0, m.start() - 500)
        end_lookahead = min(len(content), m.end() + 500)
        surrounding = content[start_lookback:end_lookahead]
        if not DISCLOSURE_PAT.search(surrounding):
            findings.append(
                (
                    line_num,
                    "AIC001: AI-produced variable rendered without a visible disclosure label (EU AI Act Art. 52 + California SB 942). Wrap with an AI badge or disclosure text",
                )
            )
    return findings


def find_chatbot_without_label(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for m in CHATBOT_COMPONENT_PAT.finditer(content):
        line_num = content[: m.start()].count("\n") + 1
        start_lookback = max(0, m.start() - 800)
        end_lookahead = min(len(content), m.end() + 800)
        surrounding = content[start_lookback:end_lookahead]
        if not DISCLOSURE_PAT.search(surrounding):
            findings.append(
                (
                    line_num,
                    "AIC002: chatbot component without 'AI' or 'powered by AI' label nearby (EU AI Act Art. 52). Add a self-identification label",
                )
            )
    return findings


CHECKS = [
    find_undisclosed_ai_output,
    find_chatbot_without_label,
]


def extract_content(tool_name: str, tool_input: dict) -> tuple[str, str]:
    if tool_name == "Write":
        return tool_input.get("file_path", ""), tool_input.get("content", "")
    if tool_name == "Edit":
        return tool_input.get("file_path", ""), tool_input.get("new_string", "")
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits", [])
        return tool_input.get("file_path", ""), "\n".join(
            e.get("new_string", "") for e in edits if isinstance(e, dict)
        )
    return "", ""


def main() -> int:
    if os.environ.get("AI_DISCLOSURE_DISABLE") == "1":
        return 0
    if is_bypassed("ai-disclosure-checks"):
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        return 0

    path, content = extract_content(tool_name, tool_input)
    if not path or not content:
        return 0
    if is_skipped(path):
        return 0

    all_findings: list[tuple[int, str]] = []
    for check in CHECKS:
        all_findings.extend(check(content))

    if not all_findings:
        return 0

    all_findings.sort(key=lambda f: f[0])
    bullet_lines = "\n".join(f"  - line {ln}: {msg}" for ln, msg in all_findings[:10])
    extra = "" if len(all_findings) <= 10 else f"\n  ... {len(all_findings) - 10} more"

    _audit(
        hook="ai-disclosure-checks",
        decision="block",
        tool=tool_name,
        reason=f"{len(all_findings)} AI disclosure findings",
        command_excerpt=path,
        bypass_env="AI_DISCLOSURE_DISABLE",
    )

    print(
        "Blocked: AI disclosure pattern violations. Rule: ~/.claude/rules/ai-compliance-defaults.md\n"
        f"\n{bullet_lines}{extra}\n\n"
        "Add a visible AI disclosure label near every model-produced output and self-identification on every chatbot UI. "
        "Bypass: AI_DISCLOSURE_DISABLE=1 in the parent shell.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
