from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import NoReturn

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[3] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.dangerous_command_input import read_command  # noqa: E402


class Refused(Exception):
    pass


def _refuse(problem: str) -> NoReturn:
    raise Refused(problem)


def test_read_command_returns_the_bash_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    payload = {"tool_input": {"command": "ls -la"}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    # Act
    result = read_command(_refuse)

    # Assert
    assert result == "ls -la"


@pytest.mark.parametrize(
    ("raw", "problem"),
    [
        ("not json", "stdin is not UTF-8 JSON (JSONDecodeError)"),
        ("[]", "the payload is not a JSON object"),
        ('{"tool_input": 1}', "tool_input is not an object"),
        ('{"tool_input": {"command": 1}}', "tool_input.command is not a string"),
    ],
)
def test_read_command_refuses_malformed_payloads(
    monkeypatch: pytest.MonkeyPatch, raw: str, problem: str
) -> None:
    # Arrange
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))

    # Act
    with pytest.raises(Refused) as caught:
        read_command(_refuse)

    # Assert
    assert str(caught.value) == problem
