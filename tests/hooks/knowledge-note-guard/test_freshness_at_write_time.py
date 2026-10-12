from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "knowledge-note-guard"

NOTE_REL = "wiki/concepts/Probe.md"

HEAD = (
    "---\n"
    "date: 2026-09-18\n"
    "type: concept\n"
    "tags: [concept]\n"
    "ai-first: true\n"
    "---\n"
    "\n"
    "## For future agent\n"
    "\n"
)


def body(text: str) -> str:
    return HEAD + text + "\n"


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "second-brain"
    (root / "wiki" / "concepts").mkdir(parents=True)
    return root


@pytest.fixture
def note(vault):
    return str(vault / NOTE_REL)


@pytest.fixture
def vault_env(vault):
    return {"SECOND_BRAIN_VAULT": str(vault)}


def test_blocks_pointer_with_no_resolvable_target(tool_use, run_hook, vault_env, note):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": note,
            "content": body(
                "Where truth lives: `mise ls flutter` says whether the pinned "
                "version is installed or `missing`."
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=vault_env)

    # Assert
    assert_blocked(result, "FRESH-3")


def test_allows_pointer_with_a_url(tool_use, run_hook, vault_env, note):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": note,
            "content": body(
                "Where truth lives: https://linear.app/Acme/issue/WEB-3789"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=vault_env)

    # Assert
    assert_allowed(result)


def test_allows_pointer_with_a_typed_id(tool_use, run_hook, vault_env, note):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": note, "content": body("Where truth lives: linear:WEB-3789")},
    )

    # Act
    result = run_hook(HOOK, payload, env=vault_env)

    # Assert
    assert_allowed(result)


def test_still_blocks_the_undated_volatile_claim(tool_use, run_hook, vault_env, note):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": note, "content": body("The pipeline has 13 open deals.")},
    )

    # Act
    result = run_hook(HOOK, payload, env=vault_env)

    # Assert
    assert_blocked(result, "KN003")


def test_stale_stamp_is_not_a_write_time_block(tool_use, run_hook, vault_env, note):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": note,
            "content": body("The pipeline had 13 open deals (as of 2020-01-01)."),
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=vault_env)

    # Assert
    assert_allowed(result)
