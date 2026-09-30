"""Coverage for the local project workspace helpers.

The workspace is a per-repository folder holding the user's working material
and a continuation prompt. It must never live inside a directory the project
owns, and it must be ignored through the local exclude file only.
"""

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
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
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


def test_toplevel_returns_the_repository_root(tmp_path):
    repo = make_repo(tmp_path / "project")
    nested = repo / "src"
    nested.mkdir()

    top = pw.toplevel(nested)

    assert top == repo.resolve()


def test_toplevel_returns_none_outside_a_repository(tmp_path):
    top = pw.toplevel(tmp_path)

    assert top is None


def test_toplevel_raises_when_git_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(pw.WorkspaceError, match="git"):
        pw.toplevel(tmp_path)


def test_git_raises_on_a_failing_command(tmp_path):
    repo = make_repo(tmp_path / "project")

    with pytest.raises(pw.WorkspaceError, match="rev-parse"):
        pw.git(repo, "rev-parse", "--verify", "refs/heads/absent")


def test_resolve_root_uses_docs_when_absent(tmp_path):
    repo = make_repo(tmp_path / "project")

    root = pw.resolve_root(repo)

    assert root == "docs"


def test_resolve_root_uses_docs_when_it_is_an_empty_directory(tmp_path):
    repo = make_repo(tmp_path / "project")
    (repo / "docs").mkdir()

    root = pw.resolve_root(repo)

    assert root == "docs"


def test_resolve_root_falls_back_when_the_project_tracks_docs(tmp_path):
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/architecture.md")

    root = pw.resolve_root(repo)

    assert root == ".work"


def test_resolve_root_falls_back_when_docs_holds_foreign_content(tmp_path):
    repo = make_repo(tmp_path / "project")
    (repo / "docs").mkdir()
    (repo / "docs" / "index.html").write_text(words())

    root = pw.resolve_root(repo)

    assert root == ".work"


def test_resolve_root_falls_back_when_docs_is_a_file(tmp_path):
    repo = make_repo(tmp_path / "project")
    (repo / "docs").write_text(words())

    root = pw.resolve_root(repo)

    assert root == ".work"


def test_resolve_root_adopts_docs_holding_a_prompt(tmp_path):
    repo = make_repo(tmp_path / "project")
    (repo / "docs").mkdir()
    (repo / "docs" / "PROMPT.md").write_text(words())
    (repo / "docs" / "research.md").write_text(words())

    root = pw.resolve_root(repo)

    assert root == "docs"


def test_resolve_root_rejects_a_tracked_prompt(tmp_path):
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/PROMPT.md")

    root = pw.resolve_root(repo)

    assert root == ".work"


def test_resolve_root_keeps_a_managed_entry_once_it_has_content(tmp_path):
    repo = make_repo(tmp_path / "project")
    pw.ensure_excluded(repo, "docs")
    (repo / "docs").mkdir()
    (repo / "docs" / "research.md").write_text(words())

    root = pw.resolve_root(repo)

    assert root == "docs"


def test_resolve_root_drops_a_managed_entry_the_project_now_tracks(tmp_path):
    repo = make_repo(tmp_path / "project")
    pw.ensure_excluded(repo, "docs")
    commit_file(repo, "docs/guide.md")

    root = pw.resolve_root(repo)

    assert root == ".work"


def test_resolve_root_skips_a_tracked_work_directory(tmp_path):
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/guide.md")
    commit_file(repo, ".work/pipeline.yml")

    root = pw.resolve_root(repo)

    assert root == ".work-local"


def test_resolve_root_raises_when_every_candidate_is_taken(tmp_path):
    repo = make_repo(tmp_path / "project")
    for name in pw.WORKSPACE_CANDIDATES:
        commit_file(repo, f"{name}/owned.md")

    with pytest.raises(pw.WorkspaceError, match="no free workspace"):
        pw.resolve_root(repo)


def test_ensure_excluded_writes_the_entry_once(tmp_path):
    repo = make_repo(tmp_path / "project")
    gitignore = repo / ".gitignore"
    gitignore.write_text("node_modules/\n")

    written = [pw.ensure_excluded(repo, "docs") for _ in range(10)]

    exclude = (repo / ".git" / "info" / "exclude").read_text()
    assert written == [True] + [False] * 9
    assert exclude.count("\n/docs/\n") == 1
    assert gitignore.read_text() == "node_modules/\n"


def test_ensure_excluded_hides_the_workspace_from_status(tmp_path):
    repo = make_repo(tmp_path / "project")
    write_prompt(repo)

    status = run_git(repo, "status", "--porcelain", "--untracked-files=all")

    assert status == ""


def test_ensure_excluded_creates_a_missing_exclude_file(tmp_path):
    repo = make_repo(tmp_path / "project")
    info = repo / ".git" / "info"
    (info / "exclude").unlink()
    info.rmdir()

    written = pw.ensure_excluded(repo, "docs")

    assert written is True
    assert (info / "exclude").read_text().endswith("/docs/\n")


def test_ensure_excluded_appends_after_a_file_without_trailing_newline(tmp_path):
    repo = make_repo(tmp_path / "project")
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text("*.log")

    pw.ensure_excluded(repo, "docs")

    assert exclude.read_text().splitlines()[0] == "*.log"
    assert pw.managed_entries(repo) == ("docs",)


def test_ensure_excluded_uses_the_common_exclude_in_a_worktree(tmp_path):
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "README.md")
    linked = tmp_path / "linked"
    run_git(repo, "worktree", "add", "-q", "-b", "side", str(linked))

    pw.ensure_excluded(linked, "docs")

    assert pw.managed_entries(repo) == ("docs",)


def test_managed_entries_ignores_unmarked_lines(tmp_path):
    repo = make_repo(tmp_path / "project")
    (repo / ".git" / "info" / "exclude").write_text("/docs/\n/build/\n")

    entries = pw.managed_entries(repo)

    assert entries == ()


def test_prompt_is_stale_is_false_on_a_clean_tree(tmp_path):
    repo = make_repo(tmp_path / "project")

    stale = pw.prompt_is_stale(repo, "docs")

    assert stale is False


def test_prompt_is_stale_when_a_change_exists_and_no_prompt(tmp_path):
    repo = make_repo(tmp_path / "project")
    (repo / "main.py").write_text(words())

    stale = pw.prompt_is_stale(repo, "docs")

    assert stale is True


def test_prompt_is_stale_when_a_change_is_newer_than_the_prompt(tmp_path):
    repo = make_repo(tmp_path / "project")
    prompt = write_prompt(repo)
    age(prompt, 600)
    (repo / "main.py").write_text(words())

    stale = pw.prompt_is_stale(repo, "docs")

    assert stale is True


def test_prompt_is_fresh_when_written_after_the_change(tmp_path):
    repo = make_repo(tmp_path / "project")
    change = repo / "main.py"
    change.write_text(words())
    age(change, 600)
    write_prompt(repo)

    stale = pw.prompt_is_stale(repo, "docs")

    assert stale is False


def test_prompt_is_stale_after_a_newer_commit_by_the_user(tmp_path):
    repo = make_repo(tmp_path / "project")
    prompt = write_prompt(repo)
    age(prompt, 600)
    commit_file(repo, "main.py")

    stale = pw.prompt_is_stale(repo, "docs")

    assert stale is True


def test_prompt_ignores_commits_by_other_authors(tmp_path):
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

    stale = pw.prompt_is_stale(repo, "docs")

    assert stale is False


def test_prompt_ignores_commits_when_no_user_email_is_set(tmp_path):
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "main.py")
    prompt = write_prompt(repo)
    age(prompt, 600)
    run_git(repo, "config", "--unset", "user.email")

    stale = pw.prompt_is_stale(repo, "docs")

    assert stale is False


def test_prompt_is_stale_skips_a_deleted_file(tmp_path):
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "main.py")
    (repo / "main.py").unlink()
    write_prompt(repo)

    stale = pw.prompt_is_stale(repo, "docs")

    assert stale is False


def test_prompt_path_joins_the_root(tmp_path):
    path = pw.prompt_path(tmp_path, ".work")

    assert path == tmp_path / ".work" / "PROMPT.md"


def test_release_tracked_removes_an_entry_the_project_now_tracks(tmp_path):
    repo = make_repo(tmp_path / "project")
    pw.ensure_excluded(repo, "docs")
    pw.ensure_excluded(repo, ".work")
    commit_file(repo, "docs/guide.md")

    released = pw.release_tracked(repo)

    assert released == ("docs",)
    assert pw.managed_entries(repo) == (".work",)


def test_release_tracked_keeps_unrelated_exclude_lines(tmp_path):
    repo = make_repo(tmp_path / "project")
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text("*.log\n")
    pw.ensure_excluded(repo, "docs")
    commit_file(repo, "docs/guide.md")

    pw.release_tracked(repo)

    assert exclude.read_text() == "*.log\n"


def test_release_tracked_is_a_no_op_without_tracked_entries(tmp_path):
    repo = make_repo(tmp_path / "project")
    pw.ensure_excluded(repo, "docs")
    before = (repo / ".git" / "info" / "exclude").read_text()

    released = pw.release_tracked(repo)

    assert released == ()
    assert (repo / ".git" / "info" / "exclude").read_text() == before


def test_release_tracked_without_an_exclude_file(tmp_path):
    repo = make_repo(tmp_path / "project")
    (repo / ".git" / "info" / "exclude").unlink()

    released = pw.release_tracked(repo)

    assert released == ()


def test_in_workspace_is_true_for_a_new_file_in_the_workspace(tmp_path):
    repo = make_repo(tmp_path / "project")

    inside = pw.in_workspace(repo / "docs" / "plans" / "x" / "plan.md")

    assert inside is True


def test_in_workspace_is_false_for_a_project_owned_docs(tmp_path):
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/guide.md")

    inside = pw.in_workspace(repo / "docs" / "notes.md")

    assert inside is False


def test_in_workspace_is_false_outside_a_repository(tmp_path):
    inside = pw.in_workspace(tmp_path / "docs" / "notes.md")

    assert inside is False


def test_in_workspace_is_false_when_git_is_missing(tmp_path, monkeypatch):
    repo = make_repo(tmp_path / "project")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    inside = pw.in_workspace(repo / "docs" / "PROMPT.md")

    assert inside is False
