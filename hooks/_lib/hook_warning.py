from __future__ import annotations

import json
import sys


def emit_warning(text: str, event: str = "PreToolUse") -> None:
    payload = {
        "systemMessage": text,
        "hookSpecificOutput": {"hookEventName": event, "additionalContext": text},
    }
    sys.stdout.write(json.dumps(payload))


def emit_user_notice(text: str) -> None:
    sys.stdout.write(json.dumps({"systemMessage": text}))
