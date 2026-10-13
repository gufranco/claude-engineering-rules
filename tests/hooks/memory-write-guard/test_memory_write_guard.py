from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "memory-write-guard"

MEMORY_FILE = "/Users/someone/.claude/projects/-Users-someone/memory/feedback_x.md"
MEMORY_INDEX = "/Users/someone/.claude/projects/-Users-someone/memory/MEMORY.md"
OUTSIDE_FILE = "/Users/someone/code/project/src/feedback_x.md"

HANDWRITTEN = "---\nname: x\ntype: feedback\n---\n\nA fact with no provenance.\n"
COMPILED = (
    "---\nname: x\nmetadata:\n  generated_from: wiki/concepts/X.md\n---\n\nA fact.\n"
)


@pytest.fixture
def vault(tmp_path):
    d = tmp_path / "second-brain"
    d.mkdir()
    return {"SECOND_BRAIN_VAULT": str(d)}


def test_blocks_handwritten_memory_file_when_vault_configured(
    tool_use, run_hook, vault
):
    # Arrange
    payload = tool_use("Write", {"file_path": MEMORY_FILE, "content": HANDWRITTEN})

    # Act
    result = run_hook(HOOK, payload, env=vault)

    # Assert
    assert_blocked(result, "generated from the vault")


def test_a_write_carrying_the_compile_marker_is_still_blocked(
    tool_use, run_hook, vault
):
    # Arrange
    payload = tool_use("Write", {"file_path": MEMORY_FILE, "content": COMPILED})

    # Act
    result = run_hook(HOOK, payload, env=vault)

    # Assert
    assert_blocked(result, "generated from the vault")


def test_allows_memory_index(tool_use, run_hook, vault):
    # Arrange
    payload = tool_use("Write", {"file_path": MEMORY_INDEX, "content": "- [x](x.md)"})

    # Act
    result = run_hook(HOOK, payload, env=vault)

    # Assert
    assert_allowed(result)


def test_allows_paths_outside_the_memory_directory(tool_use, run_hook, vault):
    # Arrange
    payload = tool_use("Write", {"file_path": OUTSIDE_FILE, "content": HANDWRITTEN})

    # Act
    result = run_hook(HOOK, payload, env=vault)

    # Assert
    assert_allowed(result)


def test_inert_when_vault_unset(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": MEMORY_FILE, "content": HANDWRITTEN})

    # Act
    result = run_hook(HOOK, payload, env={"SECOND_BRAIN_VAULT": ""})

    # Assert
    assert_allowed(result)


def test_inert_when_vault_path_does_not_exist(tool_use, run_hook, tmp_path):
    # Arrange
    missing = str(tmp_path / "no-such-vault")
    payload = tool_use("Write", {"file_path": MEMORY_FILE, "content": HANDWRITTEN})

    # Act
    result = run_hook(HOOK, payload, env={"SECOND_BRAIN_VAULT": missing})

    # Assert
    assert_allowed(result)


def test_blocks_edit_of_handwritten_memory_file(tool_use, run_hook, vault):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": MEMORY_FILE,
            "old_string": "old",
            "new_string": "a hand written fact",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=vault)

    # Assert
    assert_blocked(result, "generated from the vault")


def test_bypass_env_disables_the_guard(tool_use, run_hook, vault):
    # Arrange
    payload = tool_use("Write", {"file_path": MEMORY_FILE, "content": HANDWRITTEN})

    # Act
    result = run_hook(HOOK, payload, env={**vault, "MEMORY_WRITE_GUARD_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_ignores_unrelated_tools(tool_use, run_hook, vault):
    # Arrange
    payload = tool_use("Bash", {"command": f"cat {MEMORY_FILE}"})

    # Act
    result = run_hook(HOOK, payload, env=vault)

    # Assert
    assert_allowed(result)


GENERATED_INDEX = (
    "# Memory\n\nEverything below this line is generated from the vault.\n\n"
    "## Compiled from the vault\n\n- [A](a.md): a fact\n"
)


def _index(tmp_path):
    memory = tmp_path / ".claude" / "projects" / "p" / "memory"
    memory.mkdir(parents=True)
    index = memory / "MEMORY.md"
    index.write_text(GENERATED_INDEX, encoding="utf-8")
    return index


def test_an_edit_inside_the_compiled_index_block_is_blocked(
    tool_use, run_hook, vault, tmp_path
):
    # Arrange
    index = _index(tmp_path)
    payload = tool_use(
        "Edit",
        {
            "file_path": str(index),
            "old_string": "- [A](a.md): a fact",
            "new_string": "- [A](a.md): a fact\n- [B](b.md): hand added",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=vault)

    # Assert
    assert_blocked(result, "generated from the vault")


def test_an_edit_above_the_compiled_index_block_is_allowed(
    tool_use, run_hook, vault, tmp_path
):
    # Arrange
    index = _index(tmp_path)
    payload = tool_use(
        "Edit",
        {
            "file_path": str(index),
            "old_string": "# Memory",
            "new_string": "# Memory index",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=vault)

    # Assert
    assert_allowed(result)
