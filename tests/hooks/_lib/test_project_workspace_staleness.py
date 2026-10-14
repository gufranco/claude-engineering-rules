from __future__ import annotations

import os
import time
from pathlib import Path

from _helpers.project_workspace_support import (  # noqa: F401
    commit_file,
    isolated_git_config,
    make_repo,
    pw,
    run_git,
    words,
)


def age(path: Path, seconds: float) -> None:
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


def write_prompt(repo: Path, root: str = "docs") -> Path:
    pw.ensure_excluded(repo, root)
    (repo / root).mkdir(exist_ok=True)
    prompt = repo / root / "PROMPT.md"
    prompt.write_text(words())
    return prompt


def test_managed_entries_ignores_unmarked_lines(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    (repo / ".git" / "info" / "exclude").write_text("/docs/\n/build/\n")

    # Act
    entries = pw.managed_entries(repo)

    # Assert
    assert entries == ()


def test_prompt_is_stale_is_false_on_a_clean_tree(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")

    # Act
    stale = pw.prompt_is_stale(repo, "docs")

    # Assert
    assert stale is False


def test_prompt_is_stale_when_a_change_exists_and_no_prompt(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    (repo / "main.py").write_text(words())

    # Act
    stale = pw.prompt_is_stale(repo, "docs")

    # Assert
    assert stale is True


def test_prompt_is_stale_when_a_change_is_newer_than_the_prompt(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    prompt = write_prompt(repo)
    age(prompt, 600)
    (repo / "main.py").write_text(words())

    # Act
    stale = pw.prompt_is_stale(repo, "docs")

    # Assert
    assert stale is True


def test_prompt_is_fresh_when_written_after_the_change(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    change = repo / "main.py"
    change.write_text(words())
    age(change, 600)
    write_prompt(repo)

    # Act
    stale = pw.prompt_is_stale(repo, "docs")

    # Assert
    assert stale is False


def test_prompt_is_stale_after_a_newer_commit_by_the_user(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    prompt = write_prompt(repo)
    age(prompt, 600)
    commit_file(repo, "main.py")

    # Act
    stale = pw.prompt_is_stale(repo, "docs")

    # Assert
    assert stale is True


def test_prompt_ignores_commits_by_other_authors(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    prompt = write_prompt(repo)
    age(prompt, 600)
    (repo / "main.py").write_text(words())
    run_git(repo, "add", "main.py")
    run_git(
        repo,
        "-c",
        "user.email=teammate@example.org",
        "commit",
        "-q",
        "--no-verify",
        "-m",
        "pulled change",
    )

    # Act
    stale = pw.prompt_is_stale(repo, "docs")

    # Assert
    assert stale is False


def test_prompt_ignores_commits_when_no_user_email_is_set(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "main.py")
    prompt = write_prompt(repo)
    age(prompt, 600)
    run_git(repo, "config", "--unset", "user.email")

    # Act
    stale = pw.prompt_is_stale(repo, "docs")

    # Assert
    assert stale is False


def test_prompt_is_stale_skips_a_deleted_file(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "main.py")
    (repo / "main.py").unlink()
    write_prompt(repo)

    # Act
    stale = pw.prompt_is_stale(repo, "docs")

    # Assert
    assert stale is False


def test_prompt_path_joins_the_root(tmp_path):
    # Arrange
    root = ".work"

    # Act
    path = pw.prompt_path(tmp_path, root)

    # Assert
    assert path == tmp_path / ".work" / "PROMPT.md"


def test_release_tracked_removes_an_entry_the_project_now_tracks(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    pw.ensure_excluded(repo, "docs")
    pw.ensure_excluded(repo, ".work")
    commit_file(repo, "docs/guide.md")

    # Act
    released = pw.release_tracked(repo)

    # Assert
    assert released == ("docs",)
    assert pw.managed_entries(repo) == (".work",)


def test_release_tracked_keeps_unrelated_exclude_lines(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text("*.log\n")
    pw.ensure_excluded(repo, "docs")
    commit_file(repo, "docs/guide.md")

    # Act
    pw.release_tracked(repo)

    # Assert
    assert exclude.read_text() == "*.log\n"


def test_release_tracked_is_a_no_op_without_tracked_entries(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    pw.ensure_excluded(repo, "docs")
    before = (repo / ".git" / "info" / "exclude").read_text()

    # Act
    released = pw.release_tracked(repo)

    # Assert
    assert released == ()
    assert (repo / ".git" / "info" / "exclude").read_text() == before


def test_release_tracked_without_an_exclude_file(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    (repo / ".git" / "info" / "exclude").unlink()

    # Act
    released = pw.release_tracked(repo)

    # Assert
    assert released == ()


def test_in_workspace_is_true_for_a_new_file_in_the_workspace(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")

    # Act
    inside = pw.in_workspace(repo / "docs" / "plans" / "x" / "plan.md")

    # Assert
    assert inside is True


def test_in_workspace_is_false_for_a_project_owned_docs(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/guide.md")

    # Act
    inside = pw.in_workspace(repo / "docs" / "notes.md")

    # Assert
    assert inside is False


def test_in_workspace_is_false_outside_a_repository(tmp_path):
    # Arrange
    path = tmp_path / "docs" / "notes.md"

    # Act
    inside = pw.in_workspace(path)

    # Assert
    assert inside is False


def test_in_workspace_is_false_when_git_is_missing(tmp_path, monkeypatch):
    # Arrange
    repo = make_repo(tmp_path / "project")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    # Act
    inside = pw.in_workspace(repo / "docs" / "PROMPT.md")

    # Assert
    assert inside is False


def test_ensure_pattern_excluded_ignores_the_name_at_any_depth(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    (repo / "a" / "b").mkdir(parents=True)
    (repo / "a" / "b" / "PROMPT.md").write_text(words())

    # Act
    written = [pw.ensure_pattern_excluded(repo, "PROMPT.md") for _ in range(3)]

    # Assert
    status = run_git(repo, "status", "--porcelain", "--untracked-files=all")
    assert written == [True, False, False]
    assert status == ""


def test_release_tracked_keeps_a_pattern_entry(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    pw.ensure_pattern_excluded(repo, "PROMPT.md")
    commit_file(repo, "PROMPT.md")

    # Act
    released = pw.release_tracked(repo)

    # Assert
    assert released == ()
    assert "PROMPT.md" in pw.managed_entries(repo)
