from __future__ import annotations
from pathlib import Path
import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _tdd_gate_helpers import HOOK


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
