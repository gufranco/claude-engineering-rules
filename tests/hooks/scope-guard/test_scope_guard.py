from __future__ import annotations

import json

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

TESTS_ROOT = Path(__file__).resolve().parents[2]
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
from _helpers.cov_env import apply_coverage_env  # noqa: E402

HOOK = "scope-guard"


def make_plan(tmp_path, paths: list[str]) -> str:
    spec_dir = tmp_path / "specs" / "2026-05-29-feature"
    spec_dir.mkdir(parents=True)
    body = ["# Plan", "", "## Task breakdown", ""]
    for i, p in enumerate(paths, start=1):
        body.append(f"{i}. Update `{p}` with new behavior.")
    plan = spec_dir / "plan.md"
    plan.write_text("\n".join(body))
    os.utime(plan, (time.time(), time.time()))
    return str(plan)


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


def test_allows_when_plan_has_no_paths(tool_use, run_hook, tmp_path):
    # Arrange
    spec_dir = tmp_path / "specs" / "2026-05-29-x"
    spec_dir.mkdir(parents=True)
    (spec_dir / "plan.md").write_text("# Plan\n\nNo paths here, just prose.\n")
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/foo.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_when_target_in_plan(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py", "tests/hooks/foo/test_foo.py"])
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/foo.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_edits_to_spec_folder_itself(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    plan_path = tmp_path / "specs" / "2026-05-29-feature" / "plan.md"
    payload = tool_use(
        "Edit",
        {"file_path": str(plan_path), "old_string": "x", "new_string": "y"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_when_target_matches_directory_declaration(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/"])
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/new-hook.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_when_target_outside_scope(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py", "tests/hooks/foo/test_foo.py"])
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/unrelated.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "add its path to the plan")


@pytest.mark.parametrize("name", ["Makefile", "Dockerfile", "Justfile", "LICENSE"])
def test_allows_an_extensionless_file_declared_in_the_plan(
    tool_use, run_hook, tmp_path, name
):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py", name])
    payload = tool_use(
        "Edit",
        {"file_path": str(tmp_path / name), "old_string": "a", "new_string": "b"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_an_undeclared_extensionless_file(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use(
        "Edit",
        {"file_path": str(tmp_path / "Makefile"), "old_string": "a", "new_string": "b"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "not listed in the active plan")


def test_blocks_when_editing_unrelated_test(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use(
        "Edit",
        {
            "file_path": str(tmp_path / "tests/hooks/bar/test_bar.py"),
            "old_string": "x",
            "new_string": "y",
        },
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


@pytest.mark.parametrize("tool_name", ["Bash", "Read", "Grep", "Glob"])
def test_allows_unrelated_tools(tool_use, run_hook, tool_name, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use(tool_name, {"command": "ls"}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bypass_env_var_disables_check(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/other.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload, env={"SCOPE_GUARD_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_handles_missing_file_path(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use("Write", {}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_handles_explicit_cwd_with_no_plan(tool_use, run_hook, tmp_path):
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


def write_plan(directory, paths: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    body = ["# Plan", "", "## Task breakdown", ""]
    for index, path in enumerate(paths, start=1):
        body.append(f"{index}. Update `{path}` with new behavior.")
    plan = directory / "plan.md"
    plan.write_text("\n".join(body))
    os.utime(plan, (time.time(), time.time()))


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
    _code, stderr = assert_blocked(result)
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


def edit_payload(tool_use, tmp_path, rel: str) -> dict:
    return tool_use(
        "Edit",
        {"file_path": str(tmp_path / rel), "old_string": "a", "new_string": "b"},
        cwd=str(tmp_path),
    )


def test_ignores_flag_tokens_in_the_plan(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py", "--out=dist/app.js"])

    # Act
    result = run_hook(HOOK, edit_payload(tool_use, tmp_path, "dist/app.js"))

    # Assert
    assert_blocked(result)


def test_ignores_bare_extensions_in_the_plan(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py", ".csv"])

    # Act
    result = run_hook(HOOK, edit_payload(tool_use, tmp_path, "data/rows.csv"))

    # Assert
    assert_blocked(result)


def test_a_directory_declaration_covers_the_directory_path(
    tool_use, run_hook, tmp_path
):
    # Arrange
    make_plan(tmp_path, ["build/"])

    # Act
    result = run_hook(HOOK, edit_payload(tool_use, tmp_path, "build"))

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


def test_malformed_payload_blocks():
    # Arrange
    hook = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input="not json",
        capture_output=True,
        text=True,
        env=apply_coverage_env({**os.environ, "CLAUDE_BYPASS_STATE": os.devnull}),
        check=False,
    )

    # Assert
    assert proc.returncode == 2


@pytest.mark.parametrize("root", ["docs", ".work", ".work-local"])
def test_a_workspace_plan_governs_the_repository(tool_use, run_hook, tmp_path, root):
    # Arrange
    spec_dir = tmp_path / root / "plans" / "2026-09-30-feature"
    spec_dir.mkdir(parents=True)
    (spec_dir / "plan.md").write_text("# Plan\n\n1. Update `hooks/foo.py`.\n")

    # Act
    result = run_hook(HOOK, edit_payload(tool_use, tmp_path, "hooks/unrelated.py"))

    # Assert
    assert_blocked(result)


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
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
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


def test_the_block_is_reported_as_a_deny_decision(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/unrelated.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    decision = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]
    assert (result.code, decision) == (2, "deny")
