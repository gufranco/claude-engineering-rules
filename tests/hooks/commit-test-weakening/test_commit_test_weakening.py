from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))

from git_repo_fixture import GitRepo, isolated_git_env, new_git_repo  # noqa: E402

HOOK = "commit-test-weakening"
HOOK_SOURCE = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"


def load_hook() -> ModuleType:
    sys.path.insert(0, str(HOOK_SOURCE.parent))
    spec = importlib.util.spec_from_file_location("commit_test_weakening", HOOK_SOURCE)
    assert spec is not None and spec.loader is not None, "no loader for the hook"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BLOCKED = "BLOCKED by commit-test-weakening"
TWO_TESTS = (
    "def test_one():\n    assert 1 == 1\n\n\ndef test_two():\n    assert 2 == 2\n"
)
FIRST_TEST = "def test_one():\n    assert 1 == 1\n"
SECOND_TEST = "def test_two():\n    assert 2 == 2\n"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> GitRepo:
    for key, value in isolated_git_env().items():
        monkeypatch.setenv(key, value)
    created = new_git_repo(tmp_path)
    created.stage("tests/test_orders.py", TWO_TESTS)
    created.commit()
    return created


def commit_payload(tool_use, repo: GitRepo, command: str = "git commit -am x") -> dict:
    return tool_use("Bash", {"command": command}, cwd=str(repo.root))


def test_a_test_moved_into_a_new_file_commits(tool_use, run_hook, repo):
    # Arrange
    repo.write("tests/test_orders.py", FIRST_TEST)
    repo.write("tests/test_orders_slow.py", SECOND_TEST)

    # Act
    code, _stdout, stderr = run_hook(HOOK, commit_payload(tool_use, repo))

    # Assert
    assert (code, BLOCKED in stderr) == (0, False)


def test_a_renamed_test_file_commits(tool_use, run_hook, repo):
    # Arrange
    repo.git("mv", "tests/test_orders.py", "tests/test_billing.py")

    # Act
    code, _stdout, stderr = run_hook(HOOK, commit_payload(tool_use, repo))

    # Assert
    assert (code, BLOCKED in stderr) == (0, False)


def test_a_test_removed_by_a_script_edit_blocks(tool_use, run_hook, repo):
    # Arrange
    repo.write("tests/test_orders.py", FIRST_TEST)

    # Act
    code, _stdout, stderr = run_hook(HOOK, commit_payload(tool_use, repo))

    # Assert
    assert (code, "test cases drop from 2 to 1" in stderr) == (2, True)


def test_a_deleted_test_file_blocks(tool_use, run_hook, repo):
    # Arrange
    (repo.root / "tests" / "test_orders.py").unlink()

    # Act
    code, _stdout, stderr = run_hook(HOOK, commit_payload(tool_use, repo))

    # Assert
    assert (code, "assertions drop from 2 to 0" in stderr) == (2, True)


def test_a_new_skip_marker_blocks(tool_use, run_hook, repo):
    # Arrange
    repo.write(
        "tests/test_orders.py",
        TWO_TESTS.replace("def test_two", "@pytest.mark.skip\ndef test_two"),
    )

    # Act
    code, _stdout, stderr = run_hook(HOOK, commit_payload(tool_use, repo))

    # Assert
    assert (code, "skip markers rise from 0 to 1" in stderr) == (2, True)


def test_a_change_outside_the_tests_commits(tool_use, run_hook, repo):
    # Arrange
    repo.write("src/orders.py", "TOTAL = 1\n")

    # Act
    code, _stdout, stderr = run_hook(HOOK, commit_payload(tool_use, repo))

    # Assert
    assert (code, BLOCKED in stderr) == (0, False)


def test_a_deleted_fixture_that_quotes_assertions_commits(tool_use, run_hook, repo):
    # Arrange
    repo.stage("tests/fixtures/payload.json", '{"text": "assert x; expect(y)"}\n')
    repo.commit()
    (repo.root / "tests" / "fixtures" / "payload.json").unlink()

    # Act
    code, _stdout, stderr = run_hook(HOOK, commit_payload(tool_use, repo))

    # Assert
    assert (code, BLOCKED in stderr) == (0, False)


def test_a_machine_without_git_leaves_the_commit_to_git(tool_use, run_hook, repo):
    # Arrange
    repo.write("tests/test_orders.py", FIRST_TEST)

    # Act
    code, _stdout, stderr = run_hook(
        HOOK, commit_payload(tool_use, repo), env={"PATH": "/nonexistent"}
    )

    # Assert
    assert (code, BLOCKED in stderr) == (0, False)


def test_a_command_that_does_not_commit_is_ignored(tool_use, run_hook, repo):
    # Arrange
    repo.write("tests/test_orders.py", FIRST_TEST)

    # Act
    code, _stdout, stderr = run_hook(
        HOOK, commit_payload(tool_use, repo, "git status --short")
    )

    # Assert
    assert (code, BLOCKED in stderr) == (0, False)


def test_a_repository_with_no_commit_yet_commits(
    tool_use, run_hook, tmp_path, monkeypatch
):
    # Arrange
    for key, value in isolated_git_env().items():
        monkeypatch.setenv(key, value)
    fresh = new_git_repo(tmp_path)
    fresh.write("tests/test_orders.py", FIRST_TEST)

    # Act
    code, _stdout, stderr = run_hook(HOOK, commit_payload(tool_use, fresh))

    # Assert
    assert (code, BLOCKED in stderr) == (0, False)


def test_a_repository_git_cannot_diff_blocks(tool_use, run_hook, repo):
    # Arrange
    tree = repo.git("rev-parse", "HEAD^{tree}").strip()
    (repo.root / ".git" / "objects" / tree[:2] / tree[2:]).unlink()

    # Act
    code, _stdout, stderr = run_hook(HOOK, commit_payload(tool_use, repo))

    # Assert
    assert (code, "could not compare" in stderr) == (2, True)


def test_the_disable_variable_lets_a_weakening_commit_through(tool_use, run_hook, repo):
    # Arrange
    repo.write("tests/test_orders.py", FIRST_TEST)

    # Act
    code, _stdout, _stderr = run_hook(
        HOOK,
        commit_payload(tool_use, repo),
        env={"COMMIT_TEST_WEAKENING_DISABLE": "1"},
    )

    # Assert
    assert code == 0


def test_imported_the_hook_reports_the_findings_of_a_directory(repo):
    # Arrange
    repo.write("tests/test_orders.py", FIRST_TEST)

    # Act
    found = load_hook().findings(str(repo.root))

    # Assert
    assert found == ["assertions drop from 2 to 1", "test cases drop from 2 to 1"]
