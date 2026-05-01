"""Structured audit log shared by hooks.

Writes JSON Lines to ~/.claude/logs/hooks.log. Rotates the file when it grows
past 5 MiB by renaming to hooks.log.1, dropping the previous .1 if any. Keeps
only one backup so the on-disk footprint stays bounded.

Usage from a hook:

    from audit_log import record
    record(hook="dangerous-command-blocker", decision="block",
           reason="rm -rf /", tool="Bash", payload_excerpt=cmd[:200])

The function never raises. Logging is best-effort.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

LOG_DIR = os.path.expanduser("~/.claude/logs")
LOG_PATH = os.path.join(LOG_DIR, "hooks.log")
BACKUP_PATH = LOG_PATH + ".1"
MAX_BYTES = 5 * 1024 * 1024


def _rotate_if_needed() -> None:
    try:
        size = os.path.getsize(LOG_PATH)
    except OSError:
        return
    if size < MAX_BYTES:
        return
    try:
        if os.path.exists(BACKUP_PATH):
            os.remove(BACKUP_PATH)
        os.rename(LOG_PATH, BACKUP_PATH)
    except OSError:
        return


def record(**fields: Any) -> None:
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        _rotate_if_needed()
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **fields}
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        # Audit logging must never break a hook. Swallow and move on.
        return


if __name__ == "__main__":
    record(hook="audit_log", decision="self-test", argv=sys.argv)
