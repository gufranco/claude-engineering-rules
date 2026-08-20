#!/usr/bin/env python3
"""Block a commit that changes rendered output without touching render-level checks.

Rationale lives in rules/frontend-render-gate.md. A diff that alters markup,
styles, or theme tokens cannot be verified by reading it: cascade outcome,
paint order, accessibility tree, focus order, and third-party frames are all
invisible in source and absent from jsdom.

The check is deliberately coarse. It asks whether the commit touches any
render-level check at all, not whether that check is the right one. Judging
adequacy is a review question; the hook only refuses the case where nothing
render-level was touched, which is the case that produced the shipped defects.

Bypass: FRONTEND_RENDER_GATE_DISABLE=1 in a parent shell.
"""

import json
import os
import re
import subprocess
import sys

UI_SUFFIXES = (
    ".tsx",
    ".jsx",
    ".vue",
    ".svelte",
    ".dart",
    ".css",
    ".scss",
    ".sass",
    ".less",
)

THEME_OR_TOKEN_SOURCE = re.compile(
    r"(^|/)(theme|tokens?|palette|design-tokens|typography|colors?)\.[cm]?[jt]s$",
    re.IGNORECASE,
)

RENDER_LEVEL_CHECK = re.compile(
    r"(^|/)(e2e|acceptance|integration_test|playwright|cypress|puppeteer|maestro|patrol)(/|$)"
    r"|\.(e2e|spec)\.[cm]?[jt]sx?$"
    r"|(^|/)[^/]*(accessibility|a11y|axe|visual|screenshot)[^/]*\.[cm]?[jt]sx?$"
    r"|(^|/)[^/]*(accessibility|a11y|golden|integration)[^/]*_test\.dart$"
    r"|(^|/)(playwright|cypress|percy|chromatic|lighthouserc)\.[^/]*$"
    r"|\.flow\.ya?ml$",
    re.IGNORECASE,
)

MOBILE_SUFFIXES = (".dart", ".swift", ".kt")

NOT_A_SHIPPED_SURFACE = re.compile(
    r"(^|/)(node_modules|dist|build|\.next|out|coverage|storybook-static)(/|$)"
    r"|(^|/)__(mocks|fixtures)__(/|$)"
    r"|\.stories\.[cm]?[jt]sx?$"
    r"|\.d\.ts$",
    re.IGNORECASE,
)

GIT_COMMIT_INVOCATION = re.compile(r"\bgit\s+(?:-\S+\s+|--\S+(?:=\S+)?\s+)*commit\b")

MAX_LISTED = 10

WEB_GUIDANCE = (
    "  agent-browser open <url>\n"
    "  agent-browser eval \"document.querySelector('<sel>').focus();\n"
    "    const s = getComputedStyle(document.activeElement);\n"
    '    JSON.stringify({ outline: s.outlineWidth, shadow: s.boxShadow })"\n'
    "  agent-browser snapshot -i\n"
)

MOBILE_GUIDANCE = (
    "  A widget test is the jsdom tier: it proves structure, not paint and not\n"
    "  the platform accessibility tree. The device tier is an integration_test\n"
    "  suite on a simulator or emulator; xcrun simctl and adb are both present.\n"
)

BLOCK_MESSAGE = (
    "BLOCKED: this commit changes rendered output with no render-level check.\n\n"
    "{files}\n\n"
    "Cascade outcome, paint order, the accessibility tree, focus order, and\n"
    "anything inside a third-party frame are invisible in source and absent\n"
    "from a DOM emulation. A class-name assertion restates the diff rather\n"
    "than testing what a visitor perceives.\n\n"
    "{guidance}\n"
    "Extend the browser-driven or simulator suite this project already has,\n"
    "asserting the computed result on the element in question. When the\n"
    "surface is genuinely unreachable, say so explicitly rather than\n"
    "reporting the change as verified.\n\n"
    "Rule: rules/frontend-render-gate.md\n"
    "Bypass for a genuine false positive: export FRONTEND_RENDER_GATE_DISABLE=1"
)


def staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def renders_to_a_screen(path: str) -> bool:
    if NOT_A_SHIPPED_SURFACE.search(path):
        return False
    return path.endswith(UI_SUFFIXES) or bool(THEME_OR_TOKEN_SOURCE.search(path))


def any_render_level_check(paths: list[str]) -> bool:
    return any(RENDER_LEVEL_CHECK.search(path) for path in paths)


def format_file_list(paths: list[str]) -> str:
    listed = "\n".join(f"  {path}" for path in paths[:MAX_LISTED])
    if len(paths) > MAX_LISTED:
        listed += f"\n  ... and {len(paths) - MAX_LISTED} more"
    return listed


def main() -> int:
    if os.environ.get("FRONTEND_RENDER_GATE_DISABLE") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    command = payload.get("tool_input", {}).get("command", "")
    if not GIT_COMMIT_INVOCATION.search(command):
        return 0

    paths = staged_files()
    ui_files = [path for path in paths if renders_to_a_screen(path)]

    if not ui_files or any_render_level_check(paths):
        return 0

    targets_mobile = any(path.endswith(MOBILE_SUFFIXES) for path in ui_files)
    guidance = MOBILE_GUIDANCE if targets_mobile else WEB_GUIDANCE

    print(
        BLOCK_MESSAGE.format(files=format_file_list(ui_files), guidance=guidance),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
