#!/usr/bin/env python3
"""Block the first Edit/Write/MultiEdit per file per session until the file
was actually read or the user named the path.

Rationale: ~/.claude/rules/pre-flight.md and ~/.claude/CLAUDE.md
"Confidence" require reading every file you will modify before changing
it. The rule is enforced in prose. Agents still occasionally edit a file
on the strength of a search snippet or a memory guess. This hook turns
the prose rule into a mechanical gate.

How it works:
  1. Track per-session state at ~/.claude/cache/gateguard-state.json.
     Keys are session IDs. Values are dicts of {file_path: True} marking
     files this session has already edited.
  2. On the first Edit/Write/MultiEdit for a given file in a session, check
     the recent transcript for evidence that the file was read or named.
     Evidence is a Read call on the path, a Grep call covering the path,
     or a user message containing the path string.
  3. If evidence is found, mark the file as cleared and allow. Subsequent
     edits to the same file in this session pass through without a check.
  4. If no evidence, block with a message instructing the agent to read
     the file or cite the user message.

The hook does not run during the second edit, third edit, etc. of the same
file in a session. It only gates the first touch.

Exit 0 = allow, exit 2 = block.

Bypass:
  - Set `GATEGUARD_DISABLE=1` in the environment. Suitable for unattended
    cron-style sessions where prior reads are not possible.
  - Set `GATEGUARD_ALLOW_NEW_FILES=1` to allow Write on a path that does
    not yet exist on disk. New files cannot have been read.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

CACHE_DIR = os.path.expanduser("~/.claude/cache")
STATE_FILE = os.path.join(CACHE_DIR, "gateguard-state.json")
STATE_TTL_SECONDS = 24 * 60 * 60  # purge sessions older than 24 hours

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None

from _lib.bypass import is_bypassed  # noqa: E402



def _load_state() -> dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict[str, Any]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass


def _prune(state: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    return {
        sid: data
        for sid, data in state.items()
        if isinstance(data, dict) and now - data.get("ts", 0) < STATE_TTL_SECONDS
    }


def _transcript_evidence(transcript_path: str, file_path: str) -> bool:
    """Walk the transcript JSONL and look for evidence the file was read
    or named in a user message."""
    if not transcript_path or not os.path.exists(transcript_path):
        return False
    abs_path = os.path.abspath(file_path)
    base = os.path.basename(file_path)
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if file_path in line or abs_path in line or base in line:
                    # Found a mention. Tighten by checking the surrounding JSON
                    # if the line is JSONL. Cheap path: substring match is
                    # enough because the path appearing anywhere in the
                    # transcript (Read result, Grep result, user message) is
                    # evidence of investigation.
                    return True
    except OSError:
        return False
    return False


def _proposed_path(tool_input: dict) -> str | None:
    return tool_input.get("file_path") or tool_input.get("path")


import sys as _sys  # noqa: E402
import os as _os  # noqa: E402

_sys.path.insert(0, _os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.hook_profile import should_run  # noqa: E402
except ImportError:

    def should_run(_id: str) -> bool:
        return True


def main() -> None:
    if not should_run("gateguard-fact-force"):
        _sys.exit(0)
    if os.environ.get("GATEGUARD_DISABLE") == "1":
        sys.exit(0)
    if is_bypassed("gateguard-fact-force"):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = data.get("tool_input", data.get("input", {}))
    file_path = _proposed_path(tool_input)
    if not file_path:
        sys.exit(0)

    session_id = data.get("session_id") or "default"
    transcript_path = data.get("transcript_path", "")
    tool_name = data.get("tool_name", "")

    state = _prune(_load_state())
    session_data = state.get(session_id) or {"ts": time.time(), "files": {}}
    if not isinstance(session_data.get("files"), dict):
        session_data["files"] = {}

    # Second-and-later edits to the same file pass without check.
    if session_data["files"].get(file_path):
        sys.exit(0)

    # First touch in this session. Check for evidence.
    if _transcript_evidence(transcript_path, file_path):
        session_data["files"][file_path] = True
        session_data["ts"] = time.time()
        state[session_id] = session_data
        _save_state(state)
        sys.exit(0)

    # New-file Write is allowed when explicitly opted in, since a new file
    # cannot have been read.
    if (
        tool_name == "Write"
        and not os.path.exists(file_path)
        and os.environ.get("GATEGUARD_ALLOW_NEW_FILES") == "1"
    ):
        session_data["files"][file_path] = True
        session_data["ts"] = time.time()
        state[session_id] = session_data
        _save_state(state)
        sys.exit(0)

    print(
        f"BLOCKED: first edit on `{file_path}` requires evidence of prior read or user instruction.\n",
        file=sys.stderr,
    )
    print(
        "Read the file with the Read tool, grep for it, or cite the user message\n"
        "that names the path. This rule is mechanical because the pre-flight rule\n"
        "is mechanical: an agent that edits files it has not read produces\n"
        "wrong-direction changes.\n",
        file=sys.stderr,
    )
    print(
        "Bypass options:\n"
        "  - For one unattended session, set GATEGUARD_DISABLE=1.\n"
        "  - For new-file Writes, set GATEGUARD_ALLOW_NEW_FILES=1.",
        file=sys.stderr,
    )
    _audit(
        hook="gateguard-fact-force",
        decision="block",
        tool=tool_name,
        reason="no transcript evidence of prior read or user mention",
        file_path=file_path,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
