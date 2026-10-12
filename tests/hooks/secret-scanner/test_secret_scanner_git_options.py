from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "secret-scanner"
FAKE_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"


@pytest.fixture()
def repo_with_staged_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "config.py").write_text(f"KEY = '{FAKE_KEY}'\n", encoding="utf-8")
    subprocess.run(["git", "add", "config.py"], check=True, cwd=str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    "template",
    [
        "git -C {repo} commit -m 'fix: y'",
        "git -C '{repo}' commit -m 'fix: y'",
        "git -c core.editor=true commit -m 'fix: y'",
        "git --no-pager commit -m 'fix: y'",
    ],
)
def test_commit_behind_global_options_is_scanned(
    template, repo_with_staged_secret, tool_use, run_hook
):
    # Arrange
    command = template.format(repo=repo_with_staged_secret)
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "AWS Access Key")


def test_status_behind_global_options_is_not_scanned(
    repo_with_staged_secret, tool_use, run_hook
):
    # Arrange
    payload = tool_use("Bash", {"command": f"git -C {repo_with_staged_secret} status"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
