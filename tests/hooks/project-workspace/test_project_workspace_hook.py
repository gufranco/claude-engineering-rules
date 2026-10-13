from __future__ import annotations

import json

from _ppw_support import (
    claim_docs_with_stale_prompt,
    commit_file,
    commit_owned_folders,
    exclude_text,
    make_repo,
    run_git,
    start,
    stop,
    words,
)


def test_start_claims_docs_in_the_exclude_file(run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")

    # Act
    code, stdout, _ = start(run_hook, repo)

    # Assert
    assert (code, stdout) == (0, "")
    assert "\n/docs/\n" in exclude_text(repo)


def test_start_excludes_prompt_files_at_any_depth(run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")

    # Act
    start(run_hook, repo)

    # Assert
    assert "\nPROMPT.md\n" in exclude_text(repo)


def test_start_claims_work_when_the_project_tracks_docs(run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/guide.md")

    # Act
    code, _, _ = start(run_hook, repo)

    # Assert
    assert code == 0
    assert "\n/.work/\n" in exclude_text(repo)
    assert "/docs/" not in exclude_text(repo)


def test_start_never_touches_project_files(run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/guide.md")
    commit_file(repo, ".gitignore")
    before = run_git(repo, "status", "--porcelain", "--untracked-files=all")

    # Act
    code, _, _ = start(run_hook, repo)

    # Assert
    after = run_git(repo, "status", "--porcelain", "--untracked-files=all")
    assert code == 0
    assert (before, after) == ("", "")


def test_start_releases_a_folder_the_project_began_tracking(run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    start(run_hook, repo)
    commit_file(repo, "docs/guide.md")

    # Act
    start(run_hook, repo)

    # Assert
    assert "/docs/" not in exclude_text(repo)
    assert "\n/.work/\n" in exclude_text(repo)


def test_start_is_silent_outside_a_repository(run_hook, tmp_path):
    # Arrange
    outside = tmp_path

    # Act
    code, stdout, stderr = start(run_hook, outside)

    # Assert
    assert (code, stdout, stderr) == (0, "", "")


def test_start_writes_nothing_when_git_is_missing(run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    before = exclude_text(repo)

    # Act
    code, stdout, stderr = start(run_hook, repo, env={"PATH": str(tmp_path)})

    # Assert
    assert (code, stdout) == (0, "")
    assert "project-workspace" in stderr
    assert exclude_text(repo) == before


def test_stop_blocks_when_the_prompt_is_stale(run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    claim_docs_with_stale_prompt(run_hook, repo)

    # Act
    code, stdout, _ = stop(run_hook, repo)

    # Assert
    decision = json.loads(stdout)
    assert code == 0
    assert decision["decision"] == "block"
    assert "docs/PROMPT.md" in decision["reason"]


def test_stop_allows_the_second_stop_in_a_chain(run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    claim_docs_with_stale_prompt(run_hook, repo)

    # Act
    code, stdout, _ = stop(run_hook, repo, active=True)

    # Assert
    assert (code, stdout) == (0, "")


def test_stop_allows_a_clean_tree(run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")

    # Act
    code, stdout, _ = stop(run_hook, repo)

    # Assert
    assert (code, stdout) == (0, "")


def test_stop_allows_outside_a_repository(run_hook, tmp_path):
    # Arrange
    outside = tmp_path

    # Act
    code, stdout, _ = stop(run_hook, outside)

    # Assert
    assert (code, stdout) == (0, "")


def test_stop_names_the_fallback_folder(run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    commit_file(repo, "docs/guide.md")
    (repo / "main.py").write_text(words())

    # Act
    code, stdout, _ = stop(run_hook, repo)

    # Assert
    assert code == 0
    assert ".work/PROMPT.md" in json.loads(stdout)["reason"]


def test_stop_allows_and_logs_when_no_folder_is_free(run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    commit_owned_folders(repo, ("docs", ".work", ".work-local"))
    (repo / "main.py").write_text(words())

    # Act
    code, stdout, stderr = stop(run_hook, repo)

    # Assert
    assert (code, stdout) == (0, "")
    assert "no free workspace" in stderr
