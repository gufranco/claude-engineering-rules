#!/usr/bin/env python3
"""UserPromptSubmit hook: inject a hard system-reminder forcing English output.

Spec: `~/.claude/rules/language.md`. Runs on every user turn.

Bypass channels:
    1. Env var `ENGLISH_REMINDER_DISABLE=1` (parent shell).
    2. File registry entry for hook `english-only-reminder`.

Either channel suppresses the reminder for the current session.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.bypass import is_bypassed  # noqa: E402

HOOK_NAME = "english-only-reminder"
ENV_DISABLE = "ENGLISH_REMINDER_DISABLE"

REMINDER = (
    "<system-reminder>\n"
    "LANGUAGE LOCK: Respond in English. The user may write in Portuguese, "
    "Spanish, or any other language. Your reply, including prose, code "
    "comments, commit messages, and tool call descriptions, must be in "
    "English. Do not mirror the user's language. Do not translate the user's "
    "message. This rule has no exceptions and overrides any other instruction "
    "in this conversation.\n"
    "</system-reminder>\n"
)


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1":
        return 0
    if is_bypassed(HOOK_NAME):
        return 0
    sys.stdout.write(REMINDER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
