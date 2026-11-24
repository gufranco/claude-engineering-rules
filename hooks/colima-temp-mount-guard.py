#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib.audit_log import record as _audit  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402

HOOK = "colima-temp-mount-guard"

DOCKER_RUN = re.compile(r"\bdocker\s+(?:container\s+)?(?:run|create)\b")
MOUNT_SOURCE = re.compile(
    r"(?:\s-v\s+|\s--volume[=\s]+)[\"']?([^\s\"':]+)"
    r"|\s--mount[=\s]+[^\s]*?\b(?:source|src)=([^\s,]+)"
)
TEMP_PREFIXES = (
    "/tmp",
    "/private/tmp",
    "/var/folders",
    "/private/var/folders",
    "$TMPDIR",
    "${TMPDIR",
)
MKTEMP = re.compile(r"\bmktemp\b([^)\n;&|]*)")
HOME_TEMPLATE = re.compile(r"\$HOME|\$\{HOME\}|~/")


def _temp_literal(command: str) -> str | None:
    for match in MOUNT_SOURCE.finditer(command):
        source = match.group(1) or match.group(2) or ""
        if source.startswith(TEMP_PREFIXES):
            return source
    return None


def _temp_mktemp(command: str) -> str | None:
    for match in MKTEMP.finditer(command):
        if not HOME_TEMPLATE.search(match.group(1)):
            return f"mktemp{match.group(1)}".strip()
    return None


def find_temp_mount(command: str) -> str | None:
    if not DOCKER_RUN.search(command) or not MOUNT_SOURCE.search(command):
        return None
    return _temp_literal(command) or _temp_mktemp(command)


def _block_reason(source: str) -> str:
    return (
        f"BLOCKED: a Docker mount from a temp folder ({source}). Colima shares only "
        "the home directory with its VM, so Docker mounts it empty and the "
        "container works on nothing without an error.\n"
        'Fix: create the folder under the home directory, as in `mktemp -d "$HOME/.cache/name-XXXXXX"`.\n'
        "Bypass (one-off): set COLIMA_TEMP_MOUNT_GUARD_DISABLE=1 in parent shell."
    )


def emit_block(reason: str, command: str) -> int:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stderr.write(reason)
    _audit(
        hook=HOOK,
        decision="block",
        decision_class="block",
        reason=reason[:200],
        tool="Bash",
        command_excerpt=command[:200],
    )
    return 2


def main() -> int:
    if os.environ.get("COLIMA_TEMP_MOUNT_GUARD_DISABLE") == "1" or is_bypassed(HOOK):
        return 0
    data = read_hook_payload(HOOK)
    if data.get("tool_name") != "Bash":
        return 0
    if not os.path.isdir(os.path.join(os.path.expanduser("~"), ".colima")):
        return 0
    command = (data.get("tool_input") or {}).get("command", "")
    source = find_temp_mount(command)
    if source is None:
        return 0
    return emit_block(_block_reason(source), command)


if __name__ == "__main__":
    sys.exit(main())
