#!/usr/bin/env python3
"""PreToolUse Bash hook: delegate to `rtk rewrite` for token-saving rewrites.

The Rust binary `rtk rewrite` is the source of truth for the command catalog.
Hook only translates its exit code into Claude Code's PreToolUse output shape:

    0 + stdout : rewrite found, no permission rule matched. Emit allow plus updatedInput.
    1          : no rtk equivalent. Pass through.
    2          : deny rule matched. Pass through (settings deny handles it).
    3 + stdout : ask rule matched. Emit updatedInput; let Claude Code prompt.

Requires `rtk >= 0.23.0` on PATH. Missing or too-old binary: warn and exit 0.

Bypass channels:
    1. Env var `RTK_REWRITE_DISABLE=1` (parent shell).
    2. File registry entry for hook `rtk-rewrite`.
"""

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
    if major < MIN_MAJOR:
        return True
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
