from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.source_scope import in_scope  # noqa: E402

IN_SCOPE = ("/r/src/a.go", "/r/lib/card.dart", "/r/app/core.py", "/r/src/a.c")
OUT_OF_SCOPE = (
    "/r/cmd/main_test.go",
    "/r/src/test/java/ATest.java",
    "/r/spec/user_spec.rb",
    "/r/lib/card.g.dart",
    "/r/vendor/lib/a.go",
    "/r/app/test_core.py",
    "/r/app/core_test.py",
    "/r/app/core.test.py",
    "/r/app/conftest.py",
    "/r/tests/helpers.py",
    "/r/node_modules/x/a.js",
    "/r/build/gen.c",
)


@pytest.mark.parametrize("path", IN_SCOPE)
def test_production_sources_are_in_scope(path):
    # Arrange
    candidate = path

    # Act
    verdict = in_scope(candidate)

    # Assert
    assert verdict is True


@pytest.mark.parametrize("path", OUT_OF_SCOPE)
def test_tests_generated_and_vendored_files_are_out_of_scope(path):
    # Arrange
    candidate = path

    # Act
    verdict = in_scope(candidate)

    # Assert
    assert verdict is False
