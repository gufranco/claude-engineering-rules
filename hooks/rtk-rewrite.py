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


def _read_payload() -> dict[str, object]:
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


def _emit_allow(updated_input: dict[str, object]) -> None:
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


def _emit_ask(updated_input: dict[str, object]) -> None:
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


def _rtk_unavailable() -> bool:
    if shutil.which("rtk") is None:
        sys.stderr.write(
            "[rtk] WARNING: rtk is not installed or not in PATH. "
            "Hook cannot rewrite commands.\n"
        )
        return True
    return _command_too_old()


def _command_input() -> tuple[dict[str, object], str] | None:
    payload = _read_payload()
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command", "")
    if not isinstance(command, str) or not command:
        return None
    return tool_input, command


def _rewrite(command: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["rtk", "rewrite", command],
            capture_output=True,
            text=True,
            timeout=RTK_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _emit_result(
    tool_input: dict[str, object],
    command: str,
    result: subprocess.CompletedProcess[str],
) -> None:
    rewritten = result.stdout
    updated = {**tool_input, "command": rewritten}
    if result.returncode == 0 and rewritten != command:
        _emit_allow(updated)
    elif result.returncode == 3:
        _emit_ask(updated)


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1":
        return 0
    if is_bypassed(HOOK_NAME):
        return 0
    if _rtk_unavailable():
        return 0
    command_input = _command_input()
    if command_input is None:
        return 0
    tool_input, command = command_input
    result = _rewrite(command)
    if result is not None:
        _emit_result(tool_input, command, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
