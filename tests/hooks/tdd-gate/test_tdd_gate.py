"""Coverage for the tdd-gate hook.

Source rule: rules/testing.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

HOOK = "tdd-gate"


# ---------------------------------------------------------------------------
# Block: production source created without companion test
# ---------------------------------------------------------------------------


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
    tool_use, assert_blocks, tmp_path, rel_path
):
    # Arrange
    target = tmp_path / rel_path
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1\n"})

    # Act / Assert
    assert_blocks(HOOK, payload, "without a companion test")


def test_blocks_typescript_service(tool_use, assert_blocks, tmp_path):
    # Arrange
    target = tmp_path / "src/api/orders.service.ts"
    payload = tool_use("Write", {"file_path": str(target), "content": "export {}"})

    # Act / Assert
    assert_blocks(HOOK, payload, "BLOCKED")


# ---------------------------------------------------------------------------
# Allow: test files themselves
# ---------------------------------------------------------------------------


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
def test_allows_test_file_creation(tool_use, assert_allows, tmp_path, rel_path):
    # Arrange
    target = tmp_path / rel_path
    payload = tool_use(
        "Write", {"file_path": str(target), "content": "test('x', () => {})"}
    )

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: non-source file types
# ---------------------------------------------------------------------------


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
def test_allows_non_source_files(tool_use, assert_allows, tmp_path, rel_path):
    # Arrange
    target = tmp_path / rel_path
    payload = tool_use("Write", {"file_path": str(target), "content": "x"})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: excluded directories
# ---------------------------------------------------------------------------


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
def test_allows_excluded_directories(tool_use, assert_allows, tmp_path, rel_path):
    # Arrange
    target = tmp_path / rel_path
    payload = tool_use("Write", {"file_path": str(target), "content": "x"})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: excluded name markers (generated, type defs, minified)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rel_path",
    [
        "src/types/api.d.ts",
        "public/app.min.js",
        "static/vendor.bundle.js",
        "src/proto/schema.generated.ts",
    ],
)
def test_allows_generated_and_minified_files(
    tool_use, assert_allows, tmp_path, rel_path
):
    # Arrange
    target = tmp_path / rel_path
    payload = tool_use("Write", {"file_path": str(target), "content": "x"})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: companion test exists
# ---------------------------------------------------------------------------


def test_allows_when_sibling_test_exists(tool_use, assert_allows, tmp_path):
    # Arrange
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "calculator.test.ts").write_text("test('x', () => {})")
    target = src_dir / "calculator.ts"
    payload = tool_use("Write", {"file_path": str(target), "content": "export {}"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_when_spec_sibling_exists(tool_use, assert_allows, tmp_path):
    # Arrange
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "calculator.spec.ts").write_text("test('x', () => {})")
    target = src_dir / "calculator.ts"
    payload = tool_use("Write", {"file_path": str(target), "content": "export {}"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_when_go_test_sibling_exists(tool_use, assert_allows, tmp_path):
    # Arrange
    pkg = tmp_path / "internal" / "api"
    pkg.mkdir(parents=True)
    (pkg / "handler_test.go").write_text("package api\n")
    target = pkg / "handler.go"
    payload = tool_use("Write", {"file_path": str(target), "content": "package api"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_when_tests_dir_mirror_exists(tool_use, assert_allows, tmp_path):
    # Arrange
    pkg = tmp_path / "src" / "services"
    pkg.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_user.py").write_text("def test_x(): pass\n")
    target = pkg / "user.py"
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_when_nested_tests_subfolder_exists(tool_use, assert_allows, tmp_path):
    # Arrange
    pkg = tmp_path / "src"
    pkg.mkdir()
    subtests = pkg / "__tests__"
    subtests.mkdir()
    (subtests / "Button.test.tsx").write_text("test('x', () => {})")
    target = pkg / "Button.tsx"
    payload = tool_use("Write", {"file_path": str(target), "content": "export {}"})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: editing an existing file (not creating new)
# ---------------------------------------------------------------------------


def test_allows_edit_of_existing_file(tool_use, assert_allows, tmp_path):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_write_overwriting_existing_file(tool_use, assert_allows, tmp_path):
    # Arrange
    target = tmp_path / "src" / "user.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n")
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 2\n"})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: irrelevant tools
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool_name", ["Bash", "Read", "Grep", "Glob", "WebFetch"])
def test_allows_unrelated_tools(tool_use, assert_allows, tool_name):
    # Arrange
    payload = tool_use(tool_name, {"command": "echo hi"})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Bypass env var
# ---------------------------------------------------------------------------


def test_bypass_env_var_disables_check(tool_use, assert_allows, tmp_path):
    # Arrange
    target = tmp_path / "src/user.py"
    payload = tool_use("Write", {"file_path": str(target), "content": "x = 1"})

    # Act / Assert
    assert_allows(HOOK, payload, env={"TDD_GATE_DISABLE": "1"})


# ---------------------------------------------------------------------------
# Robustness: malformed payload
# ---------------------------------------------------------------------------


def test_handles_missing_tool_input(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Write")

    # Act / Assert
    assert_allows(HOOK, payload)


def test_handles_empty_file_path(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Write", {"file_path": "", "content": "x"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_handles_malformed_json(run_hook, tmp_path):
    # Arrange
    import subprocess
    import sys

    hook_path = Path.home() / ".claude" / "hooks" / "tdd-gate.py"

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
    assert proc.returncode == 0
