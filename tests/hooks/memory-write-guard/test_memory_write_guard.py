"""Coverage for memory-write-guard hook.

Source rule: `~/.claude/CLAUDE.md` "Knowledge Single Source of Truth" and
`~/.claude/rules/knowledge-notes.md` "Memory Compile Contract".

The guard keeps the session memory directory a generated artifact while a
vault is configured. The vault is optional and personal, so the guard must be
completely inert when `SECOND_BRAIN_VAULT` is unset or does not resolve.
"""

from __future__ import annotations

import pytest

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
    """A configured, existing vault."""
    d = tmp_path / "second-brain"
    d.mkdir()
    return {"SECOND_BRAIN_VAULT": str(d)}


def test_blocks_handwritten_memory_file_when_vault_configured(
    tool_use, assert_blocks, vault
):
    payload = tool_use("Write", {"file_path": MEMORY_FILE, "content": HANDWRITTEN})

    assert_blocks(HOOK, payload, "generated from the vault", env=vault)


def test_allows_compiled_memory_file(tool_use, assert_allows, vault):
    payload = tool_use("Write", {"file_path": MEMORY_FILE, "content": COMPILED})

    assert_allows(HOOK, payload, env=vault)


def test_allows_memory_index(tool_use, assert_allows, vault):
    payload = tool_use("Write", {"file_path": MEMORY_INDEX, "content": "- [x](x.md)"})

    assert_allows(HOOK, payload, env=vault)


def test_allows_paths_outside_the_memory_directory(tool_use, assert_allows, vault):
    payload = tool_use("Write", {"file_path": OUTSIDE_FILE, "content": HANDWRITTEN})

    assert_allows(HOOK, payload, env=vault)


def test_inert_when_vault_unset(tool_use, assert_allows):
    payload = tool_use("Write", {"file_path": MEMORY_FILE, "content": HANDWRITTEN})

    assert_allows(HOOK, payload, env={"SECOND_BRAIN_VAULT": ""})


def test_inert_when_vault_path_does_not_exist(tool_use, assert_allows, tmp_path):
    missing = str(tmp_path / "no-such-vault")
    payload = tool_use("Write", {"file_path": MEMORY_FILE, "content": HANDWRITTEN})

    assert_allows(HOOK, payload, env={"SECOND_BRAIN_VAULT": missing})


def test_blocks_edit_of_handwritten_memory_file(tool_use, assert_blocks, vault):
    payload = tool_use(
        "Edit",
        {
            "file_path": MEMORY_FILE,
            "old_string": "old",
            "new_string": "a hand written fact",
        },
    )

    assert_blocks(HOOK, payload, "generated from the vault", env=vault)


def test_bypass_env_disables_the_guard(tool_use, assert_allows, vault):
    payload = tool_use("Write", {"file_path": MEMORY_FILE, "content": HANDWRITTEN})

    assert_allows(HOOK, payload, env={**vault, "MEMORY_WRITE_GUARD_DISABLE": "1"})


def test_ignores_unrelated_tools(tool_use, assert_allows, vault):
    payload = tool_use("Bash", {"command": f"cat {MEMORY_FILE}"})

    assert_allows(HOOK, payload, env=vault)
