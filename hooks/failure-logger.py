#!/usr/bin/env python3
"""failure-logger.py — Log failed tool calls to a JSONL file.

PostToolUseFailure hook. Reads tool failure data from stdin JSON and
appends a structured record to ~/.claude/telemetry/failures.jsonl.
"""

import json
import os
import sys
from datetime import datetime, timezone

LOG_DIR = os.path.join(os.path.expanduser("~"), ".claude", "telemetry")
LOG_FILE = os.path.join(LOG_DIR, "failures.jsonl")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = data.get("tool_name", "unknown")
    tool_input = data.get("input", {})
    error = data.get("error", data.get("output", ""))

    record = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool_name": tool_name,
        "error": str(error)[:500],
    }

    file_path = tool_input.get("file_path", tool_input.get("path"))
    if file_path:
        record["file_path"] = file_path

    command = tool_input.get("command")
    if command:
        record["command"] = command[:200]

    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
