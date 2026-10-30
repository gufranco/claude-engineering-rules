from __future__ import annotations

from pathlib import Path

TEST_DIR_PARTS = frozenset(
    {
        "tests",
        "test",
        "__tests__",
        "spec",
        "specs",
        "e2e",
        "integration-tests",
    }
)

TEST_NAME_MARKERS = (
    ".test.",
    ".spec.",
    ".int.",
    ".e2e.",
    "_test.",
    "_spec.",
    "Test.",
    "Spec.",
)


def is_test_file(path: Path) -> bool:
    if set(path.parts) & TEST_DIR_PARTS:
        return True
    return any(marker in path.name for marker in TEST_NAME_MARKERS)
