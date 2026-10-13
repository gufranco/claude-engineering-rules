from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from faker import Faker
from _helpers.hook_assertions import assert_blocked

HOOK = "doc-sync-guard"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, timeout=30
    )


@pytest.fixture()
def repo_with_undocumented_env(tmp_path: Path, faker: Faker) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", faker.email())
    _git(root, "config", "user.name", faker.first_name())
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".env.example").write_text("EXISTING=placeholder\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "chore: baseline")
    (root / "app.js").write_text(
        "const k = process.env.NEW_SECRET_KEY;\n", encoding="utf-8"
    )
    _git(root, "add", "app.js")
    return root


@pytest.mark.parametrize(
    "template",
    [
        "git -C {repo} commit -m 'feat: change'",
        "git -C '{repo}' commit -m 'feat: change'",
        "git -c core.editor=true commit -m 'feat: change'",
        "git --git-dir={repo}/.git commit -m 'feat: change'",
    ],
)
def test_commit_behind_global_options_is_checked(
    template, repo_with_undocumented_env, tool_use, run_hook
):
    # Arrange
    command = template.format(repo=repo_with_undocumented_env)
    payload = tool_use(
        "Bash", {"command": command}, cwd=str(repo_with_undocumented_env)
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "NEW_SECRET_KEY")
