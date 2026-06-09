"""Writer for the in-session bypass registry.


Companion to `bypass.py` (read-side). Lets the assistant or the user engage
or clear a bypass entry without hand-editing JSON.

Public API:

    set_bypass(hook, *, ttl_seconds=600, reason=None, state_path=None) -> Path
        Add or replace a bypass entry for `hook`. TTL is clamped to
        [60, 3600]. Writes the file with mode 0600. Returns the file path.

    clear_bypass(hook=None, *, state_path=None) -> int
        Remove the entry for `hook`, or every entry when `hook` is None.
        Returns the number of entries removed.

The file format is the v1 schema documented in `bypass.py`.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .bypass import STATE_PATH, WILDCARD

DEFAULT_TTL_SECONDS = 600
MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 3600
WILDCARD_DEFAULT_TTL_SECONDS = 300


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clamp_ttl(ttl_seconds: int, *, hook: str) -> int:
    if ttl_seconds < MIN_TTL_SECONDS:
        return MIN_TTL_SECONDS
    if hook == WILDCARD:
        cap = min(MAX_TTL_SECONDS, WILDCARD_DEFAULT_TTL_SECONDS * 4)
        return min(ttl_seconds, cap)
    if ttl_seconds > MAX_TTL_SECONDS:
        return MAX_TTL_SECONDS
    return ttl_seconds


def _load_state(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, PermissionError, OSError, json.JSONDecodeError):
        return {"version": 1, "bypasses": []}
    if (
        not isinstance(data, dict)
        or data.get("version") != 1
        or not isinstance(data.get("bypasses"), list)
    ):
        return {"version": 1, "bypasses": []}
    data["bypasses"] = [entry for entry in data["bypasses"] if isinstance(entry, dict)]
    return data


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".bypass-state.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def set_bypass(
    hook: str,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    reason: str | None = None,
    state_path: Path | None = None,
    now: datetime | None = None,
) -> Path:
    """Add or replace a bypass entry. Returns the registry path."""
    if not hook:
        raise ValueError("hook name is required")
    path = state_path if state_path is not None else STATE_PATH
    current = now if now is not None else _now()
    ttl = _clamp_ttl(int(ttl_seconds), hook=hook)
    expires_at = current + timedelta(seconds=ttl)
    state = _load_state(path)
    state["bypasses"] = [
        entry for entry in state["bypasses"] if entry.get("hook") != hook
    ]
    new_entry: dict = {"hook": hook, "expires_at": expires_at.isoformat()}
    if reason:
        new_entry["reason"] = reason
    state["bypasses"].append(new_entry)
    _atomic_write(path, state)
    return path


def clear_bypass(hook: str | None = None, *, state_path: Path | None = None) -> int:
    """Remove one entry by hook name or every entry when hook is None.

    Returns the number of entries removed.
    """
    path = state_path if state_path is not None else STATE_PATH
    state = _load_state(path)
    before = len(state["bypasses"])
    if hook is None:
        state["bypasses"] = []
    else:
        state["bypasses"] = [
            entry for entry in state["bypasses"] if entry.get("hook") != hook
        ]
    removed = before - len(state["bypasses"])
    if removed:
        _atomic_write(path, state)
    return removed
