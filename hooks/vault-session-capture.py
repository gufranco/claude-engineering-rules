#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib import knowledge_notes as kn  # noqa: E402
from _lib.hook_input import read_advisory_payload  # noqa: E402

from _lib.project_scope import repo_root  # noqa: E402

ENABLE_VAR = "VAULT_AUTO_CAPTURE"
DISABLE_VAR = "VAULT_CAPTURE_DISABLE"
DAILY_DIR = "daily"
MAX_FILES = 25
MAX_COMMITS = 10
GIT_TIMEOUT = 5

PORCELAIN_PATH_COLUMN = 3

CAVEAT = (
    "Automatic capture written at compaction. Machine-written and unreviewed: it "
    "records what was worked on, never what was concluded. Promote anything durable "
    "with /brain capture."
)


def git(args: list[str], cwd: Path, *, strip: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip() if strip else result.stdout


def changed_files(cwd: Path) -> list[str]:
    raw = git(["status", "--porcelain"], cwd, strip=False)
    names: list[str] = []
    for line in raw.splitlines():
        name = (
            line[PORCELAIN_PATH_COLUMN:].strip()
            if len(line) > PORCELAIN_PATH_COLUMN
            else ""
        )
        if name:
            names.append(name.split(" -> ")[-1])
    return names


def recent_commits(cwd: Path) -> list[str]:
    raw = git(
        ["log", "--oneline", "-n", str(MAX_COMMITS), "--since", "12 hours ago"], cwd
    )
    return [line for line in raw.splitlines() if line]


def render_block(
    stamp: str, project: str, branch: str, files: list[str], commits: list[str]
) -> str:
    lines = [
        f"## Session {stamp}",
        "",
        CAVEAT,
        "",
        f"- Project: `{project}` on branch `{branch}`",
    ]
    shown = files[:MAX_FILES]
    if shown:
        lines.append(f"- Touched: {', '.join(f'`{name}`' for name in shown)}")
    if len(files) > MAX_FILES:
        lines.append(f"- and {len(files) - MAX_FILES} more file(s) not listed")
    for commit in commits:
        lines.append(f"- Committed: `{commit}`")
    lines.append("")
    return "\n".join(lines)


def render_header(day: str) -> str:
    return (
        "---\n"
        f"date: {day}\n"
        "type: daily\n"
        "tags: [daily]\n"
        "ai-first: true\n"
        "confidence: stated\n"
        "---\n\n"
        f"{kn.PREAMBLE}\n\n"
        f"A dated record of what was worked on during {day}, appended automatically at "
        "compaction. Everything here is an observation of the working tree, not a "
        "conclusion about it, so treat it as a starting point rather than as knowledge.\n\n"
    )


RUNS_DIR = ".claude-runs"


def capture(root: Path, cwd: Path, now: datetime) -> bool:
    repo = repo_root(cwd)
    if repo is None:
        return False
    day = now.date().isoformat()
    target = root / DAILY_DIR / f"{day}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    files = changed_files(repo)
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"], repo) or "unknown"
    lock_path = root / RUNS_DIR / "capture.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        commits = [
            line
            for line in recent_commits(repo)
            if line.split(" ", 1)[0] not in existing
        ]
        if not files and not commits:
            return False
        block = render_block(
            now.strftime("%H:%M GMT"), repo.name, branch, files, commits
        )
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(
                _separator(existing) + block if existing else render_header(day) + block
            )
    return True


def _separator(existing: str) -> str:
    return (
        "\n"
        if existing.endswith("\n\n")
        else ("\n" if existing.endswith("\n") else "\n\n")
    )


def main() -> int:
    if os.environ.get(ENABLE_VAR) != "1" or os.environ.get(DISABLE_VAR) == "1":
        return 0
    payload = read_advisory_payload("vault-session-capture")
    if not payload:
        return 0
    root = kn.vault_root()
    if root is None:
        return 0
    raw_cwd = payload.get("cwd") or os.getcwd()
    try:
        cwd = Path(raw_cwd)
        if not cwd.is_dir():
            return 0
        capture(root, cwd, datetime.now(timezone.utc))
    except OSError:  # pragma: no cover
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
