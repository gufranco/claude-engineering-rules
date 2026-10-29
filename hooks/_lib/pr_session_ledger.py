from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from _lib.ai_review import REMOTE, pr_urls
from _lib.shell_segments import command_head, quoted_segments

LEDGER_DIR_ENV = "CLAUDE_PR_LEDGER_DIR"
SAFE_SESSION = re.compile(r"[A-Za-z0-9_-]{1,128}")
RETENTION_SECONDS = 7 * 24 * 3600
REPO_FLAGS = ("--repo", "-R")
GIT_TIMEOUT_SECONDS = 10


def ledger_dir() -> Path:
    default = Path.home() / ".claude" / ".pr-session-ledger"
    return Path(os.environ.get(LEDGER_DIR_ENV, str(default)))


def _read(file: Path) -> list[str]:
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    if not isinstance(data, list) or not all(isinstance(e, str) for e in data):
        raise ValueError(f"{file} is not a list of pull requests")
    return data


def _prune(directory: Path, now: float) -> None:
    for file in directory.glob("*.json"):
        if now - file.stat().st_mtime > RETENTION_SECONDS:
            file.unlink(missing_ok=True)


def record(session: str, text: str, directory: Path, now: float) -> None:
    targets = pr_urls(text)
    if not targets or not SAFE_SESSION.fullmatch(session):
        return
    directory.mkdir(parents=True, exist_ok=True)
    _prune(directory, now)
    file = directory / f"{session}.json"
    entries = [f"{t.slug}#{t.number}".lower() for t in targets]
    merged = list(dict.fromkeys([*_read(file), *entries]))
    staged = file.with_suffix(".tmp")
    staged.write_text(json.dumps(merged), encoding="utf-8")
    os.replace(staged, file)


def opened(session: str, slug: str, directory: Path) -> tuple[str, ...]:
    if not SAFE_SESSION.fullmatch(session):
        return ()
    prefix = f"{slug.lower()}#"
    return tuple(
        e for e in _read(directory / f"{session}.json") if e.startswith(prefix)
    )


def _origin_slug(cwd: str) -> str:
    result = subprocess.run(
        ["git", "-C", cwd, "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    match = REMOTE.search(result.stdout.strip()) if result.returncode == 0 else None
    return f"{match.group(2)}/{match.group(3)}" if match else ""


def _repo_flag(args: list[str]) -> str:
    pairs = zip(args, [*args[1:], ""])
    flagged = [value for flag, value in pairs if flag in REPO_FLAGS]
    joined = [a.split("=", 1)[1] for a in args if a.startswith("--repo=")]
    return next(iter([*flagged, *joined]), "")


def create_repos(command: str, cwd: str) -> list[str]:
    current, found = cwd, []
    for tokens in quoted_segments(command):
        head, args = command_head(tokens)
        if head == "cd" and len(args) > 1:
            current = os.path.join(current, os.path.expanduser(args[1]))
        elif head == "gh" and args[1:3] == ["pr", "create"]:
            slug = _repo_flag(args[3:]) or _origin_slug(current)
            found = [*found, slug] if slug else found
    return found
