from __future__ import annotations
import os
import subprocess
import time
from pathlib import Path
import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _scope_guard_helpers import HOOK, edit_payload, make_plan, write_plan


def test_allows_when_no_specs_dir(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "x.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_when_plan_is_stale(tool_use, run_hook, tmp_path):
    # Arrange
    plan_str = make_plan(tmp_path, ["hooks/foo.py"])
    old = time.time() - 7200
    os.utime(plan_str, (old, old))
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/bar.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_plan_outside_the_repository_never_governs_it(tool_use, run_hook, tmp_path):
    # Arrange
    home = tmp_path / "home"
    write_plan(home / ".claude" / "specs" / "2026-08-18-other", ["hooks/unrelated.py"])
    project = home / "dungeon-master-nochip"
    (project / ".git").mkdir(parents=True)
    target = project / ".github" / "dependabot.yml"
    target.parent.mkdir(parents=True)
    target.write_text("version: 2\n")
    payload = tool_use(
        "Write",
        {"file_path": str(target), "content": "version: 2\n"},
        cwd=str(project),
    )

    # Act
    result = run_hook("scope-guard", payload)

    # Assert
    assert_allowed(result)


def test_the_nearest_plan_wins_over_a_newer_outer_one(tool_use, run_hook, tmp_path):
    # Arrange
    home = tmp_path / "home"
    project = home / "project"
    (project / ".git").mkdir(parents=True)
    write_plan(project / "specs" / "2026-08-18-local", ["src/declared.py"])
    outer = home / ".claude" / "specs" / "2026-08-18-outer"
    write_plan(outer, ["anything/at/all.py"])
    later = time.time() + 60
    os.utime(outer / "plan.md", (later, later))
    target = project / "src" / "undeclared.py"
    target.parent.mkdir(parents=True)
    payload = tool_use(
        "Write",
        {"file_path": str(target), "content": "x = 1\n"},
        cwd=str(project),
    )

    # Act
    result = run_hook("scope-guard", payload)

    # Assert
    _code, stderr = assert_blocked(
        result,
        "BLOCKED: editing `undeclared.py` which is not listed in the active plan `",
    )
    assert "2026-08-18-local" in stderr


def test_a_repo_local_plan_still_governs_its_own_repository(
    tool_use, run_hook, tmp_path
):
    # Arrange
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    write_plan(project / "specs" / "2026-08-18-local", ["src/declared.py"])
    target = project / "src" / "declared.py"
    target.parent.mkdir(parents=True)
    payload = tool_use(
        "Write",
        {"file_path": str(target), "content": "x = 1\n"},
        cwd=str(project),
    )

    # Act
    result = run_hook("scope-guard", payload)

    # Assert
    assert_allowed(result)


def test_a_file_outside_the_governed_repository_is_left_alone(
    tool_use, run_hook, tmp_path
):
    # Arrange
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    write_plan(project / "specs" / "2026-09-28-local", ["src/declared.py"])
    vault = tmp_path / "second-brain"
    target = vault / "wiki" / "concepts" / "A note.md"
    target.parent.mkdir(parents=True)
    payload = tool_use(
        "Write",
        {"file_path": str(target), "content": "note\n"},
        cwd=str(project),
    )

    # Act
    result = run_hook("scope-guard", payload)

    # Assert
    assert_allowed(result)


def test_skips_a_plan_that_cannot_be_stat(tool_use, run_hook, tmp_path):
    # Arrange
    spec_dir = tmp_path / "specs" / "2026-05-29-broken"
    spec_dir.mkdir(parents=True)
    (spec_dir / "plan.md").symlink_to(tmp_path / "absent.md")

    # Act
    result = run_hook(HOOK, edit_payload(tool_use, tmp_path, "hooks/foo.py"))

    # Assert
    assert_allowed(result)


def test_skips_a_plan_that_cannot_be_read(tool_use, run_hook, tmp_path):
    # Arrange
    plan = make_plan(tmp_path, ["hooks/foo.py"])
    os.chmod(plan, 0)

    # Act
    result = run_hook(HOOK, edit_payload(tool_use, tmp_path, "hooks/other.py"))

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize("root", ["docs", ".work", ".work-local"])
def test_a_workspace_plan_governs_the_repository(tool_use, run_hook, tmp_path, root):
    # Arrange
    spec_dir = tmp_path / root / "plans" / "2026-09-30-feature"
    spec_dir.mkdir(parents=True)
    (spec_dir / "plan.md").write_text("# Plan\n\n1. Update `hooks/foo.py`.\n")

    # Act
    result = run_hook(HOOK, edit_payload(tool_use, tmp_path, "hooks/unrelated.py"))

    # Assert
    assert_blocked(
        result,
        "BLOCKED: editing `unrelated.py` which is not listed in the active plan `",
    )


@pytest.mark.parametrize(
    "stamp", ["Archived: 2026-10-02", "**Superseded:** 2026-10-02. Replaced."]
)
def test_a_closed_plan_no_longer_governs(tool_use, run_hook, tmp_path, stamp):
    # Arrange
    plan = Path(make_plan(tmp_path, ["hooks/foo.py"]))
    plan.write_text(f"# Plan\n\n{stamp}\n\n" + plan.read_text())
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/unrelated.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_stamp_word_in_the_body_keeps_the_plan_active(tool_use, run_hook, tmp_path):
    # Arrange
    plan = Path(make_plan(tmp_path, ["hooks/foo.py"]))
    plan.write_text(plan.read_text() + "\n\nThe old flow was Archived: never.\n")
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/unrelated.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "add its path to the plan")


def test_a_note_inside_the_never_committed_workspace_is_not_gated(
    tool_use, run_hook, tmp_path
):
    # Arrange
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=30)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PROMPT.md").write_text("continue\n")
    spec_dir = tmp_path / "docs" / "plans" / "2026-10-12-feature"
    spec_dir.mkdir(parents=True)
    (spec_dir / "plan.md").write_text("# Plan\n\n1. Update `hooks/foo.py`.\n")
    note = tmp_path / "docs" / "research" / "inventory.md"
    note.parent.mkdir(parents=True)
    note.write_text("a\n")
    payload = edit_payload(tool_use, tmp_path, "docs/research/inventory.md")

    # Act
    exit_code, stdout, _ = run_hook(HOOK, payload)

    # Assert
    assert (exit_code, stdout) == (0, "")
