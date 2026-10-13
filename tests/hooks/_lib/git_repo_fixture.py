from __future__ import annotations

import os
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path

IDENTITY_SEED = 20261012


def isolated_git_env() -> dict[str, str]:
    generator = random.Random(IDENTITY_SEED)
    handle = f"dev{generator.randrange(10_000, 99_999)}"
    return {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_AUTHOR_NAME": handle,
        "GIT_AUTHOR_EMAIL": f"{handle}@example.invalid",
        "GIT_COMMITTER_NAME": handle,
        "GIT_COMMITTER_EMAIL": f"{handle}@example.invalid",
    }


@dataclass(frozen=True, slots=True)
class GitRepo:
    root: Path

    def git(self, *args: str) -> str:
        completed = subprocess.run(
            ["git", "-c", "commit.gpgsign=false", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
            env=isolated_git_env(),
            timeout=30,
        )
        return completed.stdout

    def write(self, relative: str, text: str) -> Path:
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def stage(self, relative: str, text: str) -> None:
        self.write(relative, text)
        self.git("add", "--", relative)

    def commit(self) -> None:
        self.git("commit", "-qm", "snapshot")


def new_git_repo(parent: Path) -> GitRepo:
    root = parent / "repo"
    root.mkdir()
    repo = GitRepo(root)
    repo.git("init", "-q", "-b", "main")
    return repo
