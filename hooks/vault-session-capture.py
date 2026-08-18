#!/usr/bin/env python3
"""Append what a session worked on to today's vault note, before compaction.

Opt-in and inert until ``VAULT_AUTO_CAPTURE=1`` is set, because this is an
unattended process writing to a knowledge base.

It records what was worked on, never what was concluded. A hook is a Python
process, not a model: it can observe that files changed and that commits
landed, and it cannot tell durable knowledge from incidental work. Pretending
otherwise would file inference as fact, which is the failure the note
specification exists to prevent. Promotion into the knowledge graph stays a
deliberate act.

The landing zone is deliberate too. Daily notes are dated containers, which the
freshness policy exempts, so a machine-written snapshot claims what was true on
a date and can never rot into a false current claim.

Safety properties, all of them load-bearing:

  - appends only, and never rewrites or removes existing content
  - writes only under the vault's daily folder
  - caps its own output
  - exits zero on every failure, so compaction is never broken

Bypass: unset ``VAULT_AUTO_CAPTURE``, or set ``VAULT_CAPTURE_DISABLE=1``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from _lib import knowledge_notes as kn
except ImportError:  # pragma: no cover
    sys.exit(0)

try:
    from _lib.project_scope import repo_root
except ImportError:  # pragma: no cover
    sys.exit(0)

ENABLE_VAR = "VAULT_AUTO_CAPTURE"
DISABLE_VAR = "VAULT_CAPTURE_DISABLE"
DAILY_DIR = "daily"
MAX_FILES = 25
MAX_COMMITS = 10
GIT_TIMEOUT = 5

CAVEAT = (
    "Automatic capture written at compaction. Machine-written and unreviewed: it "
    "records what was worked on, never what was concluded. Promote anything durable "
    "with /brain capture."
)


def git(args: list[str], cwd: Path) -> str:
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
    return result.stdout.strip() if result.returncode == 0 else ""


def changed_files(cwd: Path) -> list[str]:
    raw = git(["status", "--porcelain"], cwd)
    names: list[str] = []
    for line in raw.splitlines():
        name = line[3:].strip() if len(line) > 3 else ""
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


def capture(root: Path, cwd: Path, now: datetime) -> bool:
    repo = repo_root(cwd)
    if repo is None:
        return False
    day = now.date().isoformat()
    target = root / DAILY_DIR / f"{day}.md"
    existing = ""
    if target.exists():
        try:
            existing = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # pragma: no cover
            return False
    files = changed_files(repo)
    commits = [
        line for line in recent_commits(repo) if line.split(" ", 1)[0] not in existing
    ]
    if not files and not commits:
        return False
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"], repo) or "unknown"
    target.parent.mkdir(parents=True, exist_ok=True)
    block = render_block(now.strftime("%H:%M GMT"), repo.name, branch, files, commits)
    if existing:
        target.write_text(existing.rstrip("\n") + "\n\n" + block, encoding="utf-8")
    else:
        target.write_text(render_header(day) + block, encoding="utf-8")
    return True


def main() -> int:
    if os.environ.get(ENABLE_VAR) != "1" or os.environ.get(DISABLE_VAR) == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
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
