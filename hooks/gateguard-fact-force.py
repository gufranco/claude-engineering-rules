#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

CACHE_DIR = os.path.expanduser("~/.claude/cache")
STATE_FILE = os.path.join(CACHE_DIR, "gateguard-state.json")
STATE_TTL_SECONDS = 24 * 60 * 60

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402


def _load_state() -> dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as error:
        _audit(hook="gateguard-fact-force", decision="error", reason=str(error))
        return {}


def _save_state(state: dict[str, Any]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError as error:
        _audit(hook="gateguard-fact-force", decision="error", reason=str(error))


def _prune(state: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    return {
        sid: data
        for sid, data in state.items()
        if isinstance(data, dict) and now - data.get("ts", 0) < STATE_TTL_SECONDS
    }


READ_TOOLS = frozenset({"Read"})
SEARCH_TOOLS = frozenset({"Grep", "Glob"})


def _transcript_evidence(transcript_path: str, file_path: str) -> bool:
    if not transcript_path or not os.path.exists(transcript_path):
        return False
    target = os.path.abspath(file_path)
    try:
        with open(transcript_path, encoding="utf-8") as handle:
            return any(_entry_evidence(_parse(line), target) for line in handle)
    except OSError as error:
        _audit(hook="gateguard-fact-force", decision="error", reason=str(error))
        return False


def _parse(line: str) -> dict[str, Any]:
    try:
        entry = json.loads(line)
    except ValueError:
        return {}
    return entry if isinstance(entry, dict) else {}


def _entry_evidence(entry: dict[str, Any], target: str) -> bool:
    message = entry.get("message", entry)
    if not isinstance(message, dict):
        return False
    content = message.get("content")
    if message.get("role") == "user":
        return target in _user_text(content)
    if message.get("role") == "assistant" and isinstance(content, list):
        return any(_call_reads(block, target) for block in content)
    return False


def _user_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        str(block.get("text", ""))
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def _call_reads(block: object, target: str) -> bool:
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return False
    tool_input = block.get("input")
    if not isinstance(tool_input, dict):
        return False
    if block.get("name") in READ_TOOLS:
        return os.path.abspath(str(tool_input.get("file_path", ""))) == target
    if block.get("name") in SEARCH_TOOLS:
        scope = os.path.abspath(str(tool_input.get("path") or "."))
        return target == scope or target.startswith(scope + os.sep)
    return False


def _proposed_path(tool_input: dict) -> str | None:
    return tool_input.get("file_path") or tool_input.get("path")


from _lib.hook_profile import should_run  # noqa: E402


def _should_skip() -> bool:
    if not should_run("gateguard-fact-force"):
        return True
    if os.environ.get("GATEGUARD_DISABLE") == "1":
        return True
    return is_bypassed("gateguard-fact-force")


def _record_and_allow(
    state: dict[str, Any], session_id: str, session_data: dict[str, Any], file_path: str
) -> None:
    session_data["files"][file_path] = True
    session_data["ts"] = time.time()
    state[session_id] = session_data
    _save_state(state)
    sys.exit(0)


def _new_file_allowed(tool_name: str, file_path: str) -> bool:
    return (
        tool_name == "Write"
        and not os.path.exists(file_path)
        and os.environ.get("GATEGUARD_ALLOW_NEW_FILES") == "1"
    )


def _block(tool_name: str, file_path: str) -> None:
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


def _session_entry(state: dict[str, Any], session_id: str) -> dict[str, Any]:
    session_data = state.get(session_id) or {"ts": time.time(), "files": {}}
    if not isinstance(session_data.get("files"), dict):
        session_data["files"] = {}
    return session_data


def main() -> None:
    if _should_skip():
        sys.exit(0)
    data = read_hook_payload("gateguard-fact-force")

    tool_input = data.get("tool_input", data.get("input", {}))
    file_path = _proposed_path(tool_input)
    if not file_path:
        sys.exit(0)

    session_id = data.get("session_id") or "default"
    transcript_path = data.get("transcript_path", "")
    tool_name = data.get("tool_name", "")

    state = _prune(_load_state())
    session_data = _session_entry(state, session_id)

    if session_data["files"].get(file_path):
        sys.exit(0)

    if _transcript_evidence(transcript_path, file_path) or _new_file_allowed(
        tool_name, file_path
    ):
        _record_and_allow(state, session_id, session_data, file_path)

    _block(tool_name, file_path)


if __name__ == "__main__":
    main()
