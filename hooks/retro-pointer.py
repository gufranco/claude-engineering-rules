#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from collections import Counter

LOG_PATH = os.path.expanduser("~/.claude/logs/hooks.log")
TAIL_BYTES = 64 * 1024
MAX_AGE_SECONDS = 6 * 60 * 60

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_warning import emit_user_notice  # noqa: E402


def _session_id() -> str:
    return (
        os.environ.get("CLAUDE_CODE_SESSION_ID")
        or os.environ.get("CLAUDE_SESSION_ID")
        or os.environ.get("SESSION_ID")
        or ""
    )


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
                fh.readline()
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


CORRECTION_PHRASES = (
    "no, not that",
    "stop doing that",
    "don't",
    "wrong direction",
    "i said",
    "again,",
)
ERROR_MARKERS = ("ERROR:", "Error:", "Traceback", "FAILED")
TRANSCRIPT_TAIL_BYTES = 256 * 1024
TRANSCRIPT_TAIL_LINES = 200


def _read_transcript_tail(transcript_path: str) -> list[str]:
    if not transcript_path or not os.path.exists(transcript_path):
        return []
    try:
        size = os.path.getsize(transcript_path)
    except OSError:
        return []
    try:
        with open(transcript_path, "rb") as fh:
            if size > TRANSCRIPT_TAIL_BYTES:
                fh.seek(-TRANSCRIPT_TAIL_BYTES, os.SEEK_END)
                fh.readline()
            return fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _error_fragments(line: str) -> list[str]:
    fragments = (
        line.split(marker, 1)[-1][:80].strip()
        for marker in ERROR_MARKERS
        if marker in line
    )
    return [fragment for fragment in fragments if fragment]


def _patterns_from_lines(lines: list[str]) -> list[str]:
    lowered = [line.lower() for line in lines]
    user_corrections = sum(
        1 for low in lowered if any(phrase in low for phrase in CORRECTION_PHRASES)
    )
    failed_attempts = sum(
        1 for low in lowered if "blocked" in low or "exit code 2" in low
    )
    repeated_errors = Counter(
        fragment for line in lines for fragment in _error_fragments(line)
    )
    repeats = [k for k, v in repeated_errors.items() if v >= 3]
    candidates = (
        (user_corrections >= 2, f"user corrections ({user_corrections})"),
        (bool(repeats), f"repeated error: `{repeats[0][:40]}`" if repeats else ""),
        (failed_attempts >= 4, f"hook blocks ({failed_attempts})"),
    )
    return [text for hit, text in candidates if hit]


def _transcript_patterns(transcript_path: str) -> list[str]:
    tail = _read_transcript_tail(transcript_path)
    return _patterns_from_lines(tail[-TRANSCRIPT_TAIL_LINES:])


from _lib.hook_profile import should_run  # noqa: E402


def _disabled() -> bool:
    return (
        os.environ.get("RETRO_POINTER_DISABLE") == "1"
        or is_bypassed("retro-pointer")
        or not should_run("retro-pointer")
    )


def _payload_transcript_path() -> str:
    try:
        data = json.load(sys.stdin)
        return data.get("transcript_path", "")
    except (ValueError, json.JSONDecodeError, OSError) as error:
        sys.stderr.write(f"retro-pointer: unreadable payload: {error}\n")
        return ""


def _block_notices(blocks: int, bypasses: int, hooks: list[str]) -> list[str]:
    counts = ((blocks, f"{blocks} block(s)"), (bypasses, f"{bypasses} bypass(es)"))
    parts = [text for count, text in counts if count]
    if not parts:
        return []
    top = ", ".join(hooks[:3]) if hooks else ""
    suffix = f" (top: {top})" if top else ""
    return [
        "[retro] "
        + " and ".join(parts)
        + " this session"
        + suffix
        + ". Run /retro to propose upstream fixes."
    ]


def _instinct_notices(instinct_patterns: list[str]) -> list[str]:
    if not instinct_patterns:
        return []
    return [
        "[retro instinct] session patterns worth capturing: "
        + "; ".join(instinct_patterns)
        + ". Run /retro instinct to record."
    ]


def _report() -> int:
    if _already_shown():
        return 0
    blocks, bypasses, hooks = _summarise()
    instinct_patterns = _transcript_patterns(_payload_transcript_path())
    if blocks == 0 and bypasses == 0 and not instinct_patterns:
        return 0
    notices = [
        *_block_notices(blocks, bypasses, hooks),
        *_instinct_notices(instinct_patterns),
    ]
    if notices:
        emit_user_notice("\n".join(notices))
    _mark_shown()
    return 0


def main() -> int:
    if _disabled():
        sys.exit(0)
    try:
        return _report()
    except Exception as error:
        sys.stderr.write(f"retro-pointer: summary failed: {error}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
