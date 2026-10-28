from __future__ import annotations

import json
from pathlib import Path

import pytest
from doc_sync_guard_test_repo import HOOK, _git, _stage

from _helpers.hook_assertions import assert_allowed


@pytest.fixture()
def bare_repo(tmp_path: Path, faker) -> Path:
    root = tmp_path / "fresh"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", faker.email())
    _git(root, "config", "user.name", faker.first_name())
    return root


def test_a_commit_all_before_the_first_commit_is_allowed(
    bare_repo: Path, tool_use, run_hook
):
    # Arrange
    (bare_repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    _stage(bare_repo, "app.py")
    payload = tool_use(
        "Bash", {"command": "git commit -am 'feat: first'"}, cwd=str(bare_repo)
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_newly_added_package_manifest_is_allowed(repo: Path, tool_use, run_hook):
    # Arrange
    (repo / "package.json").write_text(
        json.dumps({"scripts": {"build": "tsc"}}), encoding="utf-8"
    )
    _stage(repo, "package.json")
    payload = tool_use("Bash", {"command": "git commit -m 'feat: add'"}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_package_manifest_that_is_not_an_object_is_allowed(
    repo: Path, tool_use, run_hook
):
    # Arrange
    manifest = repo / "package.json"
    manifest.write_text("[1]", encoding="utf-8")
    _stage(repo, "package.json")
    _git(repo, "commit", "-qm", "chore: list manifest")
    manifest.write_text("[2]", encoding="utf-8")
    _stage(repo, "package.json")
    payload = tool_use(
        "Bash", {"command": "git commit -m 'chore: bump'"}, cwd=str(repo)
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
