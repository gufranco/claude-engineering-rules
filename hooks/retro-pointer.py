#!/usr/bin/env python3
"""Stop hook that nudges the user to run /retro when blocks piled up.

Reads ~/.claude/logs/hooks.log, counts block/bypass entries for the current
session, and prints a one-line cue to stderr the first time it sees any.
Tracks "already shown" via a session-scoped sentinel in /tmp.

Performance budget: under 50 ms. Reads only the tail of the log.
Never raises into the hook exit path.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time

LOG_PATH = os.path.expanduser("~/.claude/logs/hooks.log")
TAIL_BYTES = 64 * 1024
MAX_AGE_SECONDS = 6 * 60 * 60  # only consider entries from last 6 hours when no session id


def _session_id() -> str:
    return os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("SESSION_ID") or ""


def _sentinel_path() -> str:
    sid = _session_id() or "no-session"
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in sid)
    return os.path.join(tempfile.gettempdir(), f"claude-retro-pointer-{safe}.flag")


def _already_shown() -> bool:
    return os.path.exists(_sentinel_path())


def _mark_shown() -> None:
    try:
        with open(_sentinel_path(), "w", encoding="utf-8") as fh:
            fh.write(str(int(time.time())))
    except OSError:
        return


def _read_tail() -> list[str]:
    try:
        size = os.path.getsize(LOG_PATH)
    except OSError:
        return []
    try:
        with open(LOG_PATH, "rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(-TAIL_BYTES, os.SEEK_END)
                fh.readline()  # discard partial first line
            return fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _matches_session(entry: dict, sid: str) -> bool:
    if sid:
        return entry.get("session_id") == sid
    ts = entry.get("ts", "")
    try:
        when = time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError):
        return False
    return (time.time() - when) <= MAX_AGE_SECONDS


def _summarise() -> tuple[int, int, list[str]]:
    sid = _session_id()
    blocks = 0
    bypasses = 0
    hooks: list[str] = []
    for line in _read_tail():
        try:
            entry = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not _matches_session(entry, sid):
            continue
        decision = entry.get("decision")
        if decision == "block":
            blocks += 1
            hook = entry.get("hook")
            if hook and hook not in hooks:
                hooks.append(hook)
        elif decision == "bypass":
            bypasses += 1
    return blocks, bypasses, hooks


def main() -> int:
    try:
        if _already_shown():
            return 0
        blocks, bypasses, hooks = _summarise()
        if blocks == 0 and bypasses == 0:
            return 0
        top = ", ".join(hooks[:3]) if hooks else ""
        suffix = f" (top: {top})" if top else ""
        parts = []
        if blocks:
            parts.append(f"{blocks} block(s)")
        if bypasses:
            parts.append(f"{bypasses} bypass(es)")
        msg = "[retro] " + " and ".join(parts) + " this session" + suffix + ". Run /retro to propose upstream fixes."
        print(msg, file=sys.stderr)
        _mark_shown()
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
