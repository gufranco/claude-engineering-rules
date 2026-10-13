from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _kng_support import (
    GOOD,
    HOOK,
    note,
)


def test_blocks_edit_of_an_existing_raw_source(tool_use, run_hook, vault, env):
    # Arrange
    source = vault / "raw/articles/Piece.md"
    source.write_text(GOOD)
    payload = tool_use(
        "Edit",
        {
            "file_path": str(source),
            "old_string": "timeless prose",
            "new_string": "rewritten prose",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN005")


def test_allows_creating_a_new_raw_source(tool_use, run_hook, vault, env):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": note(vault, "raw/articles/Fresh.md"), "content": GOOD}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_blocks_removal_of_a_vault_note(tool_use, run_hook, vault, env):
    # Arrange
    target = vault / "wiki/concepts/Doomed.md"
    target.write_text(GOOD)
    payload = tool_use("Bash", {"command": f"rm {target}"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN006")


def test_allows_removal_inside_the_trash_folder(tool_use, run_hook, vault, env):
    # Arrange
    payload = tool_use("Bash", {"command": f"rm {vault / '_trash/old.md'}"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_allows_removal_outside_the_vault(tool_use, run_hook, tmp_path, env):
    # Arrange
    payload = tool_use("Bash", {"command": f"rm {tmp_path / 'scratch.txt'}"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_allows_bash_without_a_removal(tool_use, run_hook, vault, env):
    # Arrange
    payload = tool_use("Bash", {"command": f"cat {vault / 'index.md'}"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_allows_removal_of_a_relative_path_outside_the_vault(
    tool_use, run_hook, vault, env
):
    # Arrange
    payload = tool_use("Bash", {"command": "rm scratch-file.txt"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_skips_flag_tokens_in_a_removal(tool_use, run_hook, vault, env):
    # Arrange
    target = vault / "wiki/concepts/Flagged.md"
    target.write_text(GOOD)
    payload = tool_use("Bash", {"command": f"rm -rf {target}"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN006")


def test_blocks_overwriting_an_existing_raw_source(tool_use, run_hook, vault, env):
    # Arrange
    source = vault / "raw/articles/Kept.md"
    source.write_text(GOOD)
    payload = tool_use(
        "Write", {"file_path": str(source), "content": GOOD + "\nmore\n"}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN005")


def test_blocks_moving_a_note_out_of_the_vault(
    tool_use, run_hook, vault, env, tmp_path
):
    # Arrange
    target = vault / "wiki/concepts/Leaving.md"
    target.write_text(GOOD)
    payload = tool_use("Bash", {"command": f"mv {target} {tmp_path}/"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN006")


@pytest.mark.parametrize(
    "command_for",
    [
        lambda vault, target: f"mv {target} {vault / '_trash'}/",
        lambda vault, target: f"mv {target} {vault / 'wiki/concepts/Renamed.md'}",
        lambda vault, target: f"rm -f /tmp/scratch.txt && cat {target}",
    ],
    ids=["retire-to-trash", "rename-inside", "read-after-unrelated-rm"],
)
def test_allows_commands_that_keep_the_note(
    tool_use, run_hook, vault, env, command_for
):
    # Arrange
    target = vault / "wiki/concepts/Staying.md"
    target.write_text(GOOD)
    payload = tool_use("Bash", {"command": command_for(vault, target)})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)
