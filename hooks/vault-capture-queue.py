#!/usr/bin/env python3
"""Stop hook that queues durable facts for the next session to file.

A turn that corrected a belief or uncovered a cause usually produces knowledge
no repository owns, and today that knowledge survives only if someone
remembers to file it. This closes the gap without asking anyone to remember:
at the end of a turn it decides whether something worth keeping happened and,
when it did, appends one line to a queue the next session drains.

What it deliberately does not do is write the note. A hook is a process, not a
model: it can see that a correction-shaped sentence appeared and it cannot tell
a durable lesson from an aside. Writing on that basis would file inference as
fact, which is the failure the note specification exists to prevent. The
judgement stays with a model that has the session in front of it, and the only
thing automated here is remembering.

Safety properties, all load-bearing:

  - starts no process and holds no tool surface
  - writes exactly one file, inside the vault run directory, append only
  - never touches a note, so a false positive costs a queue line and nothing else
  - one entry per session per cooldown window, tracked in a sentinel file
  - a session spent editing the vault is skipped, having no outside work to file
  - every failure path returns zero, because a capture must never fail a turn

Opt-out: VAULT_CAPTURE_QUEUE_DISABLE=1, or the bypass registry.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))

try:
    from _lib.bypass import is_bypassed
except ImportError:

    def is_bypassed(_name: str) -> bool:
        return False


try:
    from _lib.hook_profile import should_run
except ImportError:

    def should_run(_id: str) -> bool:
        return True


HOOK_ID = "vault-capture-queue"
COOLDOWN_SECONDS = 20 * 60
TAIL_BYTES = 256 * 1024
TAIL_LINES = 400
RUN_DIR = ".claude-runs"
QUEUE_NAME = "capture-queue.jsonl"

CORRECTION_MARKERS = (
    "no, not that",
    "stop doing that",
    "that is wrong",
    "that's wrong",
    "wrong direction",
    "i said",
    "never do",
    "nao e isso",
    "nao faca",
    "na verdade",
    "esta errado",
    "ta errado",
    "pare de",
    "tome cuidado",
)

DISCOVERY_MARKERS = (
    "turns out",
    "root cause",
    "the cause was",
    "the actual cause",
    "which is why",
    "the reason it",
    "silently",
    "reports success",
    "false positive",
)


def _session_id() -> str:
    return (
        os.environ.get("CLAUDE_CODE_SESSION_ID")
        or os.environ.get("CLAUDE_SESSION_ID")
        or os.environ.get("SESSION_ID")
        or ""
    )


def _vault_root() -> str:
    root = os.environ.get("SECOND_BRAIN_VAULT", "")
    root = os.path.expanduser(root) if root else ""
    return root if root and os.path.isdir(root) else ""


def _sentinel_path(session: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in session or "none")
    return os.path.join(tempfile.gettempdir(), f"claude-capture-queue-{safe}.stamp")


def _cooling_down(session: str) -> bool:
    try:
        with open(_sentinel_path(session), encoding="utf-8") as fh:
            last = float(fh.read().strip())
    except (OSError, ValueError):
        return False
    return (time.time() - last) < COOLDOWN_SECONDS


def _stamp(session: str) -> None:
    try:
        with open(_sentinel_path(session), "w", encoding="utf-8") as fh:
            fh.write(str(time.time()))
    except OSError:
        return


def _tail(path: str) -> list[str]:
    if not path or not os.path.exists(path):
        return []
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(-TAIL_BYTES, os.SEEK_END)
                fh.readline()
            body = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    return body.splitlines()[-TAIL_LINES:]


def _signals(lines: list[str]) -> list[str]:
    corrections = 0
    discoveries = 0
    for line in lines:
        low = line.lower()
        if any(marker in low for marker in CORRECTION_MARKERS):
            corrections += 1
        if any(marker in low for marker in DISCOVERY_MARKERS):
            discoveries += 1

    found: list[str] = []
    if corrections >= 1:
        found.append(f"correction:{corrections}")
    if discoveries >= 2:
        found.append(f"discovery:{discoveries}")
    return found


def _enqueue(root: str, entry: dict) -> bool:
    directory = os.path.join(root, RUN_DIR)
    try:
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, QUEUE_NAME), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True


def main() -> int:
    if os.environ.get("VAULT_CAPTURE_QUEUE_DISABLE") == "1":
        return 0
    if is_bypassed(HOOK_ID) or not should_run(HOOK_ID):
        return 0

    root = _vault_root()
    if not root:
        return 0

    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(data, dict):
        return 0

    transcript = data.get("transcript_path", "") or ""
    cwd = data.get("cwd", "") or os.getcwd()

    try:
        if os.path.realpath(cwd) == os.path.realpath(root):
            return 0
    except OSError:
        return 0

    signals = _signals(_tail(transcript))
    if not signals:
        return 0

    session = data.get("session_id") or _session_id()
    if _cooling_down(session):
        return 0

    _stamp(session)
    _enqueue(
        root,
        {
            "ts": int(time.time()),
            "status": "pending",
            "session": session,
            "cwd": cwd,
            "transcript": transcript,
            "signals": signals,
        },
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
