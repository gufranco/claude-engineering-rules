from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "large-file-blocker.py"
OVER_LIMIT_BYTES = 6 * 1024 * 1024


@pytest.fixture()
def repo_with_large_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=30)
    (tmp_path / "huge.bin").write_bytes(b"x" * OVER_LIMIT_BYTES)
    subprocess.run(
        ["git", "add", "huge.bin"], check=True, cwd=str(tmp_path), timeout=30
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    "template",
    [
        "git -C {repo} commit -m 'fix: y'",
        "git -C \"{repo}\" commit -m 'fix: y'",
        "git -c core.editor=true commit -m 'fix: y'",
    ],
)
def test_commit_behind_global_options_is_checked(
    template, repo_with_large_file, tool_use, run_hook
):
    # Arrange
    command = template.format(repo=repo_with_large_file)
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "huge.bin")


def test_status_behind_global_options_is_not_checked(
    repo_with_large_file, tool_use, run_hook
):
    # Arrange
    payload = tool_use("Bash", {"command": f"git -C {repo_with_large_file} status"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
