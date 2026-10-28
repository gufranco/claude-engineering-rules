#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


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
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.edit_resolution import payload_fragments  # noqa: E402


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
    text = "\n".join(part for _, part in payload_fragments(tool_name, tool_input))
    return tool_input.get("file_path", ""), text


def _changed_content(payload: dict) -> tuple[str, str, str]:
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        return tool_name, "", ""
    path, content = extract_content(tool_name, tool_input)
    return tool_name, path, content


def _report(tool_name: str, path: str, findings: list[tuple[int, str]]) -> int:
    all_findings = sorted(findings, key=lambda f: f[0])
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


def main() -> int:
    if os.environ.get("AI_DISCLOSURE_DISABLE") == "1":
        return 0
    if is_bypassed("ai-disclosure-checks"):
        return 0
    payload = read_hook_payload("ai-disclosure-checks")

    tool_name, path, content = _changed_content(payload)
    if not path or not content:
        return 0
    if is_skipped(path):
        return 0

    all_findings = [finding for check in CHECKS for finding in check(content)]

    if not all_findings:
        return 0
    return _report(tool_name, path, all_findings)


if __name__ == "__main__":
    sys.exit(main())
