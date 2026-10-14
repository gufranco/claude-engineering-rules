from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from faker import Faker
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "doc-sync-guard"
COMMIT = "git commit -m 'chore: drop a tool'"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path: Path, faker: Faker) -> Path:
    root = tmp_path / "project"
    (root / "tools").mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", faker.email())
    _git(root, "config", "user.name", faker.first_name())
    _git(root, "config", "commit.gpgsign", "false")
    (root / "tools" / "baseline.py").write_text(
        'parser.add_argument("--verify")\n', encoding="utf-8"
    )
    (root / "tools" / "keep.py").write_text("print('kept')\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "chore: baseline")
    return root


def _write_doc(repo: Path, text: str) -> None:
    (repo / "GUIDE.md").write_text(text, encoding="utf-8")
    _git(repo, "add", "GUIDE.md")
    _git(repo, "commit", "-qm", "docs: guide")


def test_allows_a_doc_that_names_the_flag_for_another_tool(
    repo: Path, tool_use, run_hook
) -> None:
    # Arrange
    _write_doc(repo, "Run `git rev-parse -q --verify MERGE_HEAD` first.\n")
    _git(repo, "rm", "-q", "tools/baseline.py")
    payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_a_doc_that_names_the_deleted_tool_and_its_flag(
    repo: Path, tool_use, run_hook
) -> None:
    # Arrange
    _write_doc(repo, "Run `python tools/baseline.py --verify` before release.\n")
    _git(repo, "rm", "-q", "tools/baseline.py")
    payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "flag --verify was removed but GUIDE.md still names it")


def test_blocks_a_flag_removed_from_a_file_that_still_exists(
    repo: Path, tool_use, run_hook
) -> None:
    # Arrange
    _write_doc(repo, "Pass `--verify` to check the baseline.\n")
    (repo / "tools" / "baseline.py").write_text(
        'parser.add_argument("--check")\n', encoding="utf-8"
    )
    _git(repo, "add", "tools/baseline.py")
    payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "flag --verify was removed but GUIDE.md still names it")
