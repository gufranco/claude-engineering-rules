from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.settings_hygiene_structure import check_structure  # noqa: E402

VALID_COMMAND = {"type": "command", "command": "python3 hook.py"}


@pytest.mark.parametrize("scalar", ["text", 3, None])
def test_a_non_object_document_has_no_structure_findings(scalar: object) -> None:
    # Arrange
    parsed = [scalar]

    # Act
    findings = check_structure(parsed)

    # Assert
    assert findings == []


def test_a_well_formed_document_has_no_findings() -> None:
    # Arrange
    parsed = {
        "hooks": {"Stop": [{"hooks": [VALID_COMMAND]}, {"matcher": "Bash"}]},
        "mcpServers": {"local": {"command": "srv"}, "remote": {"url": "https://x"}},
    }

    # Act
    findings = check_structure(parsed)

    # Assert
    assert findings == []


def test_hooks_that_are_not_an_object_are_reported() -> None:
    # Arrange
    parsed = {"hooks": []}

    # Act
    findings = check_structure(parsed)

    # Assert
    assert findings == ["`hooks` must be an object keyed by event name."]


def test_event_level_problems_are_reported_in_order() -> None:
    # Arrange
    parsed = {"hooks": {"Nope": [], "Stop": {}, "SessionStart": ["x"]}}

    # Act
    findings = check_structure(parsed)

    # Assert
    assert findings == [
        "unknown hook event `Nope`. Known events: Notification, PostCompact, "
        "PostToolUse, PreCompact, PreToolUse, SessionEnd, SessionStart, Stop, "
        "SubagentStop, UserPromptSubmit.",
        "hooks.Stop must be a list of matcher groups.",
        "hooks.SessionStart[0] must be an object.",
    ]


def test_command_level_problems_are_reported_in_order() -> None:
    # Arrange
    parsed = {
        "hooks": {
            "Stop": [
                {"hooks": "x"},
                {"hooks": ["x", {"type": "prompt"}]},
            ]
        }
    }

    # Act
    findings = check_structure(parsed)

    # Assert
    assert findings == [
        "hooks.Stop[0].hooks must be a list.",
        "hooks.Stop[1].hooks[0] must be an object.",
        "hooks.Stop[1].hooks[1].type must be `command`, got `prompt`.",
        "hooks.Stop[1].hooks[1].command must be a non-empty string.",
    ]


def test_mcp_server_problems_are_reported_in_order() -> None:
    # Arrange
    parsed = {
        "mcpServers": {
            "a": "x",
            "b": {"command": "c", "url": "u"},
            "c": {},
        }
    }

    # Act
    findings = check_structure(parsed)

    # Assert
    assert findings == [
        "mcpServers.a must be an object.",
        "mcpServers.b has both `command` and `url`. Pick one transport.",
        "mcpServers.c needs either `command` (stdio) or `url` (http).",
    ]


def test_mcp_servers_that_are_not_an_object_are_reported() -> None:
    # Arrange
    parsed = {"mcpServers": ["x"]}

    # Act
    findings = check_structure(parsed)

    # Assert
    assert findings == ["`mcpServers` must be an object keyed by server name."]
