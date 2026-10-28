#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


ADVISORY_MODE = False

IN_SCOPE_PATH_SEGMENTS = (
    "/.claude/rules/",
    "/.claude/standards/",
    "/.claude/checklists/",
    "/.claude/CLAUDE.md",
)

SELF_REFERENCE_FILES = (
    "/.claude/rules/normative-keywords.md",
    "/.claude/rules/writing-precision.md",
    "/.claude/standards/normative-keywords.md",
    "/.claude/standards/writing-precision.md",
)


BULLET_SHOULD_RE = re.compile(
    r"^\s*(?:[-*]|\d+\.)\s+[Ss]hould\s+\S",
    re.MULTILINE,
)


sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.hook_profile import should_run  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_advisory_payload  # noqa: E402
from _lib.edit_resolution import payload_fragments  # noqa: E402


def is_in_scope(path: str) -> bool:
    if not path or not path.lower().endswith(".md"):
        return False
    if any(seg in path for seg in SELF_REFERENCE_FILES):
        return False
    return any(seg in path for seg in IN_SCOPE_PATH_SEGMENTS)


def collect(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    fp = tool_input.get("file_path", "") or ""
    if not is_in_scope(fp):
        return []
    return [(fp, text) for _, text in payload_fragments(tool, tool_input)]


def find_should_bullets(text: str) -> list[str]:
    hits: list[str] = []
    for m in BULLET_SHOULD_RE.finditer(text):
        line_end = text.find("\n", m.start())
        line = text[m.start() : line_end if line_end != -1 else len(text)]
        hits.append(line.strip())
    return hits


def _skip_run() -> bool:
    if not should_run("normative-keyword-discipline"):
        sys.exit(0)
    if os.environ.get("NORMATIVE_KEYWORD_DISABLE") == "1":
        _audit(
            hook="normative-keyword-discipline",
            decision="bypass",
            bypass_env="NORMATIVE_KEYWORD_DISABLE",
        )
        return True
    return is_bypassed("normative-keyword-discipline")


def _findings(items: list[tuple[str, str]]) -> list[str]:
    findings: list[str] = []
    for label, text in items:
        hits = find_should_bullets(text)
        if hits:
            findings.append(f"  - {label}:")
            findings.extend(f"      {h[:120]}" for h in hits[:5])
    return findings


def _report(tool: str, findings: list[str]) -> int:
    severity_label = "Warning" if ADVISORY_MODE else "Blocked"
    message = (
        f"{severity_label}: bullet items starting with 'Should ' detected. "
        'Rules: ~/.claude/standards/writing-precision.md "Eliminate weasel words" '
        "and ~/.claude/rules/normative-keywords.md.\n"
        + "\n".join(findings)
        + "\n\nFix: replace 'Should ' with 'Must ' for required behavior, "
        "or rephrase as optional with 'may'. The full glossary lives in "
        "rules/normative-keywords.md.\n"
        "Silence: set NORMATIVE_KEYWORD_DISABLE=1 in the parent shell."
    )
    print(message, file=sys.stderr)
    _audit(
        hook="normative-keyword-discipline",
        decision="warn" if ADVISORY_MODE else "block",
        tool=tool,
        reason="should bullet",
        command_excerpt=" | ".join(findings)[:240],
    )
    return 0 if ADVISORY_MODE else 2


def main() -> int:
    if _skip_run():
        return 0
    payload = read_advisory_payload("normative-keyword-discipline")
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    items = collect(tool, tool_input)
    if not items:
        return 0
    findings = _findings(items)
    if not findings:
        return 0
    return _report(tool, findings)


if __name__ == "__main__":
    sys.exit(main())
