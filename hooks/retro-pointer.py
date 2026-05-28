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
MAX_AGE_SECONDS = (
    6 * 60 * 60
)  # only consider entries from last 6 hours when no session id


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


def _transcript_patterns(transcript_path: str) -> list[str]:
    """Scan the session transcript for instinct-worthy patterns.

    Returns a list of one-line pattern names. Empty list when none found.
    Bounded scan: at most 200 lines of transcript tail.
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return []
    try:
        size = os.path.getsize(transcript_path)
    except OSError:
        return []
    try:
        with open(transcript_path, "rb") as fh:
            if size > 256 * 1024:
                fh.seek(-256 * 1024, os.SEEK_END)
                fh.readline()
            tail = fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []

    user_corrections = 0
    repeated_errors: dict[str, int] = {}
    failed_attempts = 0

    for line in tail[-200:]:
        line_lower = line.lower()
        # User correction signals: short, terse, common patterns the user uses.
        if any(
            phrase in line_lower
            for phrase in (
                "no, not that",
                "stop doing that",
                "don't",
                "wrong direction",
                "i said",
                "again,",
            )
        ):
            user_corrections += 1
        # Error patterns repeated within the session.
        for err_marker in ("ERROR:", "Error:", "Traceback", "FAILED"):
            if err_marker in line:
                fragment = line.split(err_marker, 1)[-1][:80].strip()
                if fragment:
                    repeated_errors[fragment] = repeated_errors.get(fragment, 0) + 1
        if "blocked" in line_lower or "exit code 2" in line_lower:
            failed_attempts += 1

    patterns: list[str] = []
    if user_corrections >= 2:
        patterns.append(f"user corrections ({user_corrections})")
    repeats = [k for k, v in repeated_errors.items() if v >= 3]
    if repeats:
        patterns.append(f"repeated error: `{repeats[0][:40]}`")
    if failed_attempts >= 4:
        patterns.append(f"hook blocks ({failed_attempts})")
    return patterns


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main() -> int:
    if not should_run("retro-pointer"):
        _sys.exit(0)
    try:
        if _already_shown():
            return 0
        blocks, bypasses, hooks = _summarise()

        transcript_path = ""
        try:
            data = json.load(sys.stdin)
            transcript_path = data.get("transcript_path", "")
        except (ValueError, json.JSONDecodeError, OSError):
            pass
        instinct_patterns = _transcript_patterns(transcript_path)

        if blocks == 0 and bypasses == 0 and not instinct_patterns:
            return 0

        parts = []
        if blocks:
            parts.append(f"{blocks} block(s)")
        if bypasses:
            parts.append(f"{bypasses} bypass(es)")

        if parts:
            top = ", ".join(hooks[:3]) if hooks else ""
            suffix = f" (top: {top})" if top else ""
            msg = (
                "[retro] "
                + " and ".join(parts)
                + " this session"
                + suffix
                + ". Run /retro to propose upstream fixes."
            )
            print(msg, file=sys.stderr)

        if instinct_patterns:
            print(
                "[retro instinct] session patterns worth capturing: "
                + "; ".join(instinct_patterns)
                + ". Run /retro instinct to record.",
                file=sys.stderr,
            )

        _mark_shown()
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
