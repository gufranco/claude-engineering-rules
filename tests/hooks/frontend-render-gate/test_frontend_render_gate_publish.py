from __future__ import annotations

from _ui_evidence_support import (
    GH,
    SHARP,
    decision,
    failing_git,
    git,
    png,
    repo_with_branch,
    run_gate,
)

BUTTON = "src/Button.tsx"
SOURCE = "export const Button = () => null\n"


def _modified(tmp_path):
    return repo_with_branch(tmp_path, {BUTTON: SOURCE}, {BUTTON: SOURCE + "// v2\n"})


def _bash(command: str) -> dict[str, object]:
    return {"command": command}


def test_a_pr_with_a_modified_surface_and_both_images_is_allowed(tmp_path):
    # Arrange
    repo = _modified(tmp_path)
    png(repo / "b.png", SHARP)
    png(repo / "a.png", SHARP)
    command = (
        f"{GH} pr create -b x --attach 'b.png#Before: button' "
        "--attach 'a.png#After: button'"
    )

    # Act
    result = run_gate(_bash(command), repo)

    # Assert
    assert (result.returncode, result.stderr) == (0, "")


def test_an_after_image_without_the_change_marker_is_blocked(tmp_path):
    # Arrange
    repo = repo_with_branch(tmp_path, {}, {"src/Toast.tsx": SOURCE})
    png(repo / "after.png", SHARP)
    command = f"{GH} pr create -b x --attach 'after.png#After: toast'"

    # Act
    result = run_gate(_bash(command), repo, extra_env={"SIPS_STUB_MARKED": "19"})

    # Assert
    assert result.returncode == 2
    assert (
        f"{repo / 'after.png'}: no #FACC15 change marker visible at 360 px wide, "
        "19 of 20 pixels"
    ) in result.stderr
    assert "outline: 8px solid #FACC15" in result.stderr


def test_a_before_image_needs_no_change_marker(tmp_path):
    # Arrange
    repo = _modified(tmp_path)
    png(repo / "b.png", SHARP)
    command = f"{GH} pr create -b x --attach 'b.png#Before: button'"

    # Act
    result = run_gate(_bash(command), repo, extra_env={"SIPS_STUB_MARKED": "0"})

    # Assert
    assert result.returncode == 2
    assert "b.png" not in result.stderr.split("Problems:")[1].split("Capture")[0]
    assert "no high-resolution image labeled After:" in result.stderr


def test_an_after_image_that_cannot_be_decoded_is_blocked(tmp_path):
    # Arrange
    repo = repo_with_branch(tmp_path, {}, {"src/Toast.tsx": SOURCE})
    png(repo / "after.png", SHARP)
    command = f"{GH} pr create -b x --attach 'after.png#After: toast'"

    # Act
    result = run_gate(_bash(command), repo, extra_env={"SIPS_STUB_FAIL": "1"})

    # Assert
    assert result.returncode == 2
    assert (
        f"{repo / 'after.png'}: cannot check the change marker: "
        "sips exited 1: unsupported image"
    ) in result.stderr


def test_an_attachment_under_a_substituted_directory_names_the_substitution(
    tmp_path,
):
    # Arrange
    repo = repo_with_branch(tmp_path, {}, {"src/Toast.tsx": SOURCE})
    command = (
        f"SHOTS=$(mktemp -d) && {GH} pr create -b x "
        '--attach "$SHOTS/after.png#After: toast"'
    )

    # Act
    result = run_gate(_bash(command), repo)

    # Assert
    assert result.returncode == 2
    assert (
        "after.png: names a shell variable this check cannot expand, and a "
        "command substitution counts as one"
    ) in result.stderr
    assert "cannot read" not in result.stderr


def test_a_pr_with_a_modified_surface_and_no_images_is_blocked(tmp_path):
    # Arrange
    repo = _modified(tmp_path)

    # Act
    result = run_gate(_bash(f"{GH} pr create --title t -b 'tweak'"), repo)

    # Assert
    assert result.returncode == 2
    assert "M src/Button.tsx" in result.stderr
    assert "agent-browser set viewport 1440 900 2" in result.stderr
    assert "git worktree add ../before <base>" in result.stderr


def test_an_added_surface_needs_only_an_after_image(tmp_path):
    # Arrange
    repo = repo_with_branch(tmp_path, {}, {"src/Settings.tsx": SOURCE})
    png(repo / "after.png", (1170, 6400))

    # Act
    result = run_gate(_bash(f"{GH} pr create -b x --attach after.png"), repo)

    # Assert
    assert result.returncode == 0


def test_a_low_resolution_capture_is_blocked_with_its_size(tmp_path):
    # Arrange
    repo = _modified(tmp_path)
    png(repo / "b.png", SHARP)
    png(repo / "a.png", (1440, 900))
    command = (
        f"{GH} pr create -b x --attach 'b.png#Before: x' --attach 'a.png#After: x'"
    )

    # Act
    result = run_gate(_bash(command), repo)

    # Assert
    assert result.returncode == 2
    assert "a.png: 1440x900, longer side under 1600 px" in result.stderr


def test_a_missing_attachment_fails_closed(tmp_path):
    # Arrange
    repo = _modified(tmp_path)
    command = (
        f"{GH} pr create -b x --attach 'gone.png#After: x' --attach 'b.png#Before: x'"
    )

    # Act
    result = run_gate(_bash(command), repo)

    # Assert
    assert result.returncode == 2
    assert "gone.png: cannot read" in result.stderr


def test_a_thread_reply_after_a_ui_fix_needs_an_embedded_after_image(tmp_path):
    # Arrange
    repo = _modified(tmp_path)
    command = f"{GH} api repos/a/b/pulls/7/comments/99/replies -X POST -f body='Fixed'"

    # Act
    result = run_gate(_bash(command), repo)

    # Assert
    assert result.returncode == 2
    assert "pull request thread reply" in result.stderr


def test_a_thread_reply_with_uploaded_images_is_allowed(tmp_path):
    # Arrange
    repo = _modified(tmp_path)
    url = "https://github.com/user-attachments/assets/1"
    body = f"Fixed ![Before: old]({url}) ![After: new]({url})"
    command = f"{GH} api repos/a/b/pulls/7/comments/99/replies -X POST -f body='{body}'"

    # Act
    result = run_gate(_bash(command), repo)

    # Assert
    assert result.returncode == 0


def test_an_issue_comment_on_a_ui_branch_needs_images(tmp_path):
    # Arrange
    repo = _modified(tmp_path)

    # Act
    result = run_gate(_bash(f"{GH} issue comment 12 -b 'shipped the fix'"), repo)

    # Assert
    assert result.returncode == 2


def test_desktop_and_tui_surfaces_print_their_recipes(tmp_path):
    # Arrange
    repo = repo_with_branch(
        tmp_path,
        {"ui/main.qml": "Item {}\n", "cli/app.py": "from textual.app import App\n"},
        {
            "ui/main.qml": "Item { id: root }\n",
            "cli/app.py": "from textual.app import App\nX = 1\n",
        },
    )

    # Act
    result = run_gate(_bash(f"{GH} pr create -b x"), repo)

    # Assert
    assert result.returncode == 2
    assert "screencapture -o -l <window-id> after.png" in result.stderr
    assert "agg --font-size 32 run.cast run.gif" in result.stderr


def test_a_deleted_surface_still_needs_a_before_image(tmp_path):
    # Arrange
    repo = repo_with_branch(tmp_path, {BUTTON: SOURCE}, {BUTTON: None})
    png(repo / "a.png", SHARP)

    # Act
    result = run_gate(_bash(f"{GH} pr create -b x --attach 'a.png#After: gone'"), repo)

    # Assert
    assert result.returncode == 2
    assert "no high-resolution image labeled Before:" in result.stderr


def test_a_backend_only_branch_passes(tmp_path):
    # Arrange
    repo = repo_with_branch(tmp_path, {}, {"api/handlers.py": "import json\n"})

    # Act
    result = run_gate(_bash(f"{GH} pr create -b 'faster query'"), repo)

    # Assert
    assert (result.returncode, result.stdout) == (0, "")


def test_an_explicit_base_branch_is_used(tmp_path):
    # Arrange
    repo = _modified(tmp_path)
    git(repo, "branch", "release", "HEAD")

    # Act
    result = run_gate(_bash(f"{GH} pr create --base release -b x"), repo)

    # Assert
    assert result.returncode == 0


def test_an_unreadable_branch_diff_asks_before_a_pr(tmp_path):
    # Arrange
    repo = tmp_path / "plain"
    repo.mkdir()

    # Act
    result = run_gate(_bash(f"{GH} pr create -b x"), repo)

    # Assert
    assert (result.returncode, decision(result)) == (0, "ask")


def test_a_pr_against_another_repository_is_not_judged_by_the_local_diff(tmp_path):
    # Arrange
    repo = _modified(tmp_path)
    git(repo, "remote", "add", "origin", "https://example.test/acme/web.git")

    # Act
    result = run_gate(_bash(f"{GH} pr create -R acme/api -b x"), repo)

    # Assert
    assert (result.returncode, decision(result)) == (0, "ask")


def test_an_issue_describing_an_interface_without_images_asks(tmp_path):
    # Arrange
    repo = repo_with_branch(tmp_path, {}, {"api/x.py": "import json\n"})

    # Act
    result = run_gate(
        _bash(f"{GH} issue create -t t -b 'The checkout button is cut off'"), repo
    )

    # Assert
    assert (result.returncode, decision(result)) == (0, "ask")
    assert "checkout" not in result.stdout


def test_a_tracker_comment_is_judged_by_its_text_not_the_checked_out_branch(
    tmp_path,
):
    # Arrange
    repo = _modified(tmp_path)

    # Act
    result = run_gate(
        {"issueId": "ENG-1", "body": "Synced the Prisma schema with develop"},
        repo,
        tool_name="mcp__linear-acme__save_comment",
    )

    # Assert
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_a_tracker_issue_describing_a_screen_without_an_image_asks(tmp_path):
    # Arrange
    repo = _modified(tmp_path)

    # Act
    result = run_gate(
        {"title": "Queue", "description": "The redemptions page layout changes"},
        repo,
        tool_name="mcp__linear-acme__save_issue",
    )

    # Assert
    assert (result.returncode, decision(result)) == (0, "ask")
    assert "tracker issue" in result.stdout


def test_unrelated_tools_pass(tmp_path):
    # Arrange
    repo = _modified(tmp_path)

    # Act
    result = run_gate({"file_path": "x", "content": "y"}, repo, tool_name="Write")

    # Assert
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_a_ui_commit_with_only_a_tui_import_needs_a_render_check(tmp_path):
    # Arrange
    repo = repo_with_branch(tmp_path, {}, {"README.md": "x\n"})
    (repo / "cli").mkdir()
    (repo / "cli" / "app.py").write_text("import curses\n", encoding="utf-8")
    git(repo, "add", "cli/app.py")

    # Act
    result = run_gate(_bash("git commit -m 'feat: tui'"), repo)

    # Assert
    assert result.returncode == 2
    assert "snap_compare" in result.stderr


def test_a_tui_commit_with_a_snapshot_passes(tmp_path):
    # Arrange
    repo = repo_with_branch(tmp_path, {}, {"README.md": "x\n"})
    (repo / "cli").mkdir()
    (repo / "cli" / "app.py").write_text("import curses\n", encoding="utf-8")
    (repo / "tests" / "__snapshots__").mkdir(parents=True)
    (repo / "tests" / "__snapshots__" / "app.svg").write_text("<svg/>\n")
    git(repo, "add", "-A")

    # Act
    result = run_gate(_bash("git commit -m 'feat: tui'"), repo)

    # Assert
    assert result.returncode == 0


def test_a_failing_branch_diff_asks_before_a_pr(tmp_path):
    # Arrange
    repo = _modified(tmp_path)
    path = failing_git(tmp_path / "stub", "--name-status")

    # Act
    result = run_gate(_bash(f"{GH} pr create -b x"), repo, path=path)

    # Assert
    assert (result.returncode, decision(result)) == (0, "ask")


def test_an_unreadable_tui_source_is_not_treated_as_a_surface(tmp_path):
    # Arrange
    repo = repo_with_branch(tmp_path, {}, {"cli/app.py": "import curses\n"})
    path = failing_git(tmp_path / "stub", "show")

    # Act
    result = run_gate(_bash(f"{GH} pr create -b 'faster query'"), repo, path=path)

    # Assert
    assert (result.returncode, result.stdout) == (0, "")


def test_a_commit_without_git_on_the_path_fails_closed(tmp_path):
    # Arrange
    repo = repo_with_branch(tmp_path, {}, {"README.md": "x\n"})
    empty = tmp_path / "empty"
    empty.mkdir()

    # Act
    result = run_gate(_bash("git commit -m 'feat: x'"), repo, path=str(empty))

    # Assert
    assert result.returncode == 2
    assert "could not list the staged files" in result.stderr


def test_a_pr_against_the_same_repository_by_url_is_judged(tmp_path):
    # Arrange
    repo = _modified(tmp_path)
    git(repo, "remote", "add", "origin", "git@github.com:acme/web.git")

    # Act
    result = run_gate(
        _bash(f"{GH} pr create -R https://github.com/acme/web -b x"), repo
    )

    # Assert
    assert result.returncode == 2


def test_a_lookalike_repository_name_is_not_the_same_repository(tmp_path):
    # Arrange
    repo = _modified(tmp_path)
    git(repo, "remote", "add", "origin", "git@github.com:acme/myweb.git")

    # Act
    result = run_gate(_bash(f"{GH} pr create -R web -b x"), repo)

    # Assert
    assert (result.returncode, decision(result)) == (0, "ask")


def test_a_clean_commit_chained_with_a_pr_still_checks_the_pr(tmp_path):
    # Arrange
    repo = _modified(tmp_path)

    # Act
    result = run_gate(
        _bash(f"git commit --allow-empty -m x && {GH} pr create -b x"), repo
    )

    # Assert
    assert result.returncode == 2
    assert "gh pr create" in result.stderr
