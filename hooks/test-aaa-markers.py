#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.aaa_structure import violations  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.edit_resolution import resolved_change  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402
from _lib.output import block  # noqa: E402
from _lib.staged_blobs import (  # noqa: E402
    StagedScanError,
    commit_request,
    staged_documents,
)

from _lib.audit_log import record as _audit  # noqa: E402


HOOK = "test-aaa-markers"
BYPASS_ENV = "TEST_AAA_MARKERS_DISABLE"
RULE_ANCHOR = "standards/testing.md (Test Structure)"
WHY = (
    "Every test reads the same way: three blocks, each opened by its bare marker, "
    "so a reviewer finds the setup, the one call, and the checks without reading "
    "the whole body. Unmarked tests drift into interleaved setup and assertions."
)
FIX = (
    "Give each listed test exactly three blocks, in order, separated by one blank line:\n"
    "  # Arrange      setup only\n"
    "  # Act          the single call under test, bound to a name when it returns one\n"
    "  # Assert       the checks\n"
    "Use the file's comment syntax (`// Act` in JS, TS and Go), alone on the line,\n"
    "nothing after the word. An expected throw binds the call inside Act\n"
    "(`with pytest.raises(...) as raised:` or `const call = () => f()`) and\n"
    "asserts on it in Assert. Legacy tests the change does not touch are not checked."
)
BYPASS_WHEN = (
    "The flagged function is not a test, or the language construct cannot hold "
    "line comments."
)


def change_violations(path: str, before: str, after: str) -> list[str]:
    return [
        f"{path}: {violation.name} (line {violation.line}): {violation.reason}"
        for violation in violations(path, before, after)
    ]


def edit_violations(tool: str, tool_input: Mapping[str, object]) -> list[str]:
    change = resolved_change(tool, tool_input)
    if change is None:
        return []
    return change_violations(change.path, change.before, change.after)


def commit_violations(tool_input: Mapping[str, object], cwd: str) -> list[str]:
    command = tool_input.get("command")
    if not isinstance(command, str):
        return []
    request = commit_request(command, cwd)
    if request is None:
        return []
    return [
        line
        for document in staged_documents(request)
        for line in change_violations(document.path, document.before, document.after)
    ]


def violations_for(payload: Mapping[str, object]) -> list[str]:
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, Mapping):
        return []
    if tool == "Bash":
        return commit_violations(tool_input, str(payload.get("cwd") or os.getcwd()))
    return edit_violations(tool, tool_input)


def emit(detected: str, decision: str) -> int:
    print(
        block(
            hook=HOOK,
            rule_anchor=RULE_ANCHOR,
            detected=detected,
            why=WHY,
            fix=FIX,
            bypass_when=BYPASS_WHEN,
            decision=decision,
            env_var=BYPASS_ENV,
        ),
        file=sys.stderr,
    )
    _audit(hook=HOOK, decision="block", reason=detected[:240])
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
        found = violations_for(payload)
    except StagedScanError as error:
        return emit(f"{HOOK} could not read the staged files: {error}", "STOP-AND-ASK")
    if not found:
        return 0
    return emit("\n".join(found), "FIX-AND-RETRY")


if __name__ == "__main__":
    sys.exit(main())
