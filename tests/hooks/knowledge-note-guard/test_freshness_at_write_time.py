"""Freshness errors must be caught as a note is written, not only by a linter.

FRESH-1 and FRESH-3 are error severity and decidable from a single file, which
is the bar KN001 to KN006 already meet. FRESH-2 stays in the linter because it
becomes true through elapsed time while the file sits unchanged, so blocking an
edit on it would punish an author for something the edit did not cause.

The FRESH-3 case below is the exact body that reached the vault on 2026-09-18
and was found only because a linter was run by hand during an unrelated audit.

Rule source: ``rules/knowledge-notes.md`` "The Freshness Policy".
"""

from __future__ import annotations

import pytest

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
    """A real vault on disk.

    The hook resolves its root with `is_dir` and stays silent when the vault is
    absent, so a hardcoded home-directory path makes every block assertion pass
    on the author's machine and every allow assertion vacuous on a runner that
    has no such directory. Creating the vault is what makes the two agree.
    """
    root = tmp_path / "second-brain"
    (root / "wiki" / "concepts").mkdir(parents=True)
    return root


@pytest.fixture
def note(vault):
    return str(vault / NOTE_REL)


@pytest.fixture
def vault_env(vault):
    return {"SECOND_BRAIN_VAULT": str(vault)}


def test_blocks_pointer_with_no_resolvable_target(
    tool_use, assert_blocks, vault_env, note
):
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

    assert_blocks(HOOK, payload, "FRESH-3", env=vault_env)


def test_allows_pointer_with_a_url(tool_use, assert_allows, vault_env, note):
    payload = tool_use(
        "Write",
        {
            "file_path": note,
            "content": body(
                "Where truth lives: https://linear.app/lineleap/issue/WEB-3789"
            ),
        },
    )

    assert_allows(HOOK, payload, env=vault_env)


def test_allows_pointer_with_a_typed_id(tool_use, assert_allows, vault_env, note):
    payload = tool_use(
        "Write",
        {"file_path": note, "content": body("Where truth lives: linear:WEB-3789")},
    )

    assert_allows(HOOK, payload, env=vault_env)


def test_still_blocks_the_undated_volatile_claim(
    tool_use, assert_blocks, vault_env, note
):
    payload = tool_use(
        "Write",
        {"file_path": note, "content": body("The pipeline has 13 open deals.")},
    )

    assert_blocks(HOOK, payload, "KN003", env=vault_env)


def test_stale_stamp_is_not_a_write_time_block(
    tool_use, assert_allows, vault_env, note
):
    payload = tool_use(
        "Write",
        {
            "file_path": note,
            "content": body("The pipeline had 13 open deals (as of 2020-01-01)."),
        },
    )

    assert_allows(HOOK, payload, env=vault_env)
