"""Coverage for the scope-guard hook.

Source rule: rules/surgical-edits.md.
"""

from __future__ import annotations

import os
import time

import pytest

HOOK = "scope-guard"


def make_plan(tmp_path, paths: list[str]) -> str:
    """Create a freshly-modified plan.md with the given declared paths."""
    spec_dir = tmp_path / "specs" / "2026-05-29-feature"
    spec_dir.mkdir(parents=True)
    body = ["# Plan", "", "## Task breakdown", ""]
    for i, p in enumerate(paths, start=1):
        body.append(f"{i}. Update `{p}` with new behavior.")
    plan = spec_dir / "plan.md"
    plan.write_text("\n".join(body))
    # ensure mtime is now (within window)
    os.utime(plan, (time.time(), time.time()))
    return str(plan)


# ---------------------------------------------------------------------------
# No active plan -> allow
# ---------------------------------------------------------------------------


def test_allows_when_no_specs_dir(tool_use, assert_allows, tmp_path):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "x.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_when_plan_is_stale(tool_use, assert_allows, tmp_path):
    # Arrange
    plan_str = make_plan(tmp_path, ["hooks/foo.py"])
    # Force mtime to >60min ago
    old = time.time() - 7200
    os.utime(plan_str, (old, old))
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/bar.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_when_plan_has_no_paths(tool_use, assert_allows, tmp_path):
    # Arrange
    spec_dir = tmp_path / "specs" / "2026-05-29-x"
    spec_dir.mkdir(parents=True)
    (spec_dir / "plan.md").write_text("# Plan\n\nNo paths here, just prose.\n")
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/foo.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# In-scope edits -> allow
# ---------------------------------------------------------------------------


def test_allows_when_target_in_plan(tool_use, assert_allows, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py", "tests/hooks/foo/test_foo.py"])
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/foo.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_edits_to_spec_folder_itself(tool_use, assert_allows, tmp_path):
    # Arrange
    plan_str = make_plan(tmp_path, ["hooks/foo.py"])
    plan_path = tmp_path / "specs" / "2026-05-29-feature" / "plan.md"
    payload = tool_use(
        "Edit",
        {"file_path": str(plan_path), "old_string": "x", "new_string": "y"},
        cwd=str(tmp_path),
    )
    assert plan_str  # silence unused

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_when_target_matches_directory_declaration(
    tool_use, assert_allows, tmp_path
):
    # Arrange
    make_plan(tmp_path, ["hooks/"])
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/new-hook.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Out-of-scope -> advisory (exit 2 / ask)
# ---------------------------------------------------------------------------


def test_blocks_when_target_outside_scope(tool_use, assert_blocks, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py", "tests/hooks/foo/test_foo.py"])
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/unrelated.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "not listed in the active plan")


def test_blocks_when_editing_unrelated_test(tool_use, assert_blocks, tmp_path):
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

    # Act / Assert
    assert_blocks(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: irrelevant tools
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool_name", ["Bash", "Read", "Grep", "Glob"])
def test_allows_unrelated_tools(tool_use, assert_allows, tool_name, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use(tool_name, {"command": "ls"}, cwd=str(tmp_path))

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Bypass + robustness
# ---------------------------------------------------------------------------


def test_bypass_env_var_disables_check(tool_use, assert_allows, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "hooks/other.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"SCOPE_GUARD_DISABLE": "1"})


def test_handles_missing_file_path(tool_use, assert_allows, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py"])
    payload = tool_use("Write", {}, cwd=str(tmp_path))

    # Act / Assert
    assert_allows(HOOK, payload)


def test_handles_explicit_cwd_with_no_plan(tool_use, assert_allows, tmp_path):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "x.py"), "content": "x"},
        cwd=str(tmp_path),
    )

    # Act / Assert
    assert_allows(HOOK, payload)
