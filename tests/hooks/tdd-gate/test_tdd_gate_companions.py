from __future__ import annotations
import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _tdd_gate_helpers import HOOK


def test_allows_when_sibling_test_exists(tool_use, run_hook, tmp_path):
    # Arrange
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "calculator.test.ts").write_text("test('x', () => {})")
    target = src_dir / "calculator.ts"
    payload = tool_use("Write", {"file_path": str(target), "content": "export {}"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_when_spec_sibling_exists(tool_use, run_hook, tmp_path):
    # Arrange
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "calculator.spec.ts").write_text("test('x', () => {})")
    target = src_dir / "calculator.ts"
    payload = tool_use("Write", {"file_path": str(target), "content": "export {}"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "companion",
    [
        "databaseExplorerService.integration.test.ts",
        "databaseExplorerService.e2e.spec.ts",
    ],
)
def test_allows_when_a_qualified_sibling_test_exists(
    tool_use, run_hook, tmp_path, companion
):
    # Arrange
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / companion).write_text("test('x', () => {})")
    target = src_dir / "databaseExplorerService.ts"
    payload = tool_use("Write", {"file_path": str(target), "content": "export {}"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_qualified_test_of_another_source_is_not_a_companion(
    tool_use, run_hook, tmp_path
):
    # Arrange
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "databaseExplorerServiceV2.integration.test.ts").write_text(
        "test('x', () => {})"
    )
    target = src_dir / "databaseExplorerService.ts"
    payload = tool_use("Write", {"file_path": str(target), "content": "export {}"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "BLOCKED: creating production source `databaseExplorerService.ts` without a companion",
    )


def test_allows_when_go_test_sibling_exists(tool_use, run_hook, tmp_path):
    # Arrange
    pkg = tmp_path / "internal" / "api"
    pkg.mkdir(parents=True)
    (pkg / "handler_test.go").write_text("package api\n")
    target = pkg / "handler.go"
    payload = tool_use("Write", {"file_path": str(target), "content": "package api"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_when_tests_dir_mirror_exists(tool_use, run_hook, tmp_path):
    # Arrange
    pkg = tmp_path / "src" / "services"
    pkg.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_user.py").write_text("def test_x(): pass\n")
    target = pkg / "user.py"
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_when_nested_tests_subfolder_exists(tool_use, run_hook, tmp_path):
    # Arrange
    pkg = tmp_path / "src"
    pkg.mkdir()
    subtests = pkg / "__tests__"
    subtests.mkdir()
    (subtests / "Button.test.tsx").write_text("test('x', () => {})")
    target = pkg / "Button.tsx"
    payload = tool_use("Write", {"file_path": str(target), "content": "export {}"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_test_directory_outside_the_repository_does_not_satisfy_the_gate(
    tool_use, run_hook, tmp_path
):
    # Arrange
    outer = tmp_path / "home"
    stray = outer / "tests"
    stray.mkdir(parents=True)
    (stray / "test_widget.py").write_text("def test_widget():\n    assert True\n")
    project = outer / "project"
    (project / ".git").mkdir(parents=True)
    (project / "src").mkdir()
    target = project / "src" / "widget.py"
    payload = tool_use(
        "Write",
        {"file_path": str(target), "content": "def widget():\n    return 1\n"},
        cwd=str(project),
    )

    # Act
    result = run_hook("tdd-gate", payload)

    # Assert
    assert_blocked(
        result,
        "BLOCKED: creating production source `widget.py` without a companion test.",
    )


def test_a_repo_local_test_directory_still_satisfies_the_gate(
    tool_use, run_hook, tmp_path
):
    # Arrange
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    (project / "src").mkdir()
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_widget.py").write_text("def test_widget():\n    assert True\n")
    target = project / "src" / "widget.py"
    payload = tool_use(
        "Write",
        {"file_path": str(target), "content": "def widget():\n    return 1\n"},
        cwd=str(project),
    )

    # Act
    result = run_hook("tdd-gate", payload)

    # Assert
    assert_allowed(result)


def test_a_loosely_named_test_is_not_a_companion(tool_use, run_hook, tmp_path):
    # Arrange
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_user_supplied_artifact_guard.py").write_text("def test_x(): pass\n")
    pkg = tmp_path / "src" / "services"
    pkg.mkdir(parents=True)
    target = pkg / "user.py"
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1\n"})

    # Act
    result = run_hook("tdd-gate", payload)

    # Assert
    assert_blocked(result, "without a companion test")


def test_a_precisely_named_test_is_a_companion(tool_use, run_hook, tmp_path):
    # Arrange
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_user.py").write_text("def test_x(): pass\n")
    pkg = tmp_path / "src" / "services"
    pkg.mkdir(parents=True)
    target = pkg / "user.py"
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1\n"})

    # Act
    result = run_hook("tdd-gate", payload)

    # Assert
    assert_allowed(result)


def test_a_sibling_test_for_another_module_does_not_count(tool_use, run_hook, tmp_path):
    # Arrange
    (tmp_path / "src" / "tests").mkdir(parents=True)
    (tmp_path / "src" / "tests" / "test_user_supplied_artifact.py").write_text("x")
    target = tmp_path / "src" / "user.py"
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "BLOCKED")


def test_a_sibling_test_named_for_the_module_counts(tool_use, run_hook, tmp_path):
    # Arrange
    (tmp_path / "src" / "tests").mkdir(parents=True)
    (tmp_path / "src" / "tests" / "test_user.py").write_text("x")
    target = tmp_path / "src" / "user.py"
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
