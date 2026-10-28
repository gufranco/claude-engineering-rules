#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


EM_DASH = "\u2014"
EN_DASH = chr(0x2013)

MARKDOWN_SUFFIXES = (".md", ".mdx", ".markdown")
SPACED_HYPHEN_RE = re.compile(r"\b[A-Za-z]{2,}[.,)]? - [A-Za-z(]")
LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
FENCE_PREFIXES = ("```", "~~~")

BOX_DRAWING_RE = re.compile(r"[\u2500-\u257F]")

EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001faff"
    "\U00002600-\U000027bf"
    "\U0001f1e6-\U0001f1ff"
    "\U0000fe0f"
    "\U0000200d"
    "]"
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


def _snippet(text: str, idx: int) -> str:
    start = max(0, idx - 40)
    end = min(len(text), idx + 41)
    return text[start:end].replace("\n", "\u23ce")


def find_violations(text: str) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []

    if EM_DASH in text:
        idx = text.index(EM_DASH)
        findings.append(("em dash (U+2014)", _snippet(text, idx)))

    if EN_DASH in text:
        idx = text.index(EN_DASH)
        findings.append(("en dash (U+2013)", _snippet(text, idx)))

    box_match = BOX_DRAWING_RE.search(text)
    if box_match:
        findings.append(("box-drawing character", _snippet(text, box_match.start())))

    emoji_match = EMOJI_RE.search(text)
    if emoji_match:
        findings.append(
            ("emoji / decorative unicode", _snippet(text, emoji_match.start()))
        )

    return findings


def _prose_lines(text: str) -> list[str]:
    in_fence = False
    prose = []
    for line in text.splitlines():
        if line.lstrip().startswith(FENCE_PREFIXES):
            in_fence = not in_fence
            continue
        body = LIST_MARKER_RE.sub("", INLINE_CODE_RE.sub("", line))
        if not in_fence and not body.lstrip().startswith("|"):
            prose = [*prose, body]
    return prose


def find_markdown_violations(text: str) -> list[tuple[str, str]]:
    hits = [line for line in _prose_lines(text) if SPACED_HYPHEN_RE.search(line)]
    if not hits:
        return []
    return [("spaced hyphen used as a dash", hits[0].strip()[:81])]


def is_markdown_path(path: str) -> bool:
    return path.lower().endswith(MARKDOWN_SUFFIXES)


SKIPPED_TEST_SEGMENTS = (
    "/tests/",
    "/test/",
    "/__tests__/",
    ".test.",
    ".spec.",
)


def is_skipped_path(path: str) -> bool:
    if not path:
        return False
    p = path.lower()
    return any(seg in p for seg in SKIPPED_TEST_SEGMENTS)


def collect_texts(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    fp = tool_input.get("file_path", "") or ""
    if tool in ("Write", "Edit", "MultiEdit") and is_skipped_path(fp):
        return out
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


from _lib.hook_profile import should_run  # noqa: E402


BLOCK_FIX = (
    "\n\nFix:\n"
    "  - Replace em dashes and en dashes with a period, comma, colon, or rewrite.\n"
    "  - In Markdown prose, a spaced hyphen standing in for a dash gets the same fix;\n"
    "    swapping one dash for another is the same violation.\n"
    "  - Remove emojis and decorative unicode.\n"
    "  - Use Mermaid in fenced code blocks instead of box-drawing diagrams.\n"
    "\nBypass (one-off, when explicitly preserving existing content): "
    "set BANNED_PROSE_CHARS_DISABLE=1 in the environment."
)


def _skipped() -> bool:
    if os.environ.get("BANNED_PROSE_CHARS_DISABLE") == "1":
        _audit(
            hook="banned-prose-chars",
            decision="bypass",
            bypass_env="BANNED_PROSE_CHARS_DISABLE",
        )
        return True
    return is_bypassed("banned-prose-chars")


def _findings(texts: list[tuple[str, str]], markdown: bool = False) -> list[str]:
    checks = (
        (find_violations, find_markdown_violations) if markdown else (find_violations,)
    )
    return [
        f"  - {kind} in {field}: ...{snippet}..."
        for field, text in texts
        for check in checks
        for kind, snippet in check(text)
    ]


def _block(tool: str, all_findings: list[str]) -> int:
    print(
        "Blocked: payload contains characters banned by "
        '~/.claude/standards/tone-and-writing.md "Writing Style".\n'
        + "\n".join(all_findings)
        + BLOCK_FIX,
        file=sys.stderr,
    )
    _audit(
        hook="banned-prose-chars",
        decision="block",
        tool=tool,
        reason="banned prose character",
        command_excerpt=" | ".join(all_findings)[:240] if all_findings else None,
    )
    return 2


def main() -> int:
    if not should_run("banned-prose-chars"):
        sys.exit(0)
    if _skipped():
        return 0

    payload = read_hook_payload("banned-prose-chars")

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    markdown = tool in ("Write", "Edit", "MultiEdit") and is_markdown_path(
        str(tool_input.get("file_path", "") or "")
    )
    all_findings = _findings(collect_texts(tool, tool_input), markdown)
    if not all_findings:
        return 0
    return _block(tool, all_findings)


if __name__ == "__main__":
    sys.exit(main())
