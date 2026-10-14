from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.python_mutation_detectors import find, is_python_source  # noqa: E402


def test_is_python_source_skips_test_and_stub_files():
    # Arrange
    paths = (
        "/repo/app/core.py",
        "/repo/app/core.pyi",
        "/repo/app/core.test.py",
        "/repo/app/core_test.py",
        "/repo/app/test_core.py",
        "/repo/app/conftest.py",
        "/repo/tests/helpers.py",
        "/repo/app/core.ts",
    )

    # Act
    verdicts = tuple(is_python_source(path) for path in paths)

    # Assert
    assert verdicts == (True, False, False, False, False, False, False, False)


def test_find_reports_line_numbers_of_each_hit():
    # Arrange
    text = "def merge(left: list[int], right: list[int]) -> None:\n    left.extend(right)\n    right.sort()\n"

    # Act
    hits = find(text)

    # Assert
    assert [hit.line for hit in hits] == [2, 3]


def test_find_falls_back_to_regex_for_broken_fragments():
    # Arrange
    text = "def helper(cache={}):\n    return cache\n  )"

    # Act
    hits = find(text)

    # Assert
    assert [hit.message for hit in hits] == [
        "mutable default argument. One instance is shared by every call"
    ]


def test_find_marks_mutable_dataclass_advisory():
    # Arrange
    text = "@dataclasses.dataclass(slots=True)\nclass Point:\n    x: int\n"

    # Act
    hits = find(text)

    # Assert
    assert [(hit.line, hit.blocking) for hit in hits] == [(1, False)]


def test_find_honors_a_suppression_comment():
    # Arrange
    text = "def stamp(image: bytearray) -> None:\n    image[0] = 1  # noqa: in-place buffer\n"

    # Act
    hits = find(text)

    # Assert
    assert hits == ()


def test_find_ignores_mutation_of_a_parameter_shadowed_by_a_copy():
    # Arrange
    text = "def add(meta: dict[str, int]) -> dict[str, int]:\n    meta = {**meta}\n    meta['n'] = 1\n    return meta\n"

    # Act
    hits = find(text)

    # Assert
    assert hits == ()


def test_find_treats_a_with_target_as_a_rebinding():
    # Arrange
    text = "def f(items: list[str]) -> None:\n    with open_items() as items:\n        items.append('x')\n"

    # Act
    hits = find(text)

    # Assert
    assert hits == ()


def test_find_skips_classvar_and_unrelated_decorators():
    # Arrange
    text = (
        "@functools.total_ordering\n"
        "class Rank:\n"
        "    ORDER: ClassVar[list[str]] = ['a']\n"
    )

    # Act
    hits = find(text)

    # Assert
    assert hits == ()


def test_find_ignores_in_place_plus_on_a_copied_parameter():
    # Arrange
    text = "def extend(items: list[str], more: list[str]) -> list[str]:\n    items = list(items)\n    items += more\n    return items\n"

    # Act
    hits = find(text)

    # Assert
    assert hits == ()


def test_find_skips_meta_classes_and_dunder_attributes():
    # Arrange
    text = (
        "class Order(models.Model):\n"
        "    __slots__ = []\n"
        "    class Meta:\n"
        "        ordering = ['-id']\n"
    )

    # Act
    hits = find(text)

    # Assert
    assert hits == ()
