"""In-session bypass registry for `~/.claude/hooks/*.py`.


Every hook in this repo supports two bypass channels:

1. Parent-shell env var (`<NAME>_DISABLE=1`). Existing convention. Requires
   exiting Claude Code, exporting the var, and re-entering. Safe but slow.
2. File-based registry at `~/.claude/.bypass-state.json` (this module).
   The assistant or user writes a TTL-bound entry while the session is live;
   the hook short-circuits as long as the entry has not expired.

Both channels coexist. Either one grants a pass. Neither is required.

This module is read-side only. The writer (`bypass_writer.py`) and CLI
(`tools/scripts/bypass.py`) handle creation, modification, and removal.

Public API:

    is_bypassed(hook_name: str) -> bool
        True when `hook_name` (or the wildcard `*`) has a live entry.
        Fails open: returns False on missing file, malformed JSON,
        expired entries, OS errors. A failing read never blocks a hook.

    STATE_PATH: Path
        Absolute path to the registry file (constant for tests to monkeypatch).

File schema (version 1):

    {
      "version": 1,
      "bypasses": [
        {
          "hook": "<hook-name-or-*>",
          "expires_at": "<ISO-8601 UTC>",
          "reason": "<free text, optional>"
        }
      ]
    }

A wildcard entry (`"hook": "*"`) matches every hook. Use sparingly.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(
    os.environ.get(
        "CLAUDE_BYPASS_STATE", str(Path.home() / ".claude" / ".bypass-state.json")
    )
)

WILDCARD = "*"


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
    """Return True when `hook_name` has a live bypass entry.

    Wildcard entries (`"hook": "*"`) match any hook name. Expired entries
    are ignored. Read errors fail open (return False) so a corrupt registry
    never blocks a real hook from doing its job.
    """
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
        if expires_at > current:
            return True
    return False
