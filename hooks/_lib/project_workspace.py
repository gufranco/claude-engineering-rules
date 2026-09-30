"""Local project workspace: where the user's working material lives in a repo.

Every repository gets one folder for research, requirements, plans, and a
continuation prompt. The folder is ignored through `.git/info/exclude`, never
the committed `.gitignore`, and it never lives inside a directory the project
owns. `docs/` is preferred; a project that owns `docs/` gets `.work/`.

Ownership is sticky: the exclude file carries a marker line above each entry
this module wrote, so a workspace that later gains files still resolves to
the same folder. A folder the project starts tracking loses that claim.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

WORKSPACE_CANDIDATES = ("docs", ".work", ".work-local")
PROMPT_NAME = "PROMPT.md"
EXCLUDE_MARKER = "# local workspace, never committed"
GIT_TIMEOUT_S = 3.0
MAX_STATUS_ENTRIES = 5000
RENAME_CODES = frozenset("RC")


class WorkspaceError(Exception):
    """Git could not answer, or no workspace folder is free."""


def _run(cwd: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceError(f"git {args[0]} could not run: {exc}") from exc


def git(top: Path, *args: str) -> str:
    result = _run(top, args)
    if result.returncode != 0:
        raise WorkspaceError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _git_optional(top: Path, *args: str) -> str | None:
    result = _run(top, args)
    return result.stdout.strip() if result.returncode == 0 else None


def toplevel(cwd: Path) -> Path | None:
    output = _git_optional(cwd, "rev-parse", "--show-toplevel")
    return Path(output).resolve() if output else None


def prompt_path(top: Path, root: str) -> Path:
    return top / root / PROMPT_NAME


def _exclude_file(top: Path) -> Path:
    return top / git(top, "rev-parse", "--git-path", "info/exclude").strip()


def managed_entries(top: Path) -> tuple[str, ...]:
    path = _exclude_file(top)
    if not path.is_file():
        return ()
    lines = path.read_text(encoding="utf-8").splitlines()
    pairs = zip(lines, lines[1:])
    return tuple(
        entry.strip("/") for marker, entry in pairs if marker == EXCLUDE_MARKER
    )


def _has_tracked(top: Path, rel: str) -> bool:
    return bool(git(top, "ls-files", "--", rel).strip())


def _claimable(top: Path, rel: str, managed: tuple[str, ...]) -> bool:
    folder = top / rel
    if _has_tracked(top, rel):
        return False
    if not folder.exists() or rel in managed:
        return True
    if not folder.is_dir():
        return False
    return (folder / PROMPT_NAME).is_file() or not any(folder.iterdir())


def resolve_root(top: Path) -> str:
    managed = managed_entries(top)
    for rel in WORKSPACE_CANDIDATES:
        if _claimable(top, rel, managed):
            return rel
    raise WorkspaceError(f"no free workspace folder among {WORKSPACE_CANDIDATES}")


def ensure_excluded(top: Path, rel: str) -> bool:
    if rel in managed_entries(top):
        return False
    path = _exclude_file(top)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    separator = "" if not existing or existing.endswith("\n") else "\n"
    block = f"{separator}{EXCLUDE_MARKER}\n/{rel}/\n"
    path.write_text(existing + block, encoding="utf-8")
    return True


def release_tracked(top: Path) -> tuple[str, ...]:
    released = tuple(rel for rel in managed_entries(top) if _has_tracked(top, rel))
    if not released:
        return ()
    path = _exclude_file(top)
    lines = path.read_text(encoding="utf-8").splitlines()
    dropped = {f"/{rel}/" for rel in released}
    kept = [
        line
        for index, line in enumerate(lines)
        if not _is_released_pair(lines, index, dropped)
    ]
    path.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
    return released


def _is_released_pair(lines: list[str], index: int, dropped: set[str]) -> bool:
    line = lines[index]
    if line == EXCLUDE_MARKER:
        return index + 1 < len(lines) and lines[index + 1] in dropped
    return line in dropped and index > 0 and lines[index - 1] == EXCLUDE_MARKER


def _changed_paths(top: Path) -> list[str]:
    raw = git(top, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    tokens = raw.split("\0")
    paths: list[str] = []
    skip_next = False
    for token in tokens[:MAX_STATUS_ENTRIES]:
        if skip_next or len(token) < 4:
            skip_next = False
            continue
        skip_next = bool(RENAME_CODES & set(token[:2]))
        paths.append(token[3:])
    return paths


def _newest_worktree_change(top: Path, rel: str) -> float | None:
    prefix = f"{rel}/"
    stamps = [
        (top / path).stat().st_mtime
        for path in _changed_paths(top)
        if not path.startswith(prefix) and (top / path).exists()
    ]
    return max(stamps, default=None)


def _newest_user_commit(top: Path) -> float | None:
    email = _git_optional(top, "config", "user.email")
    if not email or _git_optional(top, "rev-parse", "--verify", "-q", "HEAD") is None:
        return None
    stamp = git(
        top, "log", "-1", "--fixed-strings", f"--author={email}", "--format=%ct"
    )
    return float(stamp) if stamp.strip() else None


def prompt_is_stale(top: Path, rel: str) -> bool:
    stamps = [
        s for s in (_newest_worktree_change(top, rel), _newest_user_commit(top)) if s
    ]
    if not stamps:
        return False
    prompt = prompt_path(top, rel)
    return not prompt.is_file() or max(stamps) > prompt.stat().st_mtime


def _nearest_existing_dir(path: Path) -> Path:
    return next((c for c in [path, *path.parents] if c.is_dir()), Path(path.anchor))


def in_workspace(path: Path) -> bool:
    target = path.resolve()
    try:
        top = toplevel(_nearest_existing_dir(target.parent))
        return top is not None and top / resolve_root(top) in target.parents
    except WorkspaceError:
        return False
