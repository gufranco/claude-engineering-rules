from __future__ import annotations

import json
import os
import sys
import stat
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_PATH = Path(
    os.environ.get(
        "CLAUDE_SESSION_LOCK_STATE",
        str(Path.home() / ".claude" / ".session-locks.json"),
    )
)

WILDCARD = "*"

MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 14400
DEFAULT_TTL_SECONDS = 3600


class CorruptLockFile(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_expiry(raw: object) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def _load_entries(path: Path) -> list[dict[str, object]]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return []
    except (PermissionError, OSError) as exc:
        raise CorruptLockFile(str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise CorruptLockFile(str(exc)) from exc
    if not isinstance(data, dict):
        raise CorruptLockFile("root is not an object")
    entries = data.get("locks")
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise CorruptLockFile("locks is not a list")
    return [entry for entry in entries if isinstance(entry, dict)]


def is_locked(
    lock_name: str, *, state_path: Path | None = None, now: datetime | None = None
) -> bool:
    if not lock_name:
        return False
    path = state_path if state_path is not None else STATE_PATH
    current = now if now is not None else _now()
    try:
        entries = _load_entries(path)
    except CorruptLockFile:
        return True
    for entry in entries:
        target = entry.get("lock")
        if target != lock_name and target != WILDCARD:
            continue
        expires_at = _parse_expiry(entry.get("expires_at"))
        if expires_at is None:
            continue
        if expires_at > current:
            return True
    return False


def _atomic_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".session-locks-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.chmod(tmp_name, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError as cleanup_error:
            sys.stderr.write(f"could not remove {tmp_name}: {cleanup_error}\n")
        raise


def _surviving_entries(path: Path, now: datetime) -> list[dict[str, object]]:
    try:
        entries = _load_entries(path)
    except CorruptLockFile:
        return []
    survivors: list[dict[str, object]] = []
    for entry in entries:
        expires_at = _parse_expiry(entry.get("expires_at"))
        if expires_at is not None and expires_at > now:
            survivors.append(entry)
    return survivors


def acquire(
    lock_name: str,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    reason: str | None = None,
    state_path: Path | None = None,
) -> Path:
    if not lock_name:
        raise ValueError("lock_name is required")
    path = state_path if state_path is not None else STATE_PATH
    now = _now()
    ttl = max(MIN_TTL_SECONDS, min(MAX_TTL_SECONDS, int(ttl_seconds)))
    survivors = [
        entry
        for entry in _surviving_entries(path, now)
        if entry.get("lock") != lock_name
    ]
    survivors.append(
        {
            "lock": lock_name,
            "expires_at": (now + timedelta(seconds=ttl)).isoformat(),
            "reason": reason or "",
        }
    )
    _atomic_write(path, {"version": 1, "locks": survivors})
    return path


def release(lock_name: str | None = None, *, state_path: Path | None = None) -> int:
    path = state_path if state_path is not None else STATE_PATH
    now = _now()
    survivors = _surviving_entries(path, now)
    if lock_name is None:
        removed = len(survivors)
        keep: list[dict[str, object]] = []
    else:
        keep = [entry for entry in survivors if entry.get("lock") != lock_name]
        removed = len(survivors) - len(keep)
    _atomic_write(path, {"version": 1, "locks": keep})
    return removed
