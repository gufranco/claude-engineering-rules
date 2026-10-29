#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.hook_input import read_advisory_payload  # noqa: E402

ENV_VAR = "VAULT_COMPILE_DISABLE"
VAULT_VAR = "SECOND_BRAIN_VAULT"
TIMEOUT_SECONDS = 20
TIMEOUT_VAR = "VAULT_COMPILE_TIMEOUT_SECONDS"


def memory_dir_for(cwd: Path) -> Path:
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(cwd))
    return Path.home() / ".claude" / "projects" / slug / "memory"


def _compile_script() -> Path | None:
    root = os.environ.get(VAULT_VAR, "").strip()
    if not root or not Path(root).is_dir():
        return None
    script = Path(root) / ".ci" / "compile.py"
    return script if script.is_file() else None


def _payload_cwd() -> Path:
    payload = read_advisory_payload("vault-compile")
    return Path(str(payload.get("cwd") or Path.cwd()))


def _ready_memory_dir(cwd: Path) -> Path | None:
    memory = memory_dir_for(cwd)
    if not memory.parent.is_dir():
        return None
    try:
        memory.mkdir(exist_ok=True)
    except OSError as error:
        sys.stderr.write(f"vault-compile: cannot create {memory}: {error}\n")
        return None
    return memory


def _run_compile(script: Path, cwd: Path, memory: Path) -> str | None:
    command = [
        sys.executable,
        str(script),
        "--apply",
        "--cwd",
        str(cwd),
        "--memory-dir",
        str(memory),
    ]
    try:
        finished = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=float(os.environ.get(TIMEOUT_VAR) or TIMEOUT_SECONDS),
            check=False,
        )
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"vault-compile: {script.name} timed out\n")
        return None
    return finished.stdout if finished.returncode == 0 else None


def _changed_lines(stdout: str) -> list[str]:
    return [
        line
        for line in stdout.splitlines()
        if line.startswith(("applied:", "removed")) and not line.endswith(": 0")
    ]


def main() -> int:
    if os.environ.get(ENV_VAR) == "1":
        return 0

    script = _compile_script()
    if script is None:
        return 0

    cwd = _payload_cwd()
    memory = _ready_memory_dir(cwd)
    if memory is None:
        return 0

    stdout = _run_compile(script, cwd, memory)
    if stdout is None:
        return 0

    changed = _changed_lines(stdout)
    if changed:
        print("Memory recompiled from the vault: " + "; ".join(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
