from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.test_paths import is_test_file  # noqa: E402


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("tests/orders.py", True),
        ("src/__tests__/orders.ts", True),
        ("src/orders.test.ts", True),
        ("internal/orders_test.go", True),
        ("pack.retail.test.py", True),
        ("src/OrdersSpec.kt", True),
        ("src/orders.ts", False),
        ("docs/testing.md", False),
    ],
)
def test_a_path_is_a_test_by_its_directory_or_its_name(relative, expected):
    # Arrange
    path = Path(relative)

    # Act
    found = is_test_file(path)

    # Assert
    assert found is expected
