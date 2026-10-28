#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib import knowledge_notes as kn  # noqa: E402

import os  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

ENV_VAR = "VAULT_CONTEXT_DISABLE"
MAX_CHARS = 8000
PREAMBLE = (
    "The second brain vault is at {root}.\n"
    "It is the durable store for knowledge no repository owns. Its catalog follows.\n"
    "Read a note before answering from it, and never claim it holds something it does not.\n"
    "File new knowledge with /brain capture, which owns the note grammar.\n\n"
)


MAINTENANCE_RECORD = ".maintenance.json"
MAINTENANCE_WINDOW_DAYS = 8
CAPTURE_RUN_DIR = ".claude-runs"
CAPTURE_QUEUE = "capture-queue.jsonl"


NO_RECORD_NOTICE = (
    "\n\nVault maintenance has no run record, so it is overdue. "
    "Run `python3 .ci/maintain.py` in the vault.\n"
)


def _maintenance_record(root: Path) -> tuple[dict, datetime] | None:
    path = root / MAINTENANCE_RECORD
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        stamp = record.get("ran_at", "")
        ran = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
        return None
    return record, ran


def _failed_notice(record: dict, ran: datetime) -> str:
    failed = [step for step, code in (record.get("steps") or {}).items() if code] or [
        "an unnamed step"
    ]
    return (
        f"\n\nVault maintenance last ran on {ran.date()} and failed: "
        f"{', '.join(sorted(failed))}. A failed run is not a run, so the "
        "overdue clock is not reset by it. Fix the findings, then run "
        "`python3 .ci/maintain.py` in the vault.\n"
    )


def maintenance_notice(root: Path) -> str:
    loaded = _maintenance_record(root)
    if loaded is None:
        return NO_RECORD_NOTICE
    record, ran = loaded
    if record.get("exit"):
        return _failed_notice(record, ran)
    days = (datetime.now(timezone.utc) - ran).days
    if days > MAINTENANCE_WINDOW_DAYS:
        return (
            f"\n\nVault maintenance is overdue: last run {days} days ago on "
            f"{ran.date()}. Run `python3 .ci/maintain.py` in the vault.\n"
        )
    return ""


def _pending_entry(line: str) -> dict | None:
    if not line.strip():
        return None
    try:
        entry = json.loads(line)
    except (ValueError, TypeError):
        return None
    if not isinstance(entry, dict) or entry.get("status") != "pending":
        return None
    return entry


def _pending_places(lines: list[str]) -> tuple[int, list[str]]:
    entries = [e for e in (_pending_entry(line) for line in lines) if e is not None]
    wheres = [entry.get("cwd") or "an unrecorded directory" for entry in entries]
    places = [where for i, where in enumerate(wheres) if where not in wheres[:i]]
    return len(entries), places


def pending_captures(root: Path) -> str:
    path = root / CAPTURE_RUN_DIR / CAPTURE_QUEUE
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ""

    count, places = _pending_places(lines)
    if not count:
        return ""
    noun = "capture" if count == 1 else "captures"
    verb = "is" if count == 1 else "are"
    listed = ", ".join(places[:4])
    return (
        f"\n\nThere {verb} {count} pending {noun} queued by an earlier "
        f"session, from {listed}. The queue is at {path}. Read each entry, "
        f"apply the admission bar, file what clears it, and mark every entry "
        f"filed.\n"
    )


def _index_body(root: Path) -> str | None:
    try:
        body = (root / "index.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if len(body) > MAX_CHARS:
        return body[:MAX_CHARS] + "\n\n[index truncated at 8000 characters]"
    return body


def _emit_context(context: str) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                }
            }
        )
    )


def main() -> int:
    if os.environ.get(ENV_VAR) == "1":
        return 0
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    root = kn.vault_root()
    if root is None:
        return 0
    body = _index_body(root)
    if body is None:
        return 0
    _emit_context(
        PREAMBLE.format(root=root)
        + body
        + pending_captures(root)
        + maintenance_notice(root)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
