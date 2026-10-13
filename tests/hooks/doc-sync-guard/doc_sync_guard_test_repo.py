from __future__ import annotations

import subprocess
from pathlib import Path

HOOK = "doc-sync-guard"


COMMIT = "git commit -m 'feat: change'"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _commit_all(repo: Path, message: str = "chore: baseline") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


def _stage(repo: Path, *paths: str) -> None:
    _git(repo, "add", *paths)
