#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

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

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.suppression import is_suppressed  # noqa: E402


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


MAX_TAG_LENGTH = 4000
EXPRESSION = re.compile(r"\{[^{}]*\}")
TAG_START = re.compile(r"<([A-Za-z][\w.-]*)\b")
ICON_CHILD = re.compile(r"<(?:svg\b|Icon\b|[A-Z]\w*Icon\b)")
INTERACTIVE_ROLES = ("button", "link", "checkbox", "switch", "tab")
NON_INTERACTIVE = ("div", "span", "p", "li", "td", "tr")
KEY_HANDLERS = (
    "onKeyDown",
    "onKeyUp",
    "onKeyPress",
    "onkeydown",
    "onkeyup",
    "onkeypress",
)


@dataclass(frozen=True, slots=True)
class Tag:
    name: str
    attrs: str
    start: int
    end: int


def _tag_end(text: str, index: int) -> int:
    depth, quote = 0, ""
    for position in range(index, min(len(text), index + MAX_TAG_LENGTH)):
        char = text[position]
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'`":
            quote = char
        elif char in "{}":
            depth = depth + 1 if char == "{" else max(0, depth - 1)
        elif char == ">" and depth == 0:
            return position
    return -1


def _flatten(attrs: str) -> str:
    for _ in range(10):
        flattened = EXPRESSION.sub("{}", attrs)
        if flattened == attrs:
            return attrs
        attrs = flattened
    return attrs


def tags(content: str) -> list[Tag]:
    found: list[Tag] = []
    for match in TAG_START.finditer(content):
        end = _tag_end(content, match.end())
        if end >= 0:
            attrs = _flatten(content[match.end() : end])
            found = [*found, Tag(match.group(1), attrs, match.start(), end + 1)]
    return found


def is_element(tag: Tag, *names: str) -> bool:
    return tag.name in names or (tag.name.isupper() and tag.name.lower() in names)


def has_attr(tag: Tag, *names: str) -> bool:
    return any(re.search(rf"(?:^|\s){re.escape(n)}\s*=", tag.attrs) for n in names)


def attr_value(tag: Tag, name: str) -> str:
    match = re.search(
        rf"(?:^|\s){name}\s*=\s*[\"']([^\"']*)[\"']", tag.attrs, re.IGNORECASE
    )
    return match.group(1).lower() if match else ""


def _line(content: str, tag: Tag) -> int:
    return content[: tag.start].count("\n") + 1


def _tag_findings(content: str, tag: Tag) -> list[tuple[int, str]]:
    line = _line(content, tag)
    checks = (
        (
            is_element(tag, "img") and not has_attr(tag, "alt"),
            "AMC001: <img> without alt attribute (WCAG 1.1.1 A)",
        ),
        (
            is_element(tag, "input")
            and attr_value(tag, "type") != "hidden"
            and not has_attr(tag, "aria-label", "aria-labelledby", "id"),
            "AMC002: <input> without label, aria-label, aria-labelledby, or id for label-for (WCAG 3.3.2 A)",
        ),
        (
            is_element(tag, "div", "span")
            and attr_value(tag, "role") in INTERACTIVE_ROLES
            and not has_attr(tag, *KEY_HANDLERS),
            f'AMC003: role="{attr_value(tag, "role")}" on <{tag.name}> without keyboard handler (WCAG 2.1.1 A). Use a semantic element instead',
        ),
        (
            is_element(tag, "html") and not has_attr(tag, "lang"),
            "AMC005: <html> without lang attribute (WCAG 3.1.1 A)",
        ),
        (
            is_element(tag, "a") and not has_attr(tag, "href"),
            "AMC006: <a> without href attribute. Use <button> or add href",
        ),
        (
            is_element(tag, *NON_INTERACTIVE)
            and has_attr(tag, "onClick", "onclick")
            and not has_attr(tag, "role"),
            f"AMC007: onClick on <{tag.name}> without role+tabIndex+onKeyDown (WCAG 2.1.1 A). Use <button>",
        ),
        (
            is_element(tag, "input")
            and attr_value(tag, "type") == "password"
            and not has_attr(tag, "autocomplete", "autoComplete"),
            'AMC008: <input type="password"> without autocomplete attribute (current-password or new-password)',
        ),
    )
    return [(line, message) for failed, message in checks if failed]


def check_icon_only_button(content: str, tag: Tag) -> list[tuple[int, str]]:
    if not is_element(tag, "button") or has_attr(
        tag, "aria-label", "aria-labelledby", "title"
    ):
        return []
    close = content.find("</button>", tag.end)
    if close < 0:
        return []
    inner = content[tag.end : close]
    text = re.sub(r"<[^>]*>", "", EXPRESSION.sub("", inner)).strip()
    if text or not ICON_CHILD.search(inner):
        return []
    return [
        (
            _line(content, tag),
            "AMC009: icon-only <button> without aria-label (WCAG 4.1.2 A)",
        )
    ]


def check_tabindex_positive(content: str) -> list[tuple[int, str]]:
    pat = re.compile(r"\btabIndex\s*=\s*\{?\s*([1-9]\d*)", re.IGNORECASE)
    return [
        (
            content[: m.start()].count("\n") + 1,
            f"AMC004: tabIndex={m.group(1)} breaks logical tab order. Use 0 or -1",
        )
        for m in pat.finditer(content)
    ]


SUPPRESSING_RULES = {
    "AMC001": frozenset({"jsx-a11y/alt-text"}),
    "AMC002": frozenset(
        {
            "jsx-a11y/label-has-associated-control",
            "jsx-a11y/control-has-associated-label",
        }
    ),
    "AMC003": frozenset(
        {"jsx-a11y/interactive-supports-focus", "jsx-a11y/click-events-have-key-events"}
    ),
    "AMC004": frozenset({"jsx-a11y/tabindex-no-positive"}),
    "AMC005": frozenset({"jsx-a11y/html-has-lang"}),
    "AMC006": frozenset({"jsx-a11y/anchor-is-valid"}),
    "AMC007": frozenset(
        {
            "jsx-a11y/no-static-element-interactions",
            "jsx-a11y/click-events-have-key-events",
        }
    ),
    "AMC008": frozenset({"jsx-a11y/autocomplete-valid"}),
    "AMC009": frozenset({"jsx-a11y/control-has-associated-label"}),
}


def find_all(content: str) -> list[tuple[int, str]]:
    found = [
        finding
        for tag in tags(content)
        for finding in (
            *_tag_findings(content, tag),
            *check_icon_only_button(content, tag),
        )
    ]
    lines = content.splitlines()
    return [
        (line, message)
        for line, message in [*found, *check_tabindex_positive(content)]
        if not is_suppressed(lines, line - 1, rules=SUPPRESSING_RULES[message[:6]])
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
    if is_bypassed("accessibility-mechanical-checks"):
        return 0
    payload = read_hook_payload("accessibility-mechanical-checks")

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        return 0

    path, content = extract_content(tool_name, tool_input)
    if not path or not content:
        return 0
    if is_skipped(path):
        return 0

    all_findings = find_all(content)

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
        "Fix the patterns above, or suppress one line with an eslint-disable-next-line directive naming the matching jsx-a11y rule. Bypass: ACCESSIBILITY_CHECKS_DISABLE=1 in the parent shell.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
