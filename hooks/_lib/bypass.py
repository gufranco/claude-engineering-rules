from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_PATH = Path(
    os.environ.get(
        "CLAUDE_BYPASS_STATE", str(Path.home() / ".claude" / ".bypass-state.json")
    )
)

WILDCARD = "*"
MAX_TTL_SECONDS = 3600
WILDCARD_MAX_TTL_SECONDS = 1200
CLOCK_TOLERANCE = timedelta(seconds=60)


def ttl_ceiling(hook_name: str) -> int:
    return WILDCARD_MAX_TTL_SECONDS if hook_name == WILDCARD else MAX_TTL_SECONDS


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
    except (FileNotFoundError, PermissionError, OSError):
        return []
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    entries = data.get("bypasses")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def is_bypassed(
    hook_name: str, *, state_path: Path | None = None, now: datetime | None = None
) -> bool:
    if not hook_name:
        return False
    path = state_path if state_path is not None else STATE_PATH
    current = now if now is not None else _now()
    for entry in _load_entries(path):
        target = entry.get("hook")
        if target != hook_name and target != WILDCARD:
            continue
        expires_at = _parse_expiry(entry.get("expires_at"))
        if expires_at is None:
            continue
        ceiling = current + timedelta(seconds=ttl_ceiling(str(target)))
        if current < expires_at <= ceiling + CLOCK_TOLERANCE:
            return True
    return False
