from __future__ import annotations

from pathlib import Path

import pytest

from _helpers.project_workspace_support import (  # noqa: F401
    commit_file,
    isolated_git_config,
    make_repo,
    pw,
    run_git,
    words,
)


def commit_every_candidate(repo: Path) -> None:
    for name in pw.WORKSPACE_CANDIDATES:
        commit_file(repo, f"{name}/owned.md")


def test_toplevel_returns_the_repository_root(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    nested = repo / "src"
    nested.mkdir()

    # Act
    top = pw.toplevel(nested)

    # Assert
    assert top == repo.resolve()


def test_toplevel_returns_none_outside_a_repository(tmp_path):
    # Arrange
    directory = tmp_path

    # Act
    top = pw.toplevel(directory)

    # Assert
    assert top is None


def test_toplevel_raises_when_git_is_missing(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setenv("PATH", str(tmp_path))

    # Act
    with pytest.raises(pw.WorkspaceError) as raised:
        pw.toplevel(tmp_path)

    # Assert
    assert "git" in str(raised.value)


def test_git_raises_on_a_failing_command(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")

    # Act
    with pytest.raises(pw.WorkspaceError) as raised:
        pw.git(repo, "rev-parse", "--verify", "refs/heads/absent")

    # Assert
    assert "rev-parse" in str(raised.value)


def test_resolve_root_uses_docs_when_absent(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")

    # Act
    root = pw.resolve_root(repo)

    # Assert
    assert root == "docs"


def test_resolve_root_uses_docs_when_it_is_an_empty_directory(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    (repo / "docs").mkdir()

    # Act
    root = pw.resolve_root(repo)

    # Assert
    assert root == "docs"


def test_resolve_root_falls_back_when_the_project_tracks_docs(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/architecture.md")

    # Act
    root = pw.resolve_root(repo)

    # Assert
    assert root == ".work"


def test_resolve_root_falls_back_when_docs_holds_foreign_content(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    (repo / "docs").mkdir()
    (repo / "docs" / "index.html").write_text(words())

    # Act
    root = pw.resolve_root(repo)

    # Assert
    assert root == ".work"


def test_resolve_root_falls_back_when_docs_is_a_file(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    (repo / "docs").write_text(words())

    # Act
    root = pw.resolve_root(repo)

    # Assert
    assert root == ".work"


def test_resolve_root_adopts_docs_holding_a_prompt(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    (repo / "docs").mkdir()
    (repo / "docs" / "PROMPT.md").write_text(words())
    (repo / "docs" / "research.md").write_text(words())

    # Act
    root = pw.resolve_root(repo)

    # Assert
    assert root == "docs"


def test_resolve_root_rejects_a_tracked_prompt(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/PROMPT.md")

    # Act
    root = pw.resolve_root(repo)

    # Assert
    assert root == ".work"


def test_resolve_root_keeps_a_managed_entry_once_it_has_content(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    pw.ensure_excluded(repo, "docs")
    (repo / "docs").mkdir()
    (repo / "docs" / "research.md").write_text(words())

    # Act
    root = pw.resolve_root(repo)

    # Assert
    assert root == "docs"


def test_resolve_root_drops_a_managed_entry_the_project_now_tracks(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    pw.ensure_excluded(repo, "docs")
    commit_file(repo, "docs/guide.md")

    # Act
    root = pw.resolve_root(repo)

    # Assert
    assert root == ".work"


def test_resolve_root_skips_a_tracked_work_directory(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/guide.md")
    commit_file(repo, ".work/pipeline.yml")

    # Act
    root = pw.resolve_root(repo)

    # Assert
    assert root == ".work-local"


def test_resolve_root_raises_when_every_candidate_is_taken(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    commit_every_candidate(repo)

    # Act
    with pytest.raises(pw.WorkspaceError) as raised:
        pw.resolve_root(repo)

    # Assert
    assert "no free workspace" in str(raised.value)


def test_ensure_excluded_writes_the_entry_once(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    gitignore = repo / ".gitignore"
    gitignore.write_text("node_modules/\n")

    # Act
    written = [pw.ensure_excluded(repo, "docs") for _ in range(10)]

    # Assert
    exclude = (repo / ".git" / "info" / "exclude").read_text()
    assert written == [True] + [False] * 9
    assert exclude.count("\n/docs/\n") == 1
    assert gitignore.read_text() == "node_modules/\n"


def test_ensure_excluded_hides_the_workspace_from_status(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    (repo / "docs").mkdir()
    (repo / "docs" / "PROMPT.md").write_text(words())

    # Act
    pw.ensure_excluded(repo, "docs")

    # Assert
    status = run_git(repo, "status", "--porcelain", "--untracked-files=all")
    assert status == ""


def test_ensure_excluded_creates_a_missing_exclude_file(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    info = repo / ".git" / "info"
    (info / "exclude").unlink()
    info.rmdir()

    # Act
    written = pw.ensure_excluded(repo, "docs")

    # Assert
    assert written is True
    assert (info / "exclude").read_text().endswith("/docs/\n")


def test_ensure_excluded_appends_after_a_file_without_trailing_newline(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text("*.log")

    # Act
    pw.ensure_excluded(repo, "docs")

    # Assert
    assert exclude.read_text().splitlines()[0] == "*.log"
    assert pw.managed_entries(repo) == ("docs",)


def test_ensure_excluded_uses_the_common_exclude_in_a_worktree(tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "README.md")
    linked = tmp_path / "linked"
    run_git(repo, "worktree", "add", "-q", "-b", "side", str(linked))

    # Act
    pw.ensure_excluded(linked, "docs")

    # Assert
    assert pw.managed_entries(repo) == ("docs",)
