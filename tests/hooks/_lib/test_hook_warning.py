from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.hook_warning import emit_user_notice, emit_warning  # noqa: E402


def test_a_warning_reaches_the_model_and_the_user(capsys):
    # Arrange
    text = "check-then-act sequence on line 4"

    # Act
    emit_warning(text)

    # Assert
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "systemMessage": text,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                "check-then-act sequence on line 4\n\n"
                "Investigate this advisory before you continue: read the code it "
                "names and decide whether it holds. If it holds, fix it in this "
                "change. If it does not, state in one line why it does not apply."
            ),
        },
    }


def test_a_stop_warning_names_its_event(capsys):
    # Arrange
    text = "ruff format changed 2 files"

    # Act
    emit_warning(text, event="Stop")

    # Assert
    payload = json.loads(capsys.readouterr().out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "Stop"


def test_a_notice_reaches_only_the_user(capsys):
    # Arrange
    text = "[retro] 3 blocks this session"

    # Act
    emit_user_notice(text)

    # Assert
    assert json.loads(capsys.readouterr().out) == {"systemMessage": text}
