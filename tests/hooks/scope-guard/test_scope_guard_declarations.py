from __future__ import annotations
import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _scope_guard_helpers import HOOK, edit_payload, make_plan


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


def test_ignores_flag_tokens_in_the_plan(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py", "--out=dist/app.js"])

    # Act
    result = run_hook(HOOK, edit_payload(tool_use, tmp_path, "dist/app.js"))

    # Assert
    assert_blocked(
        result, "BLOCKED: editing `app.js` which is not listed in the active plan `"
    )


def test_ignores_bare_extensions_in_the_plan(tool_use, run_hook, tmp_path):
    # Arrange
    make_plan(tmp_path, ["hooks/foo.py", ".csv"])

    # Act
    result = run_hook(HOOK, edit_payload(tool_use, tmp_path, "data/rows.csv"))

    # Assert
    assert_blocked(
        result, "BLOCKED: editing `rows.csv` which is not listed in the active plan `"
    )


def test_a_directory_declaration_covers_the_directory_path(
    tool_use, run_hook, tmp_path
):
    # Arrange
    make_plan(tmp_path, ["build/"])

    # Act
    result = run_hook(HOOK, edit_payload(tool_use, tmp_path, "build"))

    # Assert
    assert_allowed(result)
