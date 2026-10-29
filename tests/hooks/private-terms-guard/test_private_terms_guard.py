from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env

HOOK = "private-terms-guard"


def _git(repo: Path, *args: str) -> None:
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_AUTHOR_NAME": "dev",
        "GIT_AUTHOR_EMAIL": "dev@example.invalid",
        "GIT_COMMITTER_NAME": "dev",
        "GIT_COMMITTER_EMAIL": "dev@example.invalid",
    }
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env=env,
        timeout=30,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "public"
    root.mkdir()
    _git(root, "init", "-q")
    (root / ".gitignore").write_text("local/\n", encoding="utf-8")
    return root


@pytest.fixture
def term(faker: Faker) -> str:
    return f"{faker.word().lower()}corp"


def _env(tmp_path: Path, repo: Path, term: str) -> dict[str, str]:
    terms = tmp_path / "terms.txt"
    terms.write_text(f"# employers\n\n{term}\n", encoding="utf-8")
    return {"PRIVATE_TERMS_FILE": str(terms), "PRIVATE_TERMS_REPO": str(repo)}


def test_blocks_a_write_naming_a_private_term(
    tool_use, run_hook, tmp_path, repo, term
) -> None:
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": str(repo / "rules" / "a.md"),
            "content": f"Learned at {term.upper()}.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path, repo, term))

    # Assert
    assert result.code == 2
    assert f"rules/a.md: {term}" in result.stderr


def test_blocks_a_multi_edit_fragment(tool_use, run_hook, tmp_path, repo, term) -> None:
    # Arrange
    edits = [
        {"old_string": "a", "new_string": "plain"},
        {"old_string": "b", "new_string": f"see {term}"},
    ]
    payload = tool_use("MultiEdit", {"file_path": str(repo / "b.md"), "edits": edits})

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path, repo, term))

    # Assert
    assert result.code == 2


@pytest.mark.parametrize(
    "relative",
    ["../outside.md", "local/notes.md"],
)
def test_allows_a_write_outside_the_published_tree(
    tool_use, run_hook, tmp_path, repo, term, relative
) -> None:
    # Arrange
    payload = tool_use(
        "Edit", {"file_path": str(repo / relative), "new_string": f"from {term}"}
    )

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path, repo, term))

    # Assert
    assert (result.code, result.stderr) == (0, "")


def test_allows_a_term_inside_a_longer_word(
    tool_use, run_hook, tmp_path, repo, term
) -> None:
    # Arrange
    payload = tool_use(
        "Write", {"file_path": str(repo / "a.md"), "content": f"{term}s and x{term}\n"}
    )

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path, repo, term))

    # Assert
    assert result.code == 0


def test_allows_everything_without_a_terms_file(
    tool_use, run_hook, tmp_path, repo, term
) -> None:
    # Arrange
    payload = tool_use("Write", {"file_path": str(repo / "a.md"), "content": term})
    env = {
        "PRIVATE_TERMS_FILE": str(tmp_path / "absent.txt"),
        "PRIVATE_TERMS_REPO": str(repo),
    }

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert result.code == 0


def test_reads_the_terms_file_from_the_vault_by_default(
    tool_use, run_hook, tmp_path, repo, term
) -> None:
    # Arrange
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".private-terms.txt").write_text(f"{term}\n", encoding="utf-8")
    payload = tool_use("Write", {"file_path": str(repo / "a.md"), "content": term})
    env = {
        "SECOND_BRAIN_VAULT": str(vault),
        "PRIVATE_TERMS_FILE": "",
        "PRIVATE_TERMS_REPO": str(repo),
    }

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert result.code == 2


def test_honours_the_disable_switch(tool_use, run_hook, tmp_path, repo, term) -> None:
    # Arrange
    payload = tool_use("Write", {"file_path": str(repo / "a.md"), "content": term})
    env = {**_env(tmp_path, repo, term), "PRIVATE_TERMS_GUARD_DISABLE": "1"}

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert result.code == 0


def test_blocks_a_commit_that_stages_a_private_term(
    tool_use, run_hook, tmp_path, repo, term
) -> None:
    # Arrange
    (repo / "c.md").write_text(f"Built for {term}.\n", encoding="utf-8")
    _git(repo, "add", "c.md")
    payload = tool_use(
        "Bash", {"command": "git commit -m 'docs: add c'"}, cwd=str(repo)
    )

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path, repo, term))

    # Assert
    assert result.code == 2
    assert f"c.md: {term}" in result.stderr


def test_ignores_a_commit_in_another_repository(
    tool_use, run_hook, tmp_path, repo, term
) -> None:
    # Arrange
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q")
    (other / "c.md").write_text(term, encoding="utf-8")
    _git(other, "add", "c.md")
    payload = tool_use("Bash", {"command": "git commit -m x"}, cwd=str(other))

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path, repo, term))

    # Assert
    assert result.code == 0


def test_ignores_a_bash_command_that_is_not_a_commit(
    tool_use, run_hook, tmp_path, repo, term
) -> None:
    # Arrange
    payload = tool_use("Bash", {"command": f"echo {term}"}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path, repo, term))

    # Assert
    assert result.code == 0


def test_blocks_unreadable_input() -> None:
    # Arrange
    hook = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
    env = apply_coverage_env(dict(os.environ))

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input="not json",
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )

    # Assert
    assert proc.returncode == 2


def test_allows_everything_with_no_vault_configured(
    tool_use, run_hook, repo, term
) -> None:
    # Arrange
    payload = tool_use("Write", {"file_path": str(repo / "a.md"), "content": term})
    env = {
        "SECOND_BRAIN_VAULT": "",
        "PRIVATE_TERMS_FILE": "",
        "PRIVATE_TERMS_REPO": str(repo),
    }

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert result.code == 0


def test_allows_an_edit_with_no_file_path(
    tool_use, run_hook, tmp_path, repo, term
) -> None:
    # Arrange
    payload = tool_use("Edit", {"new_string": term})

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path, repo, term))

    # Assert
    assert result.code == 0


def test_allows_a_payload_whose_tool_input_is_not_an_object(
    run_hook, tmp_path, repo, term
) -> None:
    # Arrange
    payload = {"tool_name": "Write", "tool_input": term}

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path, repo, term))

    # Assert
    assert result.code == 0


def test_blocks_a_commit_whose_index_cannot_be_read(
    tool_use, run_hook, tmp_path, repo, term
) -> None:
    # Arrange
    (repo / "c.md").write_text("plain\n", encoding="utf-8")
    _git(repo, "add", "c.md")
    (repo / ".git" / "index").write_bytes(b"not an index")
    payload = tool_use("Bash", {"command": "git commit -m x"}, cwd=str(repo))

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path, repo, term))

    # Assert
    assert result.code == 2
    assert "could not read the staged files" in result.stderr
