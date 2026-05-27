#!/usr/bin/env python3
"""
normative-keyword-discipline.py

PreToolUse hook that flags ambiguous normative keywords in rule files,
standards, checklists, and CLAUDE.md.

Rule sources:
  - ~/.claude/rules/normative-keywords.md (BCP 14 glossary, lowercase-primary).
  - ~/.claude/rules/writing-precision.md "Eliminate weasel words".

Coverage:
  - Write/Edit/MultiEdit on Markdown files under ~/.claude/rules/,
    ~/.claude/standards/, ~/.claude/checklists/, or named CLAUDE.md.

Detection (Phase 3, conservative):
  - Bullet items starting with "Should " or "should " in a position the
    weasel-words rule already calls a violation.

Severity:
  - Advisory (exit 0). Prints a warning to stderr; does not block the write.
  - Promoted to blocking (exit 2) in a later phase after the rules/ retrofit
    lands, by flipping ADVISORY_MODE.

Bypass:
  NORMATIVE_KEYWORD_DISABLE=1 (per-shell export, not inline).
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


ADVISORY_MODE = False

IN_SCOPE_PATH_SEGMENTS = (
    "/.claude/rules/",
    "/.claude/standards/",
    "/.claude/checklists/",
    "/.claude/CLAUDE.md",
)

# Files inside the rule that DEFINES this convention will naturally contain
# "Should " inside example blocks. Skip them entirely.
SELF_REFERENCE_FILES = (
    "/.claude/rules/normative-keywords.md",
    "/.claude/rules/writing-precision.md",
)


# Detects bullet items starting with "Should " or "should ".
# Matches lines like:
#   - Should validate input.
#   * should always run tests.
#   1. Should pick a clear approach.
BULLET_SHOULD_RE = re.compile(
    r"^\s*(?:[-*]|\d+\.)\s+[Ss]hould\s+\S",
    re.MULTILINE,
)


sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.profile import should_run  # type: ignore  # noqa: E402
except ImportError:  # pragma: no cover

    def should_run(_id: str) -> bool:  # type: ignore
        return True


def is_in_scope(path: str) -> bool:
    if not path or not path.lower().endswith(".md"):
        return False
    if any(seg in path for seg in SELF_REFERENCE_FILES):
        return False
    return any(seg in path for seg in IN_SCOPE_PATH_SEGMENTS)


def collect(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    fp = tool_input.get("file_path", "") or ""
    if not is_in_scope(fp):
        return out
    if tool == "Write":
        c = tool_input.get("content", "")
        if isinstance(c, str):
            out.append((fp, c))
    elif tool == "Edit":
        c = tool_input.get("new_string", "")
        if isinstance(c, str):
            out.append((fp, c))
    elif tool == "MultiEdit":
        for i, edit in enumerate(tool_input.get("edits", []) or []):
            if isinstance(edit, dict):
                c = edit.get("new_string", "")
                if isinstance(c, str):
                    out.append((f"{fp} [{i}]", c))
    return out


def find_should_bullets(text: str) -> list[str]:
    hits: list[str] = []
    for m in BULLET_SHOULD_RE.finditer(text):
        line_end = text.find("\n", m.start())
        line = text[m.start():line_end if line_end != -1 else len(text)]
        hits.append(line.strip())
    return hits


def main() -> int:
    if not should_run("normative-keyword-discipline"):
        sys.exit(0)
    if os.environ.get("NORMATIVE_KEYWORD_DISABLE") == "1":
        _audit(
            hook="normative-keyword-discipline",
            decision="bypass",
            bypass_env="NORMATIVE_KEYWORD_DISABLE",
        )
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:  # pragma: no cover
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    items = collect(tool, tool_input)
    if not items:
        return 0

    findings: list[str] = []
    for label, text in items:
        hits = find_should_bullets(text)
        if hits:
            findings.append(f"  - {label}:")
            findings.extend(f"      {h[:120]}" for h in hits[:5])

    if not findings:
        return 0

    severity_label = "Warning" if ADVISORY_MODE else "Blocked"
    message = (
        f"{severity_label}: bullet items starting with 'Should ' detected. "
        'Rules: ~/.claude/rules/writing-precision.md "Eliminate weasel words" '
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


if __name__ == "__main__":
    sys.exit(main())
