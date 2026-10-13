from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _kng_support import (
    GOOD,
    HOOK,
    note,
)


def test_allows_compliant_note(tool_use, run_hook, vault, env):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Idea.md"), "content": GOOD}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_allows_path_outside_the_vault(tool_use, run_hook, tmp_path, env):
    # Arrange
    outside = tmp_path / "elsewhere.md"
    payload = tool_use(
        "Write", {"file_path": str(outside), "content": "no frontmatter here"}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_allows_non_markdown_inside_the_vault(tool_use, run_hook, vault, env):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/data.json"), "content": "{}"}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "rel", ["templates/entity.md", "_trash/old.md", ".obsidian/app.json"]
)
def test_allows_exempt_directories(tool_use, run_hook, vault, env, rel):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": note(vault, rel), "content": "anything at all"}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_allows_vault_root_manual_without_frontmatter(tool_use, run_hook, vault, env):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": note(vault, "CLAUDE.md"), "content": "# Manual\n"}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_blocks_missing_frontmatter(tool_use, run_hook, vault, env):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": note(vault, "wiki/concepts/Bare.md"),
            "content": "# Bare\n\nno frontmatter\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN001")


def test_blocks_missing_required_key(tool_use, run_hook, vault, env):
    # Arrange
    content = GOOD.replace("ai-first: true\n", "")
    payload = tool_use(
        "Write",
        {"file_path": note(vault, "wiki/concepts/Partial.md"), "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "ai-first")


def test_blocks_missing_preamble(tool_use, run_hook, vault, env):
    # Arrange
    content = GOOD.replace("## For future agent", "## Summary")
    payload = tool_use(
        "Write",
        {"file_path": note(vault, "wiki/concepts/NoPreamble.md"), "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN002")


def test_blocks_undated_volatile_claim(tool_use, run_hook, vault, env):
    # Arrange
    content = GOOD + "\nThe pipeline has 13 open deals.\n"
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Rot.md"), "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN003")


def test_allows_stamped_volatile_claim(tool_use, run_hook, vault, env):
    # Arrange
    content = GOOD + "\nThe pipeline has 13 open deals (as of 2026-08-18).\n"
    payload = tool_use(
        "Write",
        {"file_path": note(vault, "wiki/concepts/Stamped.md"), "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_allows_volatile_claim_in_dated_container(tool_use, run_hook, vault, env):
    # Arrange
    content = GOOD + "\nThe pipeline has 13 open deals.\n"
    payload = tool_use(
        "Write", {"file_path": note(vault, "daily/2026-08-18.md"), "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_allows_volatile_claim_under_dated_heading(tool_use, run_hook, vault, env):
    # Arrange
    content = GOOD + "\n## 2026-08-18\n\nThe pipeline has 13 open deals.\n"
    payload = tool_use(
        "Write",
        {"file_path": note(vault, "wiki/concepts/Snapshot.md"), "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_ignores_volatile_claim_inside_a_code_fence(tool_use, run_hook, vault, env):
    # Arrange
    content = GOOD + "\n```\nThe pipeline has 13 open deals.\n```\n"
    payload = tool_use(
        "Write",
        {"file_path": note(vault, "wiki/concepts/Fenced.md"), "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_blocks_wikilink_to_a_note_that_does_not_exist(tool_use, run_hook, vault, env):
    # Arrange
    content = GOOD + "\nSee [[Nonexistent Person]] for context.\n"
    payload = tool_use(
        "Write",
        {"file_path": note(vault, "wiki/concepts/Linker.md"), "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN004")


def test_allows_wikilink_to_an_existing_note(tool_use, run_hook, vault, env):
    # Arrange
    (vault / "wiki/entities/Real Person.md").write_text(GOOD)
    content = GOOD + "\nSee [[Real Person]] for context.\n"
    payload = tool_use(
        "Write",
        {"file_path": note(vault, "wiki/concepts/Linker.md"), "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_allows_wikilink_marked_tbd(tool_use, run_hook, vault, env):
    # Arrange
    content = GOOD + "\nSee [[Future Note]], TBD until it is written.\n"
    payload = tool_use(
        "Write",
        {"file_path": note(vault, "wiki/concepts/Pending.md"), "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)
