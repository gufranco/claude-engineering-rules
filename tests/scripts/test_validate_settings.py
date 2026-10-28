from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-settings.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_settings", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_settings = _load()


def _hooks(matcher: str) -> dict[str, object]:
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": matcher,
                    "hooks": [{"type": "command", "command": "echo ok"}],
                }
            ]
        }
    }


@pytest.mark.parametrize(
    "matcher",
    [
        "Bash",
        "mcp__.*",
        "mcp__linear-acme__save_issue|mcp__linear-acme__save_comment",
    ],
)
def test_known_tools_and_exact_mcp_tool_names_are_valid_matchers(matcher):
    # Arrange
    data = _hooks(matcher)

    # Act
    result = validate_settings.validate_hooks(data)

    # Assert
    assert result == []


@pytest.mark.parametrize(
    ("matcher", "token"),
    [
        ("Bsh", "Bsh"),
        ("mcp__linear[^_]*__save_issue", "mcp__linear[^_]*__save_issue"),
        ("mcp__server", "mcp__server"),
    ],
)
def test_unknown_matchers_are_reported(matcher, token):
    # Arrange
    data = _hooks(matcher)

    # Act
    result = validate_settings.validate_hooks(data)

    # Assert
    assert result == [f"  Unknown hook matcher '{token}' in PreToolUse"]
