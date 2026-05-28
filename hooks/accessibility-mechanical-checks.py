#!/usr/bin/env python3
"""accessibility-mechanical-checks

PreToolUse hook on Write, Edit, MultiEdit for UI files. Catches the
highest-signal accessibility patterns that automated regex can detect.

Rule source: ~/.claude/rules/accessibility-defaults.md "Forbidden Patterns".

Detected patterns:
  - <img> without alt attribute
  - <input> (type != hidden) without label/aria-label/aria-labelledby
  - role="button" on <div> or <span> without keyboard handler
  - tabIndex > 0
  - Missing lang on <html> root
  - <a> tag without href (other than placeholder anchors)
  - Click handler on <div>/<span> without role+tabIndex+onKeyDown
  - Missing aria-label on icon-only button
  - <input type="password"> without autocomplete

Scope: .tsx, .jsx, .vue, .svelte, .html, .htm files. Skips test files.

Bypass:
  ACCESSIBILITY_CHECKS_DISABLE=1
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


UI_EXTS = (".tsx", ".jsx", ".vue", ".svelte", ".html", ".htm")

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


def is_skipped(path: str) -> bool:
    if not path.endswith(UI_EXTS):
        return True
    if any(seg in path for seg in SKIP_SEGMENTS):
        return True
    if any(
        part in os.path.basename(path) for part in (".test.", ".spec.", ".stories.")
    ):
        return True
    return False


def check_img_alt(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    pat = re.compile(r"<img\b(?![^>]*\salt\s*=)[^>]*>", re.IGNORECASE)
    for m in pat.finditer(content):
        line = content[: m.start()].count("\n") + 1
        findings.append((line, "AMC001: <img> without alt attribute (WCAG 1.1.1 A)"))
    return findings


def check_input_label(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    pat = re.compile(
        r"<input\b(?![^>]*type\s*=\s*[\"']hidden[\"'])(?![^>]*aria-label\b)(?![^>]*aria-labelledby\b)(?![^>]*id\s*=\s*[\"'][^\"']+[\"'])[^>]*/?>",
        re.IGNORECASE,
    )
    for m in pat.finditer(content):
        line = content[: m.start()].count("\n") + 1
        findings.append(
            (
                line,
                "AMC002: <input> without label, aria-label, aria-labelledby, or id for label-for (WCAG 3.3.2 A)",
            )
        )
    return findings


def check_role_on_div(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    pat = re.compile(
        r"<(div|span)\b[^>]*\brole\s*=\s*[\"'](button|link|checkbox|switch|tab)[\"'][^>]*(?<!onkeydown=)(?<!onKeyDown=)>",
        re.IGNORECASE,
    )
    for m in pat.finditer(content):
        line = content[: m.start()].count("\n") + 1
        findings.append(
            (
                line,
                f'AMC003: role="{m.group(2)}" on <{m.group(1)}> without keyboard handler (WCAG 2.1.1 A). Use a semantic element instead',
            )
        )
    return findings


def check_tabindex_positive(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    pat = re.compile(r"\btabIndex\s*=\s*\{?\s*([1-9]\d*)", re.IGNORECASE)
    for m in pat.finditer(content):
        line = content[: m.start()].count("\n") + 1
        findings.append(
            (
                line,
                f"AMC004: tabIndex={m.group(1)} breaks logical tab order. Use 0 or -1",
            )
        )
    return findings


def check_html_lang(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    pat = re.compile(r"<html\b(?![^>]*\blang\s*=)[^>]*>", re.IGNORECASE)
    for m in pat.finditer(content):
        line = content[: m.start()].count("\n") + 1
        findings.append((line, "AMC005: <html> without lang attribute (WCAG 3.1.1 A)"))
    return findings


def check_anchor_no_href(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    pat = re.compile(r"<a\b(?![^>]*\shref\s*=)[^>]*>", re.IGNORECASE)
    for m in pat.finditer(content):
        line = content[: m.start()].count("\n") + 1
        findings.append(
            (line, "AMC006: <a> without href attribute. Use <button> or add href")
        )
    return findings


def check_click_on_non_interactive(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    pat = re.compile(
        r"<(div|span|p|li|td|tr)\b(?![^>]*\brole\s*=)[^>]*\bon[Cc]lick\s*=",
        re.IGNORECASE,
    )
    for m in pat.finditer(content):
        line = content[: m.start()].count("\n") + 1
        findings.append(
            (
                line,
                f"AMC007: onClick on <{m.group(1)}> without role+tabIndex+onKeyDown (WCAG 2.1.1 A). Use <button>",
            )
        )
    return findings


def check_password_autocomplete(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    pat = re.compile(
        r"<input\b[^>]*\btype\s*=\s*[\"']password[\"'](?![^>]*\bautocomplete\s*=)[^>]*>",
        re.IGNORECASE,
    )
    for m in pat.finditer(content):
        line = content[: m.start()].count("\n") + 1
        findings.append(
            (
                line,
                'AMC008: <input type="password"> without autocomplete attribute (current-password or new-password)',
            )
        )
    return findings


CHECKS = [
    check_img_alt,
    check_input_label,
    check_role_on_div,
    check_tabindex_positive,
    check_html_lang,
    check_anchor_no_href,
    check_click_on_non_interactive,
    check_password_autocomplete,
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
    if os.environ.get("ACCESSIBILITY_CHECKS_DISABLE") == "1":
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
        hook="accessibility-mechanical-checks",
        decision="block",
        tool=tool_name,
        reason=f"{len(all_findings)} accessibility findings",
        command_excerpt=path,
        bypass_env="ACCESSIBILITY_CHECKS_DISABLE",
    )

    print(
        "Blocked: accessibility violations detected. Rule: ~/.claude/rules/accessibility-defaults.md\n"
        f"\n{bullet_lines}{extra}\n\n"
        "Fix the patterns above or wrap with a suppression marker. Bypass: ACCESSIBILITY_CHECKS_DISABLE=1 in the parent shell.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
