#!/usr/bin/env python3
"""Stop hook: POST a notification when Claude Code finishes a response.

Requires `CLAUDE_NOTIFY_WEBHOOK` env var (Slack or Discord compatible).
Silently exits 0 when the env var is unset, when bypass is engaged, or
when the network call fails. Never blocks the session.

Bypass channels:
    1. Env var `NOTIFY_WEBHOOK_DISABLE=1` (parent shell).
    2. File registry entry for hook `notify-webhook`.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.bypass import is_bypassed  # noqa: E402

HOOK_NAME = "notify-webhook"
ENV_DISABLE = "NOTIFY_WEBHOOK_DISABLE"
ENV_WEBHOOK = "CLAUDE_NOTIFY_WEBHOOK"
PAYLOAD = {"text": "Claude Code: Response complete", "username": "Claude Code"}
TIMEOUT_SECONDS = 3.0


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1":
        return 0
    if is_bypassed(HOOK_NAME):
        return 0
    url = os.environ.get(ENV_WEBHOOK, "").strip()
    if not url:
        return 0
    body = json.dumps(PAYLOAD).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
