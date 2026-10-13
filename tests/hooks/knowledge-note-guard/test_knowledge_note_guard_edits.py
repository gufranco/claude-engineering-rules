from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _kng_support import (
    GOOD,
    HOOK,
    LEGACY,
    note,
)


def test_edit_composes_the_post_edit_text(tool_use, run_hook, vault, env):
    # Arrange
    target = vault / "wiki/concepts/Growing.md"
    target.write_text(GOOD)
    payload = tool_use(
        "Edit",
        {
            "file_path": str(target),
            "old_string": "Some timeless prose about the idea.",
            "new_string": "The backlog has 42 open tasks.",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN003")


def test_a_note_declared_timeless_may_state_undated_quantities(
    tool_use, run_hook, vault, env
):
    # Arrange
    content = GOOD.replace(
        "ai-first: true\n", "ai-first: true\nfreshness: timeless\n"
    ).replace(
        "Some timeless prose about the idea.", "The memory map has 22 rows of cells."
    )
    payload = tool_use(
        "Write", {"file_path": note(vault, "wiki/concepts/Rom.md"), "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_an_edit_is_judged_on_what_it_adds_not_on_older_lines(
    tool_use, run_hook, vault, env
):
    # Arrange
    target = vault / "wiki/concepts/Legacy.md"
    target.write_text(LEGACY)
    payload = tool_use(
        "Edit",
        {
            "file_path": str(target),
            "old_string": "Some timeless prose about the idea.",
            "new_string": "Some timeless prose about the idea, expanded.",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_overwriting_a_legacy_note_keeps_its_old_lines_unjudged(
    tool_use, run_hook, vault, env
):
    # Arrange
    target = vault / "wiki/concepts/Legacy.md"
    target.write_text(LEGACY)
    payload = tool_use(
        "Write", {"file_path": str(target), "content": LEGACY + "\nMore prose.\n"}
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_overwriting_an_unreadable_note_judges_every_line(
    tool_use, run_hook, vault, env
):
    # Arrange
    target = vault / "wiki/concepts/Garbled.md"
    target.write_bytes(b"\xff\xfe")
    payload = tool_use("Write", {"file_path": str(target), "content": LEGACY})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN003")


def test_an_edit_adding_a_new_undated_claim_beside_an_old_one_is_blocked(
    tool_use, run_hook, vault, env
):
    # Arrange
    target = vault / "wiki/concepts/Legacy.md"
    target.write_text(LEGACY)
    payload = tool_use(
        "Edit",
        {
            "file_path": str(target),
            "old_string": "Some timeless prose about the idea.",
            "new_string": "The pipeline has 13 open deals.",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN003")


def test_multiedit_composes_every_edit(tool_use, run_hook, vault, env):
    # Arrange
    target = vault / "wiki/concepts/Multi.md"
    target.write_text(GOOD)
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": str(target),
            "edits": [
                {
                    "old_string": "Some timeless prose about the idea.",
                    "new_string": "Filler.",
                },
                {
                    "old_string": "Filler.",
                    "new_string": "The backlog has 42 open tasks.",
                },
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "KN003")


def test_allows_edit_of_a_note_that_does_not_exist_yet(tool_use, run_hook, vault, env):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": note(vault, "wiki/concepts/Absent.md"),
            "old_string": "a",
            "new_string": "b",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)
