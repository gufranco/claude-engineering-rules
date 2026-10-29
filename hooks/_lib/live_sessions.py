from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

SESSIONS_DIR_ENV = "CLAUDE_SESSIONS_DIR"
MAX_RECORDS = 200


@dataclass(frozen=True, slots=True)
class LiveSession:
    session_id: str
    cwd: str
    name: str
    status: str


def sessions_dir() -> Path:
    default = Path.home() / ".claude" / "sessions"
    return Path(os.environ.get(SESSIONS_DIR_ENV, str(default)))


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _record(file: Path) -> LiveSession | None:
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    pid, session, cwd = data.get("pid"), data.get("sessionId"), data.get("cwd")
    if not (isinstance(pid, int) and isinstance(session, str) and isinstance(cwd, str)):
        return None
    if not _alive(pid):
        return None
    return LiveSession(
        session, cwd, str(data.get("name") or ""), str(data.get("status") or "")
    )


def sessions(folder: Path) -> tuple[LiveSession, ...]:
    if not folder.is_dir():
        return ()
    files = sorted(folder.glob("*.json"))[:MAX_RECORDS]
    return tuple(found for file in files if (found := _record(file)) is not None)


def _inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def _foreign(session: LiveSession, path: str, here: str, own_session: str) -> bool:
    root = os.path.realpath(session.cwd)
    shelters_me = bool(here) and here != root and _inside(here, root)
    return session.session_id != own_session and _inside(path, root) and not shelters_me


def owner_of(
    target: str, own_cwd: str, own_session: str, live: tuple[LiveSession, ...]
) -> LiveSession | None:
    path = os.path.realpath(target)
    here = os.path.realpath(own_cwd) if own_cwd else ""
    owners = [s for s in live if _foreign(s, path, here, own_session)]
    return max(owners, key=lambda s: len(os.path.realpath(s.cwd)), default=None)
