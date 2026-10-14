#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.bypass import is_bypassed  # noqa: E402

HOOK_NAME = "rtk-rewrite"
ENV_DISABLE = "RTK_REWRITE_DISABLE"
MIN_MAJOR = 0
MIN_MINOR = 23
RTK_TIMEOUT_SECONDS = 5
VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _read_payload() -> dict:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _command_too_old() -> bool:
    try:
        result = subprocess.run(
            ["rtk", "--version"],
            capture_output=True,
            text=True,
            timeout=RTK_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return True
    match = VERSION_RE.search(result.stdout or "")
    if not match:
        return False
    major, minor = int(match.group(1)), int(match.group(2))
    if major == MIN_MAJOR and minor < MIN_MINOR:
        sys.stderr.write(
            f"[rtk] WARNING: rtk {match.group(0)} is too old (need >= {MIN_MAJOR}.{MIN_MINOR}.0). "
            "Upgrade: cargo install rtk\n"
        )
        return True
    return False


def _emit_allow(updated_input: dict) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "RTK auto-rewrite",
                    "updatedInput": updated_input,
                }
            }
        )
    )


def _emit_ask(updated_input: dict) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "updatedInput": updated_input,
                }
            }
        )
    )


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1":
        return 0
    if is_bypassed(HOOK_NAME):
        return 0
    if shutil.which("rtk") is None:
        sys.stderr.write(
            "[rtk] WARNING: rtk is not installed or not in PATH. "
            "Hook cannot rewrite commands.\n"
        )
        return 0
    if _command_too_old():
        return 0
    payload = _read_payload()
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    command = tool_input.get("command", "")
    if not isinstance(command, str) or not command:
        return 0
    try:
        result = subprocess.run(
            ["rtk", "rewrite", command],
            capture_output=True,
            text=True,
            timeout=RTK_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return 0
    rewritten = result.stdout
    exit_code = result.returncode
    if exit_code == 0:
        if rewritten == command:
            return 0
        updated = dict(tool_input)
        updated["command"] = rewritten
        _emit_allow(updated)
        return 0
    if exit_code in (1, 2):
        return 0
    if exit_code == 3:
        updated = dict(tool_input)
        updated["command"] = rewritten
        _emit_ask(updated)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
