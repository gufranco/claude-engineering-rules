from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from faker import Faker
from _helpers.hook_assertions import assert_allowed, assert_blocked

ROOT = Path(__file__).resolve().parents[3]
HOOK = "git-author-guard"
HOOK_PATH = ROOT / "hooks" / f"{HOOK}.py"
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "tests"))

from _helpers.cov_env import apply_coverage_env  # noqa: E402
from _lib.bypass_writer import set_bypass  # noqa: E402

FAKE = Faker()
FAKE.seed_instance(20261012)
AUTHOR_NAME = FAKE.first_name()
REAL_EMAIL = FAKE.free_email()
OTHER_EMAIL = FAKE.free_email()
OVERRIDE_EMAIL = FAKE.free_email()
PLACEHOLDER = "dev@" + "example.com"


def _config(path: Path, email: str | None) -> dict[str, str]:
    lines = ["[user]", f"\tname = {AUTHOR_NAME}"]
    if email is not None:
        lines = [*lines, f"\temail = {email}"]
    lines = [*lines, "[commit]", "\tgpgsign = false"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"GIT_CONFIG_GLOBAL": str(path), "GIT_CONFIG_NOSYSTEM": "1"}


def _git(repo: Path, env: dict[str, str], *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        env={**os.environ, **env},
        check=True,
        capture_output=True,
    )


def _repo(tmp_path: Path, email: str | None) -> tuple[Path, dict[str, str]]:
    env = _config(tmp_path / "gitconfig", email)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, env, "init", "-q", "-b", "main")
    return repo, env


def _commit(repo: Path, env: dict[str, str], email: str) -> None:
    author = {**env, "GIT_AUTHOR_EMAIL": email, "GIT_COMMITTER_EMAIL": email}
    _git(repo, author, "commit", "-q", "--allow-empty", "-m", "chore: x")


def _with_upstream(tmp_path: Path, repo: Path, env: dict[str, str]) -> None:
    remote = tmp_path / "remote.git"
    _git(tmp_path, env, "init", "-q", "--bare", str(remote))
    _git(repo, env, "remote", "add", "origin", str(remote))
    _commit(repo, env, REAL_EMAIL)
    _git(repo, env, "push", "-q", "-u", "origin", "main")


def test_commit_without_an_email_is_blocked(tmp_path, tool_use, run_hook):
    # Arrange
    repo, env = _repo(tmp_path, None)
    payload = tool_use("Bash", {"command": f"git -C {repo} commit -m 'fix: y'"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "`user.email` is not set")


def test_commit_with_a_placeholder_email_is_blocked(tmp_path, tool_use, run_hook):
    # Arrange
    repo, env = _repo(tmp_path, PLACEHOLDER)
    payload = tool_use("Bash", {"command": f"git -C {repo} commit -m 'fix: y'"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, f"is a placeholder ({PLACEHOLDER})")


def test_commit_with_a_local_user_block_is_blocked(tmp_path, tool_use, run_hook):
    # Arrange
    repo, env = _repo(tmp_path, REAL_EMAIL)
    config = repo / ".git" / "config"
    config.write_text(
        config.read_text(encoding="utf-8")
        + f"# note\n; note\n[user]\n\temail = {OTHER_EMAIL}\n",
        encoding="utf-8",
    )
    payload = tool_use("Bash", {"command": f"git -C {repo} commit -m 'fix: y'"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "contains a local [user] block")


@pytest.mark.parametrize(
    "template",
    ["git -C {repo} commit -m 'fix: y'", "cd {repo} && git commit -m 'fix: y'"],
)
def test_commit_with_a_resolved_identity_is_allowed(
    template, tmp_path, tool_use, run_hook
):
    # Arrange
    repo, env = _repo(tmp_path, REAL_EMAIL)
    payload = tool_use("Bash", {"command": template.format(repo=repo)})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_commit_with_an_env_identity_override_is_blocked(tmp_path, tool_use, run_hook):
    # Arrange
    repo, env = _repo(tmp_path, REAL_EMAIL)
    command = f"GIT_AUTHOR_EMAIL={OVERRIDE_EMAIL} git -C {repo} commit -m 'fix: y'"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, "identity override env var")


def test_commit_outside_a_repository_is_allowed(tmp_path, tool_use, run_hook):
    # Arrange
    _repo_dir, env = _repo(tmp_path, None)
    loose = tmp_path / "loose"
    loose.mkdir()
    payload = tool_use("Bash", {"command": f"git -C {loose} commit -m 'fix: y'"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_push_of_a_placeholder_commit_without_upstream_is_blocked(
    tmp_path, tool_use, run_hook
):
    # Arrange
    repo, env = _repo(tmp_path, REAL_EMAIL)
    _commit(repo, env, PLACEHOLDER)
    payload = tool_use("Bash", {"command": f"git -C {repo} push origin feat"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, f"placeholder author email ({PLACEHOLDER})")


def test_push_of_a_placeholder_commit_ahead_of_upstream_is_blocked(
    tmp_path, tool_use, run_hook
):
    # Arrange
    repo, env = _repo(tmp_path, REAL_EMAIL)
    _with_upstream(tmp_path, repo, env)
    _commit(repo, env, PLACEHOLDER)
    payload = tool_use("Bash", {"command": f"git -C {repo} push origin feat"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_blocked(result, f"placeholder author email ({PLACEHOLDER})")


def test_push_of_clean_commits_ahead_of_upstream_is_allowed(
    tmp_path, tool_use, run_hook
):
    # Arrange
    repo, env = _repo(tmp_path, REAL_EMAIL)
    _with_upstream(tmp_path, repo, env)
    _commit(repo, env, REAL_EMAIL)
    payload = tool_use("Bash", {"command": f"git -C {repo} push origin feat"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize("target_name", ["repo", ""])
def test_push_with_nothing_to_inspect_is_allowed(
    target_name, tmp_path, tool_use, run_hook
):
    # Arrange
    _repo_dir, env = _repo(tmp_path, REAL_EMAIL)
    target = tmp_path / target_name
    payload = tool_use("Bash", {"command": f"git -C {target} push origin feat"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_a_config_write_to_another_key_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git config core.editor vim"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "env", [{"CLAUDE_DISABLED_HOOKS": HOOK}, {"GIT_AUTHOR_GUARD_DISABLE": "1"}]
)
def test_an_explicit_switch_allows(env, tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": f"git config user.email {OVERRIDE_EMAIL}"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_a_live_bypass_entry_allows(tmp_path, tool_use, run_hook):
    # Arrange
    state = tmp_path / "bypass.json"
    set_bypass(HOOK, ttl_seconds=120, state_path=state)
    payload = tool_use("Bash", {"command": f"git config user.email {OVERRIDE_EMAIL}"})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    assert_allowed(result)


def test_a_payload_that_is_not_json_blocks():
    # Arrange
    env = apply_coverage_env(dict(os.environ))
    env["CLAUDE_BYPASS_STATE"] = os.devnull

    # Act
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="not json",
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )

    # Assert
    assert (proc.returncode, "could not read its input" in proc.stderr) == (2, True)


def test_repo_dir_falls_back_to_the_working_directory(tmp_path, monkeypatch):
    # Arrange
    spec = importlib.util.spec_from_file_location("_gag_repos", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path)

    # Act
    resolved = module.repo_dir("cd /does/not/exist && git -C /nor/this commit")

    # Assert
    assert resolved == tmp_path


def test_commit_in_a_linked_worktree_is_allowed(tmp_path, tool_use, run_hook):
    # Arrange
    repo, env = _repo(tmp_path, REAL_EMAIL)
    _commit(repo, env, REAL_EMAIL)
    worktree = tmp_path / "wt"
    _git(repo, env, "worktree", "add", "-q", "-b", "side", str(worktree))
    payload = tool_use("Bash", {"command": f"git -C {worktree} commit -m 'fix: y'"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_a_local_user_block_without_identity_keys_is_allowed(
    tmp_path, tool_use, run_hook
):
    # Arrange
    repo, env = _repo(tmp_path, REAL_EMAIL)
    config = repo / ".git" / "config"
    config.write_text(
        config.read_text(encoding="utf-8") + "[user]\n\tsigningkey = ABC123\n",
        encoding="utf-8",
    )
    payload = tool_use("Bash", {"command": f"git -C {repo} commit -m 'fix: y'"})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_a_missing_git_binary_reads_as_outside_a_repository(
    tmp_path, tool_use, run_hook
):
    # Arrange
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    payload = tool_use("Bash", {"command": f"git -C {tmp_path} commit -m 'fix: y'"})

    # Act
    result = run_hook(HOOK, payload, env={"PATH": str(empty)})

    # Assert
    assert_allowed(result)
