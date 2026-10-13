from __future__ import annotations


import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "ai-slop-blocker"
DOC = "/repo/docs/notes.md"

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))


@pytest.mark.parametrize(
    "text",
    [
        "The endpoint returns 404 when the user does not exist.",
        "If the CLI could not find the config, it exits with status 2.",
        "The probe checks the lock before every write.",
    ],
)
def test_behavior_that_mentions_failure_is_not_search_narration(
    tool_use, run_hook, text
):
    # Arrange
    payload = tool_use("Write", {"file_path": DOC, "content": f"# Notes\n\n{text}\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "words",
    [
        "a pivotal and intricate migration",
        "fostering a crucial change",
        "a testament to the pivotal release",
    ],
)
def test_added_vocabulary_fires_at_two_distinct_words(tool_use, run_hook, words):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": DOC, "content": f"# Notes\n\nThis was {words}.\n"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "SLOP009")


def test_sentence_opening_additionally_counts_toward_the_cluster(tool_use, run_hook):
    # Arrange
    content = (
        "# Notes\n\nThe change is pivotal.\nAdditionally, the cache warms first.\n"
    )
    payload = tool_use("Write", {"file_path": DOC, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "SLOP009")


NARRATION = "# Notes\n\nThe pinout was verified on 2026-10-11 against the board.\n"


def test_search_narration_is_allowed_in_the_vault(tool_use, run_hook, tmp_path):
    # Arrange
    vault = tmp_path / "vault"
    note = vault / "wiki" / "concepts" / "Pinout.md"
    note.parent.mkdir(parents=True)
    payload = tool_use("Write", {"file_path": str(note), "content": NARRATION})

    # Act
    result = run_hook(HOOK, payload, env={"SECOND_BRAIN_VAULT": str(vault)})

    # Assert
    assert_allowed(result)


def test_search_narration_is_allowed_in_a_prompt_file(tool_use, run_hook, tmp_path):
    # Arrange
    prompt = tmp_path / "PROMPT.md"
    payload = tool_use("Write", {"file_path": str(prompt), "content": NARRATION})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_search_narration_is_allowed_in_the_project_workspace(
    tool_use, run_hook, tmp_path
):
    # Arrange
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=30)
    research = repo / "docs" / "research" / "pinout.md"
    research.parent.mkdir(parents=True)
    (repo / "docs" / "PROMPT.md").write_text("# Prompt\n", encoding="utf-8")
    payload = tool_use("Write", {"file_path": str(research), "content": NARRATION})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_search_narration_outside_the_vault_is_blocked(tool_use, run_hook, tmp_path):
    # Arrange
    vault = tmp_path / "vault"
    vault.mkdir()
    readme = tmp_path / "project" / "README.md"
    payload = tool_use("Write", {"file_path": str(readme), "content": NARRATION})

    # Act
    result = run_hook(HOOK, payload, env={"SECOND_BRAIN_VAULT": str(vault)})

    # Assert
    assert_blocked(result, "SLOP015")


def test_record_paths_still_block_other_tells(tool_use, run_hook, tmp_path):
    # Arrange
    prompt = tmp_path / "PROMPT.md"
    content = NARRATION + "This stands as a testament to the design.\n"
    payload = tool_use("Write", {"file_path": str(prompt), "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(result, "SLOP002")
    assert "SLOP015" not in stderr


def test_search_narration_in_a_published_body_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "gh pr comment 12 --body 'The pinout could not be verified.'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "SLOP015")


def test_search_narration_is_blocked_when_no_vault_is_set(tool_use, run_hook, tmp_path):
    # Arrange
    readme = tmp_path / "project" / "README.md"
    payload = tool_use("Write", {"file_path": str(readme), "content": NARRATION})

    # Act
    result = run_hook(HOOK, payload, env={"SECOND_BRAIN_VAULT": ""})

    # Assert
    assert_blocked(result, "SLOP015")
