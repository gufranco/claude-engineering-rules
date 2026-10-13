from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "secret-scanner"
FAKE_KEY = "AKIA" + "QWERTYUIOPASDFGH"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t.test",
            *args,
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
    _git(root, "add", "app.py")
    _git(root, "commit", "-q", "--no-verify", "-m", "chore: start")
    return root


def test_the_report_names_the_line_and_never_the_secret(tool_use, run_hook, repo):
    # Arrange
    (repo / "app.py").write_text(f"print('ok')\nKEY = '{FAKE_KEY}'\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    payload = tool_use("Bash", {"command": "git commit -m 'fix: y'"}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "app.py:2: AWS Access Key")
    assert FAKE_KEY not in stderr


def test_commit_all_scans_unstaged_tracked_changes(tool_use, run_hook, repo):
    # Arrange
    (repo / "app.py").write_text(f"KEY = '{FAKE_KEY}'\n", encoding="utf-8")
    payload = tool_use("Bash", {"command": "git commit -am 'fix: y'"}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "app.py:1: AWS Access Key")


def test_an_add_chained_before_the_commit_scans_new_files(tool_use, run_hook, repo):
    # Arrange
    (repo / "creds.py").write_text(f"KEY = '{FAKE_KEY}'\n", encoding="utf-8")
    command = "git add . && git commit -m 'fix: y'"
    payload = tool_use("Bash", {"command": command}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "creds.py:1: AWS Access Key")


def test_a_leading_cd_selects_the_repository(tool_use, run_hook, repo, tmp_path):
    # Arrange
    (repo / "app.py").write_text(f"KEY = '{FAKE_KEY}'\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    command = f"cd {repo} && git commit -m 'fix: y'"
    payload = tool_use("Bash", {"command": command}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "app.py:1: AWS Access Key")


def test_git_dash_c_selects_the_repository(tool_use, run_hook, repo, tmp_path):
    # Arrange
    (repo / "app.py").write_text(f"KEY = '{FAKE_KEY}'\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    command = f"git -C {repo} commit -m 'fix: y'"
    payload = tool_use("Bash", {"command": command}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "app.py:1: AWS Access Key")


def test_a_clean_commit_in_the_session_directory_passes(tool_use, run_hook, repo):
    # Arrange
    (repo / "app.py").write_text("print('fine')\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    payload = tool_use("Bash", {"command": "git commit -m 'fix: y'"}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_narrow_add_ignores_untracked_files_it_does_not_name(
    tool_use, run_hook, repo
):
    # Arrange
    (repo / "notes.py").write_text(f"KEY = '{FAKE_KEY}'\n", encoding="utf-8")
    (repo / "app.py").write_text("print('fine')\n", encoding="utf-8")
    command = "git add app.py && git commit -m 'fix: y'"
    payload = tool_use("Bash", {"command": command}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_narrow_add_scans_the_untracked_file_it_names(tool_use, run_hook, repo):
    # Arrange
    (repo / "sub").mkdir()
    (repo / "sub" / "creds.py").write_text(f"KEY = '{FAKE_KEY}'\n", encoding="utf-8")
    command = "git add sub/ && git commit -m 'fix: y'"
    payload = tool_use("Bash", {"command": command}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "sub/creds.py:1: AWS Access Key")


def test_a_directory_that_is_not_a_repository_passes(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use("Bash", {"command": "git commit -m 'fix: y'"}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
