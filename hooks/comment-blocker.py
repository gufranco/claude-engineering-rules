#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from fnmatch import fnmatch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.comment_syntax import (  # noqa: E402
    added_comment_lines,
    document_view,
    is_test_path,
)
from _lib.edit_resolution import payload_fragments, resolved_change  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402
from _lib.staged_blobs import (  # noqa: E402
    StagedScanError,
    commit_request,
    staged_documents,
)

from _lib.audit_log import record as _audit  # noqa: E402


HOOK = "comment-blocker"
BYPASS_ENV = "COMMENT_BLOCKER_DISABLE"
SNIPPET_LIMIT = 60
WAIVED_PATHS = (
    "*src/example-project/asm/*.asm",
    "*example-emulator/asm/*.asm",
)
EDIT_LABEL = "line numbers in the file this edit produces"
STAGED_LABEL = "staged for commit, line numbers in the staged file"
FIX_GUIDANCE = (
    "\n\nThere is no per-comment suppression. Fix the code instead:\n"
    "  1. Delete the comment. If code felt like it needed explaining, that is\n"
    "     the signal to improve the code: rename the symbol, extract a\n"
    "     well-named function, or split the expression until it reads clearly.\n"
    "  2. Docstrings and doc comments are comments: a Python docstring,\n"
    "     `/** ... */`, `///`, `//!`, `{-| -}`, `@doc`, POD. Delete them and\n"
    "     express a public-API contract in names and types.\n"
    "  3. A test carries exactly three comments, one bare marker opening each\n"
    "     block in order: `# Arrange`, `# Act`, `# Assert` in the file's own\n"
    "     comment syntax (`// Act`, `-- Assert`), alone on the line, nothing\n"
    "     after the word. Any other comment in a test file is blocked.\n"
    "  4. Tool directives are the one exempt class and are already allowed:\n"
    "     `// eslint-disable-next-line`, `// @ts-expect-error`, `//go:build`,\n"
    "     `# noqa`, `# type: ignore`, `# shellcheck disable=SC2086`. If a real\n"
    "     directive was flagged, it is missing from the allowlist in\n"
    "     ~/.claude/hooks/_lib/tool_directive.py.\n"
    "  5. Files written through Bash are checked when they are committed. Fix\n"
    "     the staged file, `git add` it again, and rerun the commit."
)


def format_hits(pairs: list[tuple[int, str]]) -> list[str]:
    return [
        f"L{index + 1}: {line if len(line) <= SNIPPET_LIMIT else line[:57] + '...'}"
        for index, line in pairs
    ]


def change_findings(path: str, before: str, after: str, label: str) -> list[str]:
    if any(fnmatch(path, pattern) for pattern in WAIVED_PATHS):
        return []
    after_view = document_view(path, after)
    if after_view is None:
        return []
    before_view = document_view(path, before)
    before_text = before_view.text if before_view else ""
    pairs = added_comment_lines(
        before_text, after_view.text, after_view.family, is_test_path(path)
    )
    if not pairs:
        return []
    return [f"  - {path} ({label}):\n      " + "\n      ".join(format_hits(pairs))]


def edit_findings(tool: str, tool_input: Mapping[str, object]) -> list[str]:
    change = resolved_change(tool, tool_input)
    if change is not None:
        return change_findings(change.path, change.before, change.after, EDIT_LABEL)
    path = str(tool_input.get("file_path") or "")
    return [
        finding
        for field, text in payload_fragments(tool, tool_input)
        for finding in change_findings(path, "", text, field)
    ]


def commit_findings(tool_input: Mapping[str, object], cwd: str) -> list[str]:
    command = tool_input.get("command")
    if not isinstance(command, str):
        return []
    request = commit_request(command, cwd)
    if request is None:
        return []
    return [
        finding
        for document in staged_documents(request)
        for finding in change_findings(
            document.path, document.before, document.after, STAGED_LABEL
        )
    ]


def findings_for(payload: Mapping[str, object]) -> list[str]:
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, Mapping):
        return []
    if tool == "Bash":
        return commit_findings(tool_input, str(payload.get("cwd") or os.getcwd()))
    return edit_findings(tool, tool_input)


def report(tool: str, findings: list[str]) -> int:
    print(
        "Blocked: comment added to source code. "
        'Rule: ~/.claude/rules/code-style.md "Comments" '
        "(code must be self-explanatory; comments, docstrings, and doc comments "
        "are not permitted).\n" + "\n".join(findings) + FIX_GUIDANCE,
        file=sys.stderr,
    )
    _audit(
        hook=HOOK,
        decision="block",
        tool=tool,
        reason="comment added to source",
        command_excerpt=" | ".join(findings)[:240],
    )
    return 2


def report_scan_failure(error: StagedScanError) -> int:
    print(
        f"Blocked: {HOOK} could not read the staged files, so the commit was not "
        f"checked for added comments.\n  {error}\n"
        "Fix the repository state and retry. Bypass for one commit with "
        f"{BYPASS_ENV}=1 in the parent shell.",
        file=sys.stderr,
    )
    return 2


def read_payload() -> dict[str, object] | None:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def unreadable_input() -> int:
    print(
        f"Blocked: {HOOK} could not read its input: stdin is not a UTF-8 JSON "
        f"object, so the change was not checked. Bypass once with {BYPASS_ENV}=1 "
        "in the parent shell.",
        file=sys.stderr,
    )
    _audit(hook=HOOK, decision="block", reason="unreadable hook input")
    return 2


def main() -> int:
    if not should_run(HOOK):
        return 0
    if os.environ.get(BYPASS_ENV) == "1":
        _audit(hook=HOOK, decision="bypass", bypass_env=BYPASS_ENV)
        return 0
    if is_bypassed(HOOK):
        return 0
    payload = read_payload()
    if payload is None:
        return unreadable_input()
    try:
        findings = findings_for(payload)
    except StagedScanError as error:
        return report_scan_failure(error)
    if not findings:
        return 0
    return report(str(payload.get("tool_name") or ""), findings)


if __name__ == "__main__":
    sys.exit(main())
