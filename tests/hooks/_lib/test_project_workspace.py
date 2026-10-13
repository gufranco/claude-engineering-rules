from __future__ import annotations

import os
import random
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import project_workspace as pw  # noqa: E402

RNG = random.Random(20260930)


@pytest.fixture(autouse=True)
def isolated_git_config(monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def words(count: int = 4) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    return " ".join(
        "".join(RNG.choice(alphabet) for _ in range(RNG.randint(3, 9)))
        for _ in range(count)
    )


def run_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, timeout=30
    ).stdout


def make_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    run_git(root, "init", "-q", "-b", "main")
    run_git(root, "config", "user.email", f"{words(1)}@example.org")
    run_git(root, "config", "user.name", words(2))
    run_git(root, "config", "commit.gpgsign", "false")
    return root


def commit_file(repo: Path, rel: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(words())
    run_git(repo, "add", "-f", "--", rel)
    run_git(repo, "commit", "-q", "--no-verify", "-m", "add file")


def age(path: Path, seconds: float) -> None:
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


def write_prompt(repo: Path, root: str = "docs") -> Path:
    pw.ensure_excluded(repo, root)
    (repo / root).mkdir(exist_ok=True)
    prompt = repo / root / "PROMPT.md"
    prompt.write_text(words())
    return prompt


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
