from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _icl_support import (
    CONFIG_TEXT,
    GIT_ENV,
    HOOK,
    make_repo,
)


def test_allows_config_paths_inside_the_second_brain_vault(
    tool_use, run_hook, tmp_path
):
    # Arrange
    vault = tmp_path / "vault" / "wiki" / "concepts"
    vault.mkdir(parents=True)
    target = vault / "Tooling.md"
    payload = tool_use(
        "Write",
        {
            "file_path": str(target),
            "content": "MCP servers load from ~/.claude.json, not ~/.claude/settings.json.\n",
        },
    )

    # Act
    result = run_hook(
        HOOK, payload, env={"SECOND_BRAIN_VAULT": str(tmp_path / "vault")}
    )

    # Assert
    assert_allowed(result)


def test_still_blocks_config_paths_outside_the_vault(tool_use, run_hook, tmp_path):
    # Arrange
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "project" / "NOTES.md"
    outside.parent.mkdir()
    payload = tool_use(
        "Write",
        {
            "file_path": str(outside),
            "content": "MCP servers load from ~/.claude.json, not ~/.claude/settings.json.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"SECOND_BRAIN_VAULT": str(vault)})

    # Assert
    assert_blocked(
        result,
        "Blocked: internal Claude config or templated scaffolding leaking into external output.",
    )


def test_allows_config_paths_in_the_local_workspace(tool_use, run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path)
    target = repo / "docs" / "PROMPT.md"
    payload = tool_use("Write", {"file_path": str(target), "content": CONFIG_TEXT})

    # Act
    result = run_hook(HOOK, payload, env=GIT_ENV)

    # Assert
    assert_allowed(result)


def test_still_blocks_config_paths_in_project_owned_docs(tool_use, run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "index.md").write_text("# Project docs\n")
    target = repo / "docs" / "guide.md"
    payload = tool_use("Write", {"file_path": str(target), "content": CONFIG_TEXT})

    # Act
    result = run_hook(HOOK, payload, env=GIT_ENV)

    # Assert
    assert_blocked(
        result,
        "Blocked: internal Claude config or templated scaffolding leaking into external output.",
    )
