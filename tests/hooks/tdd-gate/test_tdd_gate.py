from __future__ import annotations

from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
import subprocess
import sys

HOOK = "tdd-gate"


@pytest.mark.parametrize(
    "rel_path",
    [
        "src/services/user.py",
        "src/components/Button.tsx",
        "src/utils/format.js",
        "internal/api/handler.go",
        "lib/calculator.rb",
        "app/models/Order.kt",
    ],
)
def test_blocks_new_production_source_without_test(
    tool_use, run_hook, tmp_path, rel_path
):
    # Arrange
    target = tmp_path / rel_path
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "without a companion test")


def test_blocks_typescript_service(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "src/api/orders.service.ts"
    payload = tool_use("Write", {"file_path": str(target), "content": "export {}"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "BLOCKED")


@pytest.mark.parametrize(
    "rel_path",
    [
        "src/services/user.test.ts",
        "src/services/user.spec.ts",
        "src/services/user_test.go",
        "tests/services/test_user.py",
        "__tests__/Button.test.tsx",
        "spec/calculator_spec.rb",
        "e2e/checkout.spec.ts",
    ],
)
def test_allows_test_file_creation(tool_use, run_hook, tmp_path, rel_path):
    # Arrange
    target = tmp_path / rel_path
    payload = tool_use(
        "Write", {"file_path": str(target), "content": "test('x', () => {})"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "rel_path",
    [
        "docs/README.md",
        "config/app.yaml",
        "package.json",
        "tsconfig.json",
        "schema.prisma",
        ".env.example",
        "Dockerfile",
        "Makefile",
    ],
)
def test_allows_non_source_files(tool_use, run_hook, tmp_path, rel_path):
    # Arrange
    target = tmp_path / rel_path
    payload = tool_use("Write", {"file_path": str(target), "content": "x"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "rel_path",
    [
        "node_modules/foo/index.js",
        "dist/bundle.js",
        "build/output.ts",
        ".next/server/page.js",
        "migrations/0001_init.ts",
        "vendor/third-party/lib.go",
        "coverage/lcov.info",
    ],
)
def test_allows_excluded_directories(tool_use, run_hook, tmp_path, rel_path):
    # Arrange
    target = tmp_path / rel_path
    payload = tool_use("Write", {"file_path": str(target), "content": "x"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "rel_path",
    [
        "src/types/api.d.ts",
        "public/app.min.js",
        "static/vendor.bundle.js",
        "src/proto/schema.generated.ts",
    ],
)
def test_allows_generated_and_minified_files(tool_use, run_hook, tmp_path, rel_path):
    # Arrange
    target = tmp_path / rel_path
    payload = tool_use("Write", {"file_path": str(target), "content": "x"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


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
    assert_blocked(result)


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


def test_allows_edit_of_existing_file(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "src" / "user.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n")
    payload = tool_use(
        "Edit",
        {
            "file_path": str(target),
            "old_string": "x = 1",
            "new_string": "x = 2",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_write_overwriting_existing_file(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "src" / "user.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n")
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 2\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize("tool_name", ["Bash", "Read", "Grep", "Glob", "WebFetch"])
def test_allows_unrelated_tools(tool_use, run_hook, tool_name):
    # Arrange
    payload = tool_use(tool_name, {"command": "echo hi"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bypass_env_var_disables_check(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "src/user.py"
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1"})

    # Act
    result = run_hook(HOOK, payload, env={"TDD_GATE_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_handles_missing_tool_input(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write")

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_handles_empty_file_path(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": "", "content": "x"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "rel_path",
    [
        "tsup.config.ts",
        "vite.config.ts",
        "jest.config.js",
        "src/__init__.py",
        "tests/conftest.py",
        "setup.py",
        "src/types.ts",
        "src/types.py",
    ],
)
def test_allows_config_and_declaration_files(tool_use, run_hook, tmp_path, rel_path):
    # Arrange
    target = tmp_path / rel_path
    payload = tool_use(
        "Write", {"file_path": str(target), "content": "export default {}"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "content",
    [
        "export * from './a';\nexport { b } from './b';",
        "import { x } from './x';\nexport { x };",
        "export {\n  a,\n  b,\n} from './ab';",
        "export type { T } from './t';",
        "",
    ],
)
def test_allows_barrel_index(tool_use, run_hook, tmp_path, content):
    # Arrange
    target = tmp_path / "src/index.ts"
    payload = tool_use("Write", {"file_path": str(target), "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "content",
    [
        "export function compute(x) { return x * 2; }",
        "export * from './a';\nexport const K = 1;",
        "const internal = 1;\nexport { internal };",
    ],
)
def test_blocks_index_that_declares_behavior(tool_use, run_hook, tmp_path, content):
    # Arrange
    target = tmp_path / "src/index.ts"
    payload = tool_use("Write", {"file_path": str(target), "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "without a companion test")


def test_blocks_malformed_json():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "tdd-gate.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not json at all",
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    # Assert
    assert proc.returncode == 2


def test_allows_source_in_session_scratchpad(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "session-abc" / "scratchpad" / "build_review.py"
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_source_written_directly_to_shared_tmp(tool_use, run_hook):
    # Arrange
    target = Path("/tmp") / "retro-probe-measure-drift.py"
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_still_blocks_source_under_the_per_user_tmpdir(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "src" / "services" / "user.py"
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "without a companion test")


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
    assert_blocked(result)


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
