#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
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
BATCH_DIR = Path.home() / ".claude" / "cache"
EXCLUDED_FRAGMENTS = (
    "/.claude/cache/",
    "/node_modules/",
    "/.git/",
    "/dist/",
    "/build/",
)


def _batch_path(session_id: str) -> Path:
    override = os.environ.get(ENV_BATCH)
    if override:
        return Path(override)
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id) or "default"
    return BATCH_DIR / f"edit-batch-{safe}.txt"


def _read_payload() -> tuple[str, str]:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError) as error:
        sys.stderr.write(f"{HOOK_NAME}: unreadable payload: {error}\n")
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    tool_input = data.get("tool_input") or data.get("input") or {}
    value = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
    session = data.get("session_id") or ""
    return (value if isinstance(value, str) else ""), str(session)


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1":
        return 0
    if is_bypassed(HOOK_NAME):
        return 0
    if not should_run(HOOK_NAME):
        return 0
    file_path, session_id = _read_payload()
    if not file_path:
        return 0
    path = Path(file_path)
    if not path.is_file():
        return 0
    normalized = f"/{path.as_posix().lstrip('/')}"
    for fragment in EXCLUDED_FRAGMENTS:
        if fragment in normalized:
            return 0
    batch = _batch_path(session_id)
    batch.parent.mkdir(parents=True, exist_ok=True)
    with batch.open("a", encoding="utf-8") as fh:
        fh.write(file_path + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
