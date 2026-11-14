#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.audit_log import record as _audit  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload, tool_input_of  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402
from _lib.machine_identity import discover, probe  # noqa: E402
from _lib.machine_leak import Finding, Line, added_lines, scan_lines  # noqa: E402
from _lib.machine_leak_sources import added_in_command, command_text_lines  # noqa: E402
from _lib.output import block  # noqa: E402
from _lib.staged_blobs import (  # noqa: E402
    StagedScanError,
    commit_request,
    staged_documents,
)

HOOK = "machine-leak-guard"
BYPASS_ENV = "MACHINE_LEAK_DISABLE"
RULE_ANCHOR = "rules/machine-agnostic.md"
WHY = (
    "Committed and published text must read the same on any machine. A home path, "
    "a host name, a local folder or window name, a session id or the owner's name "
    "in a fixture exposes the author's machine and breaks for every other user."
)
FIX = (
    "Replace each value with a neutral one that keeps the property the code needs:\n"
    "  a path built at runtime from $HOME or a temp dir, or /home/user in a fixture\n"
    "  a generic folder or window name such as work, project, or two words\n"
    "  octocat for a GitHub user in a demo, a seeded faker name for a person\n"
    "  a synthetic UUID instead of a live session id\n"
    "Extra names to catch go one per line in ~/.claude/machine-identifiers.txt;\n"
    "a line `!name` there exempts a product name that matches a local folder."
)
BYPASS_WHEN = "The match is a public product name, not something from this machine."


def _repo_root(directory: str) -> Path:
    top = probe(["git", "-C", directory, "rev-parse", "--show-toplevel"]).strip()
    return Path(top or directory)


def _staged_lines(command: str, cwd: str) -> list[Line]:
    request = commit_request(command, cwd)
    if request is None:
        return []
    documents = staged_documents(request)
    staged = [
        line for d in documents for line in added_lines(d.path, d.before, d.after)
    ]
    return [*staged, *added_in_command(command, request.directory)]


def findings_for(command: str, cwd: str) -> list[Finding]:
    lines = [*_staged_lines(command, cwd), *command_text_lines(command, cwd)]
    if not lines:
        return []
    return scan_lines(lines, discover(Path.home(), _repo_root(cwd)))


def _report(found: list[Finding]) -> str:
    rows = [f"{f.path}:{f.line}: {f.kind.value} {f.token!r}" for f in found]
    return "\n".join(
        ["This would publish details of the machine it was written on:", *rows]
    )


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
    _audit(hook=HOOK, decision="block", reason=decision)
    return 2


def _command(payload: dict[str, object]) -> str:
    command = tool_input_of(payload).get("command")
    return (
        command
        if payload.get("tool_name") == "Bash" and isinstance(command, str)
        else ""
    )


def main() -> int:
    if not should_run(HOOK) or os.environ.get(BYPASS_ENV) == "1" or is_bypassed(HOOK):
        return 0
    payload = read_hook_payload(HOOK)
    command = _command(payload)
    if not command:
        return 0
    cwd = str(payload.get("cwd") or os.getcwd())
    try:
        found = findings_for(command, cwd)
    except StagedScanError as error:
        return emit(
            f"{HOOK} could not read what this commit records: {error}", "STOP-AND-ASK"
        )
    return emit(_report(found), "FIX-AND-RETRY") if found else 0


if __name__ == "__main__":
    sys.exit(main())
