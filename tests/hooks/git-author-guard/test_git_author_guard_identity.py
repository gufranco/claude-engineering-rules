from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from faker import Faker
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "git-author-guard"
FAKE = Faker()
FAKE.seed_instance(20261104)
AUTHOR_NAME = FAKE.first_name()
REAL_EMAIL = FAKE.free_email()
OTHER_EMAIL = FAKE.free_email()
HOST_EMAIL = f"{FAKE.user_name()}@{FAKE.word()}-mac.local"


def git(repo: Path, env: dict[str, str], *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        env={**os.environ, **env},
        check=True,
        capture_output=True,
        timeout=30,
    )


def write_config(tmp_path: Path, signing: str) -> dict[str, str]:
    config = tmp_path / "gitconfig"
    config.write_text(
        f"[user]\n\tname = {AUTHOR_NAME}\n\temail = {REAL_EMAIL}\n{signing}",
        encoding="utf-8",
    )
    return {"GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_NOSYSTEM": "1"}


def ssh_signing(tmp_path: Path) -> str:
    key = tmp_path / "signing"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    public = key.with_suffix(".pub").read_text(encoding="utf-8").strip()
    allowed = tmp_path / "allowed_signers"
    allowed.write_text(f"{REAL_EMAIL} {public}\n", encoding="utf-8")
    return (
        f"[user]\n\tsigningkey = {key}.pub\n[gpg]\n\tformat = ssh\n"
        f'[gpg "ssh"]\n\tallowedSignersFile = {allowed}\n'
        "[commit]\n\tgpgsign = true\n"
    )


def pushed_repo(tmp_path: Path, signing: str) -> tuple[Path, dict[str, str]]:
    env = write_config(tmp_path, signing)
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    repo.mkdir()
    git(tmp_path, env, "init", "-q", "--bare", str(remote))
    git(repo, env, "init", "-q", "-b", "main")
    git(repo, env, "remote", "add", "origin", str(remote))
    git(repo, env, "commit", "-q", "--allow-empty", "-m", "chore: base")
    git(repo, env, "push", "-q", "-u", "origin", "main")
    return repo, env


def commit_as(repo: Path, env: dict[str, str], author: str, committer: str) -> None:
    identity = {**env, "GIT_AUTHOR_EMAIL": author, "GIT_COMMITTER_EMAIL": committer}
    git(repo, identity, "commit", "-q", "--allow-empty", "-m", "fix: y")


def push_payload(tool_use, repo: Path):
    return tool_use("Bash", {"command": f"git -C {repo} push origin main"})


@pytest.mark.parametrize(
    ("author", "committer", "role"),
    [(HOST_EMAIL, REAL_EMAIL, "author"), (REAL_EMAIL, HOST_EMAIL, "committer")],
)
def test_push_of_a_hostname_email_is_blocked(
    tmp_path, tool_use, run_hook, author, committer, role
):
    # Arrange
    repo, env = pushed_repo(tmp_path, "[commit]\n\tgpgsign = false\n")
    commit_as(repo, env, author, committer)

    # Act
    result = run_hook(HOOK, push_payload(tool_use, repo), env=env)

    # Assert
    assert_blocked(result, f"{role} email derived from the machine name")


def test_push_of_a_commit_by_another_committer_is_blocked(tmp_path, tool_use, run_hook):
    # Arrange
    repo, env = pushed_repo(tmp_path, "[commit]\n\tgpgsign = false\n")
    commit_as(repo, env, REAL_EMAIL, OTHER_EMAIL)

    # Act
    result = run_hook(HOOK, push_payload(tool_use, repo), env=env)

    # Assert
    assert_blocked(result, f"was committed as {OTHER_EMAIL}")


def test_push_of_an_unsigned_commit_under_signing_is_blocked(
    tmp_path, tool_use, run_hook
):
    # Arrange
    repo, env = pushed_repo(tmp_path, ssh_signing(tmp_path))
    git(repo, env, "commit", "-q", "--allow-empty", "--no-gpg-sign", "-m", "fix: y")

    # Act
    result = run_hook(HOOK, push_payload(tool_use, repo), env=env)

    # Assert
    assert_blocked(result, "carries no valid signature")


def test_push_of_a_signed_commit_by_the_configured_identity_is_allowed(
    tmp_path, tool_use, run_hook
):
    # Arrange
    repo, env = pushed_repo(tmp_path, ssh_signing(tmp_path))
    git(repo, env, "commit", "-q", "--allow-empty", "-m", "fix: y")

    # Act
    result = run_hook(HOOK, push_payload(tool_use, repo), env=env)

    # Assert
    assert_allowed(result)


def test_push_by_the_configured_identity_without_signing_is_allowed(
    tmp_path, tool_use, run_hook
):
    # Arrange
    repo, env = pushed_repo(tmp_path, "[commit]\n\tgpgsign = false\n")
    commit_as(repo, env, REAL_EMAIL, REAL_EMAIL)

    # Act
    result = run_hook(HOOK, push_payload(tool_use, repo), env=env)

    # Assert
    assert_allowed(result)
