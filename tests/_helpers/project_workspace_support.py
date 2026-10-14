from __future__ import annotations

import os
import random
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import project_workspace as pw  # noqa: E402

RNG = random.Random(20260930)


@pytest.fixture(autouse=True)
def isolated_git_config(monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def words(count: int = 4) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    return " ".join(
        "".join(RNG.choice(alphabet) for _ in range(RNG.randint(3, 9)))
        for _ in range(count)
    )


def run_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, timeout=30
    ).stdout


def make_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    run_git(root, "init", "-q", "-b", "main")
    run_git(root, "config", "user.email", f"{words(1)}@example.org")
    run_git(root, "config", "user.name", words(2))
    run_git(root, "config", "commit.gpgsign", "false")
    return root


def commit_file(repo: Path, rel: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(words())
    run_git(repo, "add", "-f", "--", rel)
    run_git(repo, "commit", "-q", "--no-verify", "-m", "add file")


__all__ = [
    "REPO_ROOT",
    "RNG",
    "commit_file",
    "isolated_git_config",
    "make_repo",
    "pw",
    "run_git",
    "words",
]
