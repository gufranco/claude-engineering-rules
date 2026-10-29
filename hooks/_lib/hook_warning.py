from __future__ import annotations

import json
import sys

INVESTIGATE = (
    "Investigate this advisory before you continue: read the code it names and "
    "decide whether it holds. If it holds, fix it in this change. If it does "
    "not, state in one line why it does not apply."
)


def emit_warning(text: str, event: str = "PreToolUse") -> None:
    payload = {
        "systemMessage": text,
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": f"{text}\n\n{INVESTIGATE}",
        },
    }
    sys.stdout.write(json.dumps(payload))


def emit_user_notice(text: str) -> None:
    sys.stdout.write(json.dumps({"systemMessage": text}))
