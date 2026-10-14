from __future__ import annotations

import sys
from pathlib import Path

from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_detectors_runtime import (  # noqa: E402
    detect_date_setters,
    detect_finalization_registry,
    detect_for_await_push_pattern,
    detect_object_groupby_push,
    detect_proxy_mutating_traps,
    detect_weakref_then_mutate,
)


def _source(faker: Faker) -> str:
    return f"/repo/src/{faker.word()}.ts"


def test_date_setters_flag_the_constructor_chain_before_the_setter(
    faker: Faker,
) -> None:
    # Arrange
    text = "const next = new Date(startDate.setMonth(2));\n"

    # Act
    hits = detect_date_setters(text, "ts", _source(faker))

    # Assert
    assert [h.detector for h in hits] == ["date.constructor-chain", "date.setMonth"]


def test_date_setters_mention_temporal_when_the_file_uses_it(faker: Faker) -> None:
    # Arrange
    text = "const n = Temporal.Now.instant();\nstartDate.setHours(1);\n"

    # Act
    hits = detect_date_setters(text, "ts", _source(faker))

    # Assert
    assert [h.metadata["temporal_in_scope"] for h in hits] == ["1"]
    assert "Temporal" in hits[0].fix_hint


def test_date_setters_need_a_date_receiver_hint(faker: Faker) -> None:
    # Arrange
    text = "thing.setHours(1);\n"

    # Act
    hits = detect_date_setters(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_proxy_traps_flag_only_inside_the_handler(faker: Faker) -> None:
    # Arrange
    text = (
        "const p = new Proxy(target, {\n"
        "  set(t, k, v) { return true; },\n"
        "});\n"
        "set(1);\n"
    )

    # Act
    hits = detect_proxy_mutating_traps(text, "ts", _source(faker))

    # Assert
    assert [(h.detector, h.line) for h in hits] == [("proxy.trap.set", 2)]


def test_weakref_deref_flags_only_mutating_methods(faker: Faker) -> None:
    # Arrange
    text = (
        "const ref = new WeakRef(list);\nref.deref()?.push(1);\nref.deref().map(f);\n"
    )

    # Act
    hits = detect_weakref_then_mutate(text, "ts", _source(faker))

    # Assert
    assert [h.detector for h in hits] == ["weakref.deref-mutate.push"]


def test_finalization_registry_construction_is_info_level(faker: Faker) -> None:
    # Arrange
    text = "const reg = new FinalizationRegistry(cleanup);\n"

    # Act
    hits = detect_finalization_registry(text, "ts", _source(faker))

    # Assert
    assert [(h.detector, h.metadata["severity"]) for h in hits] == [
        ("finalization-registry.construct", "info")
    ]


def test_for_await_push_flags_pushes_inside_the_loop_body_only(faker: Faker) -> None:
    # Arrange
    text = "for await (const row of rows) {\n  out.push(row);\n}\nother.push(1);\n"

    # Act
    hits = detect_for_await_push_pattern(text, "ts", _source(faker))

    # Assert
    assert [(h.line, h.metadata["owner"]) for h in hits] == [(2, "out")]


def test_for_await_push_ignores_text_without_a_push(faker: Faker) -> None:
    # Arrange
    text = "for await (const row of rows) {\n  log(row);\n}\n"

    # Act
    hits = detect_for_await_push_pattern(text, "ts", _source(faker))

    # Assert
    assert hits == []


def test_object_groupby_bucket_push_is_flagged(faker: Faker) -> None:
    # Arrange
    text = "const g = Object.groupBy(items, key);\ng[k].push(x);\n"

    # Act
    hits = detect_object_groupby_push(text, "ts", _source(faker))

    # Assert
    assert [(h.detector, h.line) for h in hits] == [("object.group-by-bucket-push", 2)]


def test_object_groupby_without_bucket_push_is_clean(faker: Faker) -> None:
    # Arrange
    text = "const g = Object.groupBy(items, key);\n"

    # Act
    hits = detect_object_groupby_push(text, "ts", _source(faker))

    # Assert
    assert hits == []
