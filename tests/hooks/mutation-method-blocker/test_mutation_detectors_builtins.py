from __future__ import annotations

import sys
from pathlib import Path

from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_detectors_builtins import (  # noqa: E402
    detect_async_iterator_return_throw,
    detect_delete_operator,
    detect_global_assignment,
    detect_object_assign_target_mutation,
    detect_object_define_setprototype,
    detect_reflect_mutations,
)


def _source(faker: Faker) -> str:
    return f"/repo/src/{faker.word()}.ts"


def test_object_assign_flags_a_named_target(faker: Faker) -> None:
    # Arrange
    text = "Object.assign(target, patch);\nObject.assign({}, target, patch);\n"

    # Act
    hits = detect_object_assign_target_mutation(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["first_arg"]) for h in hits] == [(1, "target")]


def test_object_define_and_set_prototype_are_each_flagged(faker: Faker) -> None:
    # Arrange
    text = (
        "Object.defineProperty(o, 'a', d);\n"
        "Object.defineProperties(o, ds);\n"
        "Object.setPrototypeOf(o, p);\n"
    )

    # Act
    hits = detect_object_define_setprototype(text, "ts", _source(faker))

    # Assert
    assert [h.detector for h in hits] == [
        "object.defineProperty",
        "object.defineProperties",
        "object.setPrototypeOf",
    ]


def test_reflect_mutations_keep_the_per_line_detector_order(faker: Faker) -> None:
    # Arrange
    text = "Reflect.setPrototypeOf(o, p); Reflect.set(o, k, v); Reflect.deleteProperty(o, k);\n"

    # Act
    hits = detect_reflect_mutations(text, "ts", _source(faker))

    # Assert
    assert [h.detector for h in hits] == [
        "reflect.set",
        "reflect.deleteProperty",
        "reflect.setPrototypeOf",
    ]


def test_delete_operator_reports_the_target(faker: Faker) -> None:
    # Arrange
    text = "delete cache[key];\n"

    # Act
    hits = detect_delete_operator(text, "ts", _source(faker))

    # Assert
    assert [(h.detector, h.metadata["target"]) for h in hits] == [
        ("delete-operator", "cache[key]")
    ]


def test_global_assignment_flags_process_env_writes(faker: Faker) -> None:
    # Arrange
    text = "process.env.MODE = 'x';\nif (process.env.MODE == 'x') {}\n"

    # Act
    hits = detect_global_assignment(text, "ts", _source(faker))

    # Assert
    assert [h.line for h in hits] == [1]


def test_async_iterator_return_is_flagged_under_the_stage_three_filter(
    faker: Faker, monkeypatch
) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_TC39_STAGE_FILTER", "3")
    text = "const it: AsyncIterator<number> = source();\nawait it.return();\n"

    # Act
    hits = detect_async_iterator_return_throw(text, "ts", _source(faker))

    # Assert
    assert [(h.detector, h.metadata["method"]) for h in hits] == [
        ("async-iterator.return-throw", "return")
    ]


def test_async_iterator_is_skipped_under_the_default_stage_four_filter(
    faker: Faker, monkeypatch
) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_TC39_STAGE_FILTER", "4")
    text = "const it: AsyncIterator<number> = source();\nawait it.throw(e);\n"

    # Act
    hits = detect_async_iterator_return_throw(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_async_iterator_mention_without_a_binding_is_clean(
    faker: Faker, monkeypatch
) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_TC39_STAGE_FILTER", "3")
    text = "type T = AsyncIterator<number>;\nit.return();\n"

    # Act
    hits = detect_async_iterator_return_throw(text, "ts", _source(faker))

    # Assert
    assert hits == []
