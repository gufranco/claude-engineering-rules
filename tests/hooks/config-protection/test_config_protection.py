"""Coverage for config-protection hook.

Source rule: `~/.claude/CLAUDE.md` "Maximum Compiler and Checker Strictness"
and `~/.claude/rules/code-style.md` "Zero Warnings".
"""

from __future__ import annotations

import pytest

HOOK = "config-protection"


@pytest.mark.parametrize(
    "file_path",
    [
        "/repo/tsconfig.json",
        "/repo/tsconfig.app.json",
        "/repo/jsconfig.json",
        "/repo/.eslintrc.json",
        "/repo/eslint.config.mjs",
        "/repo/.prettierrc",
        "/repo/biome.json",
        "/repo/ruff.toml",
        "/repo/mypy.ini",
        "/repo/pyrightconfig.json",
        "/repo/clippy.toml",
        "/repo/.golangci.yml",
        "/repo/.rubocop.yml",
        "/repo/detekt.yml",
    ],
)
def test_blocks_protected_config_writes(tool_use, assert_blocks, file_path):
    # Arrange
    payload = tool_use("Write", {"file_path": file_path, "content": "{}"})

    # Act / Assert
    assert_blocks(HOOK, payload, "weaken type or lint strictness")


def test_blocks_edit_to_protected_config(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/tsconfig.json",
            "old_string": "strict: true",
            "new_string": "strict: false",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "weaken type or lint strictness")


def test_blocks_multiedit_to_protected_config(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/.eslintrc.json",
            "edits": [{"old_string": "error", "new_string": "warn"}],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "weaken type or lint strictness")


def test_allows_unprotected_file(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Write", {"file_path": "/repo/src/index.ts", "content": "x"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_with_bypass_env(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": "/repo/tsconfig.json", "content": "{}"})

    # Act
    code, _out, _err = run_hook(HOOK, payload, env={"CONFIG_PROTECTION_DISABLE": "1"})

    # Assert
    assert code == 0


def test_allows_missing_file_path(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Write", {"content": "x"})

    # Act / Assert
    assert_allows(HOOK, payload)
