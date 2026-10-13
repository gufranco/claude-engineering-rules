from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "config-protection"


@pytest.mark.parametrize(
    "path",
    [
        "/home/u/.claude/.bypass-state.json",
        "/repo/eslint.config.mts",
        "/repo/prettier.config.ts",
        "/repo/.prettierrc.toml",
    ],
)
def test_always_protected_files_block(tool_use, run_hook, path):
    # Arrange
    payload = tool_use("Write", {"file_path": path, "content": "{}"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


@pytest.mark.parametrize(
    ("path", "content"),
    [
        ("/repo/pyproject.toml", '[tool.ruff.lint]\nignore = ["E501"]\n'),
        ("/repo/pyproject.toml", "[tool.mypy]\nstrict = false\n"),
        ("/repo/setup.cfg", "[flake8]\nextend-ignore = E203\n"),
        ("/repo/.flake8", "[flake8]\nmax-line-length = 200\n"),
    ],
)
def test_lint_and_type_sections_in_mixed_files_block(tool_use, run_hook, path, content):
    # Arrange
    payload = tool_use(
        "Edit", {"file_path": path, "old_string": "x", "new_string": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_a_dependency_change_in_pyproject_passes(tool_use, run_hook):
    # Arrange
    content = '[project]\ndependencies = ["httpx==0.28.1"]\n'
    payload = tool_use(
        "Edit",
        {"file_path": "/repo/pyproject.toml", "old_string": "x", "new_string": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
