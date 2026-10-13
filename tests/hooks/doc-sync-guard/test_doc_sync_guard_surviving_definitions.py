from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from faker import Faker
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "doc-sync-guard"
COMMIT = "git commit -m 'chore: drop a script'"
COMMIT_ALL = "git commit -a -m 'chore: drop a script'"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, timeout=30
    )


@pytest.fixture()
def repo(tmp_path: Path, faker: Faker) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", faker.email())
    _git(root, "config", "user.name", faker.first_name())
    _git(root, "config", "commit.gpgsign", "false")
    (root / "old.py").write_text('parser.add_argument("--json")\n', encoding="utf-8")
    (root / "keep.py").write_text('parser.add_argument("--json")\n', encoding="utf-8")
    (root / "lib.ts").write_text("export function render() {}\n", encoding="utf-8")
    (root / "old.ts").write_text("export function render() {}\n", encoding="utf-8")
    (root / "README.md").write_text(
        "Pass `--json` to get rows; call render to draw.\n", encoding="utf-8"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "chore: baseline")
    return root


def test_allows_deleting_a_script_whose_flag_another_script_defines(
    repo: Path, tool_use, run_hook
) -> None:
    # Arrange
    _git(repo, "rm", "-q", "old.py")
    payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_deleting_a_module_whose_export_another_module_defines(
    repo: Path, tool_use, run_hook
) -> None:
    # Arrange
    _git(repo, "rm", "-q", "old.ts")
    payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_when_the_last_definition_of_a_documented_flag_goes(
    repo: Path, tool_use, run_hook
) -> None:
    # Arrange
    _git(repo, "rm", "-q", "old.py", "keep.py")
    payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "flag --json was removed but README.md still names it")


def test_commit_all_reads_surviving_definitions_from_the_working_tree(
    repo: Path, tool_use, run_hook
) -> None:
    # Arrange
    (repo / "old.py").write_text("print('gone')\n", encoding="utf-8")
    (repo / "keep.py").write_text("print('gone')\n", encoding="utf-8")
    payload = tool_use("Bash", {"command": COMMIT_ALL}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "flag --json was removed but README.md still names it")
