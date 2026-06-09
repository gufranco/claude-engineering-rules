#!/usr/bin/env python3
"""PreToolUse Bash hook: block `git commit` when staged files exceed 5 MB.

Prevents accidental commits of build artifacts, database dumps, media, BIOSes.

Bypass channels:
    1. Env var `LARGE_FILE_DISABLE=1` (parent shell). Use for intentionally
       tracked large binary assets.
    2. File registry entry for hook `large-file-blocker`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.output import block as _block  # noqa: E402

try:
    from _lib.audit_log import record as _audit_record
except Exception:  # noqa: BLE001
    _audit_record = None  # type: ignore[assignment]

HOOK_NAME = "large-file-blocker"
ENV_DISABLE = "LARGE_FILE_DISABLE"
MAX_SIZE_KB = 5120
GIT_TIMEOUT_SECONDS = 5
COMMIT_PATTERN = re.compile(r"\bgit\s+commit\b")


def _read_command() -> str:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    tool_input = data.get("tool_input") or data.get("input") or {}
    if not isinstance(tool_input, dict):
        return ""
    cmd = tool_input.get("command", "")
    return cmd if isinstance(cmd, str) else ""


def _staged_files() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def _file_size_kb(path: Path) -> int | None:
    try:
        size_bytes = path.stat().st_size
    except OSError:
        return None
    return max(1, (size_bytes + 1023) // 1024)


def _audit(command: str) -> None:
    if _audit_record is None:
        return
    try:
        _audit_record(
            hook=HOOK_NAME,
            decision="block",
            decision_class="block",
            reason="staged file exceeds size limit",
            tool="Bash",
            command_excerpt=command[:200],
        )
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1":
        return 0
    if is_bypassed(HOOK_NAME):
        return 0
    command = _read_command()
    if not COMMIT_PATTERN.search(command):
        return 0
    offenders: list[tuple[str, int]] = []
    for name in _staged_files():
        path = Path(name)
        if not path.is_file():
            continue
        size_kb = _file_size_kb(path)
        if size_kb is None or size_kb <= MAX_SIZE_KB:
            continue
        offenders.append((name, size_kb))
    if not offenders:
        return 0
    detected = "\n".join(
        [f"{MAX_SIZE_KB}KB threshold exceeded by {len(offenders)} staged file(s):"]
        + [f"  {name} ({size_kb / 1024:.1f} MB)" for name, size_kb in offenders]
    )
    message = _block(
        hook=HOOK_NAME,
        rule_anchor="rules/git-workflow.md (Ignored Artifacts)",
        detected=detected,
        why="Large binaries in git history bloat clones, slow CI, and waste storage forever.",
        fix=(
            "Unstage the file:\n"
            "  bad:  git add huge.bin && git commit\n"
            "  good: git reset HEAD huge.bin && git rm --cached huge.bin\n"
            "Add the path to .gitignore, or move it to Git LFS for tracked binaries."
        ),
        bypass_when=(
            "Intentionally tracking a vetted large asset (BIOS, IWAD, golden frame). "
            "Confirm with the user before bypassing in shared repos."
        ),
        decision="STOP-AND-ASK",
        env_var=ENV_DISABLE,
        safety="future large files in the same session will not be blocked.",
    )
    sys.stderr.write(message)
    _audit(command)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
