#!/usr/bin/env python3
"""Compile this project's memory from the vault at session start.

The vault is the source of truth and the memory directory is a generated
artifact, so a memory directory is only as current as the last time somebody
remembered to run the compile. Nobody should have to remember: the point of the
vault integration is that capture and retrieval both happen without a command.

Quiet by design. It prints only when the compile changed something, because a
line at every session start is noise that trains the reader to skip the whole
block, including the times it matters.

Never fails a session. Every failure path exits zero, because a session that
cannot start is a far worse outcome than a memory directory one compile behind.

Bypass: set ``VAULT_COMPILE_DISABLE=1`` in a parent shell.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ENV_VAR = "VAULT_COMPILE_DISABLE"
VAULT_VAR = "SECOND_BRAIN_VAULT"
TIMEOUT_SECONDS = 20


def memory_dir_for(cwd: Path) -> Path:
    """Where Claude Code keeps this working directory's memory."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(cwd))
    return Path.home() / ".claude" / "projects" / slug / "memory"


def main() -> int:
    if os.environ.get(ENV_VAR) == "1":
        return 0

    root = os.environ.get(VAULT_VAR, "").strip()
    if not root or not Path(root).is_dir():
        return 0

    script = Path(root) / ".ci" / "compile.py"
    if not script.is_file():
        return 0

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = Path(payload.get("cwd") or Path.cwd())
    memory = memory_dir_for(cwd)
    if not memory.is_dir():
        return 0

    try:
        finished = subprocess.run(
            [
                sys.executable,
                str(script),
                "--apply",
                "--cwd",
                str(cwd),
                "--memory-dir",
                str(memory),
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0

    if finished.returncode != 0:
        return 0

    changed = [
        line
        for line in finished.stdout.splitlines()
        if line.startswith(("applied:", "removed")) and not line.endswith(": 0")
    ]
    if changed:
        print("Memory recompiled from the vault: " + "; ".join(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
