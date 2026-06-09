#!/usr/bin/env python3
"""PostToolUse Edit/Write/MultiEdit hook: append edited path to batch file.

The companion `stop-format-typecheck.py` consumes the batch on Stop, dedupes,
formats every file once, runs the type checker once, then clears the batch.

Batch file path: `$CLAUDE_FORMATTER_BATCH` if set, else
`~/.claude/cache/edit-batch.txt`.

Bypass channels:
    1. Env var `SMART_FORMATTER_DISABLE=1` (parent shell).
    2. File registry entry for hook `smart-formatter`.
    3. Profile gate via `hook_profile.should_run`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.bypass import is_bypassed  # noqa: E402

try:
    from _lib.hook_profile import should_run
except Exception:  # noqa: BLE001

    def should_run(_name: str) -> bool:  # type: ignore[override]
        return True


HOOK_NAME = "smart-formatter"
ENV_DISABLE = "SMART_FORMATTER_DISABLE"
ENV_BATCH = "CLAUDE_FORMATTER_BATCH"
DEFAULT_BATCH = Path.home() / ".claude" / "cache" / "edit-batch.txt"
EXCLUDED_FRAGMENTS = (
    "/.claude/cache/",
    "/node_modules/",
    "/.git/",
    "/dist/",
    "/build/",
)


def _batch_path() -> Path:
    override = os.environ.get(ENV_BATCH)
    return Path(override) if override else DEFAULT_BATCH


def _read_file_path() -> str:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    tool_input = data.get("tool_input") or data.get("input") or {}
    if not isinstance(tool_input, dict):
        return ""
    value = tool_input.get("file_path", "")
    return value if isinstance(value, str) else ""


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1":
        return 0
    if is_bypassed(HOOK_NAME):
        return 0
    if not should_run(HOOK_NAME):
        return 0
    file_path = _read_file_path()
    if not file_path:
        return 0
    path = Path(file_path)
    if not path.is_file():
        return 0
    normalized = f"/{path.as_posix().lstrip('/')}"
    for fragment in EXCLUDED_FRAGMENTS:
        if fragment in normalized:
            return 0
    batch = _batch_path()
    batch.parent.mkdir(parents=True, exist_ok=True)
    with batch.open("a", encoding="utf-8") as fh:
        fh.write(file_path + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
