from __future__ import annotations

import os
import random
import subprocess
import time
from pathlib import Path

HOOK = "project-workspace"


RNG = random.Random(20260930)


GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


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


def exclude_text(repo: Path) -> str:
    return (repo / ".git" / "info" / "exclude").read_text()


def start(run_hook, repo: Path, env: dict[str, str] | None = None):
    payload = {"hook_event_name": "SessionStart", "source": "startup", "cwd": str(repo)}
    return run_hook(HOOK, payload, env={**GIT_ENV, **(env or {})})


def stop(run_hook, repo: Path, active: bool = False):
    payload = {"hook_event_name": "Stop", "stop_hook_active": active, "cwd": str(repo)}
    return run_hook(HOOK, payload, env=GIT_ENV)


def bash(run_hook, tool_use, repo: Path, command: str, env=None):
    payload = tool_use("Bash", {"command": command}, cwd=str(repo))
    return run_hook(HOOK, payload, env={**GIT_ENV, **(env or {})})


def commit_owned_folders(repo: Path, names: tuple[str, ...]) -> None:
    for name in names:
        commit_file(repo, f"{name}/owned.md")


def claim_docs_with_stale_prompt(run_hook, repo: Path) -> None:
    start(run_hook, repo)
    (repo / "docs").mkdir()
    prompt = repo / "docs" / "PROMPT.md"
    prompt.write_text(words())
    stamp = time.time() - 600
    os.utime(prompt, (stamp, stamp))
    (repo / "main.py").write_text(words())


def write(repo: Path, rel: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(words())


def repo_with_untracked_prompt(tmp_path: Path, rel: str = "notes/PROMPT.md") -> Path:
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "src/main.py")
    write(repo, rel)
    return repo


def repo_with_tracked_prompt(tmp_path: Path) -> Path:
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "planning/PROMPT.md")
    write(repo, "planning/PROMPT.md")
    return repo
