from __future__ import annotations

import os
import subprocess
from pathlib import Path

HOOK = "internal-config-leakage"


GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


CONFIG_TEXT = "Read `CLAUDE.md` and ~/.claude/settings.json before continuing.\n"


def make_repo(root: Path) -> Path:
    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=root,
        check=True,
        capture_output=True,
        env={**os.environ, **GIT_ENV},
        timeout=30,
    )
    return root
