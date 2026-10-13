#!/usr/bin/env python3
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
    if not memory.parent.is_dir():
        return 0
    try:
        memory.mkdir(exist_ok=True)
    except OSError:
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
