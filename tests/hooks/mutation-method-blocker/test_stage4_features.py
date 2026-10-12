from __future__ import annotations

import datetime as _dt
import importlib
import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))


@pytest.fixture(autouse=True)
def _restore_tc39_stage_filter():
    original = os.environ.get("MUTATION_METHOD_TC39_STAGE_FILTER")
    yield
    if original is None:
        os.environ.pop("MUTATION_METHOD_TC39_STAGE_FILTER", None)
    else:
        os.environ["MUTATION_METHOD_TC39_STAGE_FILTER"] = original
    if "_lib.mutation_fix_lookup" in sys.modules:
        importlib.reload(sys.modules["_lib.mutation_fix_lookup"])


def _load_fix_lookup(stage: str | None):
    if stage is None:
        os.environ.pop("MUTATION_METHOD_TC39_STAGE_FILTER", None)
    else:
        os.environ["MUTATION_METHOD_TC39_STAGE_FILTER"] = stage
    from _lib import mutation_fix_lookup as mfl

    return importlib.reload(mfl)


def _load_maintenance():
    spec = importlib.util.spec_from_file_location(
        "maintenance", REPO_ROOT / ".github" / "scripts" / "maintenance.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("maintenance.py could not be loaded")
    maintenance = importlib.util.module_from_spec(spec)
    sys.modules["maintenance"] = maintenance
    spec.loader.exec_module(maintenance)
    return maintenance


from _lib.mutation_detectors_methods import (  # noqa: E402
    detect_array_pop_shift_unshift_splice_reverse_fill_copywithin,
    detect_array_push,
    detect_array_sort,
    detect_for_await_push_pattern,
    detect_map_set_collection_mutations,
    detect_uint8_base64_setter,
)

CORPUS = REPO_ROOT / "tests" / "corpus" / "mutation-method-blocker" / "stage4_features"


def test_for_await_push_flagged_with_const_binding() -> None:
    # Arrange
    text = (
        "async function fill(items) {\n"
        "  const out = [];\n"
        "  for await (const x of items) {\n"
        "    out.push(x);\n"
        "  }\n"
        "  return out;\n"
        "}\n"
    )

    # Act
    matches = detect_for_await_push_pattern(text, "ts", "src/fill.ts")

    # Assert
    assert any(m.detector == "async-iterable.for-await-push" for m in matches)
    assert any(m.metadata.get("owner") == "out" for m in matches)


def test_for_await_push_flagged_with_let_binding() -> None:
    # Arrange
    text = (
        "async function fill(items) {\n"
        "  let acc = [];\n"
        "  for await (let item of items) {\n"
        "    acc.push(item);\n"
        "  }\n"
        "  return acc;\n"
        "}\n"
    )

    # Act
    matches = detect_for_await_push_pattern(text, "ts", "src/fill.ts")

    # Assert
    assert any(m.metadata.get("owner") == "acc" for m in matches)


def test_for_await_without_push_quiet() -> None:
    # Arrange
    text = (
        "async function consume(items) {\n"
        "  for await (const x of items) {\n"
        "    console.log(x);\n"
        "  }\n"
        "}\n"
    )

    # Act
    matches = detect_for_await_push_pattern(text, "ts", "src/consume.ts")

    # Assert
    assert matches == []


def test_push_without_for_await_not_owned_by_phase35_detector() -> None:
    # Arrange
    text = "const arr = [];\nfor (let i = 0; i < 5; i++) {\n  arr.push(i);\n}\n"

    # Act
    matches = detect_for_await_push_pattern(text, "ts", "src/loop.ts")

    # Assert
    assert matches == []


def test_uint8_set_from_base64_flagged() -> None:
    # Arrange
    text = "function decode(buf, payload) { buf.setFromBase64(payload); }\n"

    # Act
    matches = detect_uint8_base64_setter(text, "ts", "src/codec.ts")

    # Assert
    assert any(m.detector == "uint8.set-from-base64" for m in matches)
    assert any(m.metadata.get("method") == "setFromBase64" for m in matches)


def test_uint8_set_from_hex_flagged() -> None:
    # Arrange
    text = "function decode(buf, payload) { buf.setFromHex(payload); }\n"

    # Act
    matches = detect_uint8_base64_setter(text, "ts", "src/codec.ts")

    # Assert
    assert any(m.detector == "uint8.set-from-hex" for m in matches)


def test_uint8_static_fromBase64_not_flagged() -> None:
    # Arrange
    text = "const buf = Uint8Array.fromBase64(payload);\n"

    # Act
    matches = detect_uint8_base64_setter(text, "ts", "src/codec.ts")

    # Assert
    assert matches == []


def test_promise_try_no_false_flag() -> None:
    # Arrange
    text = "const p = Promise.try(() => doWork(value));\n"

    # Act
    hits = (
        detect_array_push(text, "ts", "src/a.ts")
        + detect_array_sort(text, "ts", "src/a.ts")
        + detect_map_set_collection_mutations(text, "ts", "src/a.ts")
        + detect_array_pop_shift_unshift_splice_reverse_fill_copywithin(
            text, "ts", "src/a.ts"
        )
    )

    # Assert
    assert hits == []


def test_error_iserror_no_false_flag() -> None:
    # Arrange
    text = "if (Error.isError(value)) { handle(value); }\n"

    # Act
    hits = (
        detect_array_push(text, "ts", "src/a.ts")
        + detect_array_sort(text, "ts", "src/a.ts")
        + detect_map_set_collection_mutations(text, "ts", "src/a.ts")
    )

    # Assert
    assert hits == []


def test_regexp_escape_no_false_flag() -> None:
    # Arrange
    text = "const safe = new RegExp(RegExp.escape(input));\n"

    # Act
    hits = (
        detect_array_push(text, "ts", "src/a.ts")
        + detect_array_sort(text, "ts", "src/a.ts")
        + detect_map_set_collection_mutations(text, "ts", "src/a.ts")
    )

    # Assert
    assert hits == []


def test_promise_withresolvers_no_false_flag() -> None:
    # Arrange
    text = "const { promise, resolve } = Promise.withResolvers();\n"

    # Act
    hits = detect_map_set_collection_mutations(text, "ts", "src/a.ts")

    # Assert
    assert hits == []


def test_array_fromasync_no_false_flag() -> None:
    # Arrange
    text = "const xs = await Array.fromAsync(iter, (x) => x * 2);\n"

    # Act
    hits = detect_array_push(text, "ts", "src/a.ts")

    # Assert
    assert hits == []


def test_atomics_pause_no_false_flag() -> None:
    # Arrange
    text = "while (true) { Atomics.pause(); break; }\n"

    # Act
    hits = detect_array_push(
        text, "ts", "src/a.ts"
    ) + detect_map_set_collection_mutations(text, "ts", "src/a.ts")

    # Assert
    assert hits == []


def test_stage4_clean_corpus_has_no_for_await_push_hits() -> None:
    # Arrange
    path = CORPUS / "clean.ts"
    text = path.read_text()

    # Act
    matches = detect_for_await_push_pattern(text, "ts", str(path))

    # Assert
    assert matches == []


def test_stage4_clean_corpus_has_no_uint8_setter_hits() -> None:
    # Arrange
    path = CORPUS / "clean.ts"
    text = path.read_text()

    # Act
    matches = detect_uint8_base64_setter(text, "ts", str(path))

    # Assert
    assert matches == []


def test_stage4_dirty_corpus_flags_for_await_push() -> None:
    # Arrange
    path = CORPUS / "dirty.ts"
    text = path.read_text()

    # Act
    for_await = detect_for_await_push_pattern(text, "ts", str(path))

    # Assert
    assert len(for_await) >= 2
    assert {m.metadata.get("owner") for m in for_await} >= {"out", "result"}


def test_stage4_dirty_corpus_flags_uint8_setters() -> None:
    # Arrange
    path = CORPUS / "dirty.ts"
    text = path.read_text()

    # Act
    base64 = detect_uint8_base64_setter(text, "ts", str(path))

    # Assert
    assert {m.metadata.get("method") for m in base64} == {"setFromBase64", "setFromHex"}


@pytest.mark.parametrize(
    ("rule_id", "suggested"),
    [
        ("async-iterator.helper-collect", False),
        ("async-iterable.for-await-push", True),
    ],
)
def test_tc39_stage_filter_default_4_suppresses_stage3(rule_id, suggested) -> None:
    # Arrange
    mfl = _load_fix_lookup(None)

    # Act
    suggestion = mfl.suggest_fix(rule_id)

    # Assert
    assert (suggestion is not None) is suggested


@pytest.mark.parametrize(
    ("rule_id", "suggested"),
    [
        ("async-iterator.helper-collect", True),
        ("iterator.range-replacement", False),
    ],
)
def test_tc39_stage_filter_3_includes_stage3(rule_id, suggested) -> None:
    # Arrange
    mfl = _load_fix_lookup("3")

    # Act
    suggestion = mfl.suggest_fix(rule_id)

    # Assert
    assert (suggestion is not None) is suggested


def test_tc39_stage_filter_2_prepends_volatility_marker() -> None:
    # Arrange
    mfl = _load_fix_lookup("2")

    # Act
    range_repl = mfl.suggest_fix("iterator.range-replacement")

    # Assert
    assert range_repl is not None
    assert "Stage 2 proposal" in range_repl


def test_tc39_stage_filter_invalid_value_falls_back_to_default() -> None:
    # Arrange
    mfl = _load_fix_lookup("notanumber")

    # Act
    helper_collect = mfl.suggest_fix("async-iterator.helper-collect")

    # Assert
    assert helper_collect is None


def test_tc39_stage_filter_clamps_above_4() -> None:
    # Arrange
    mfl = _load_fix_lookup("9")

    # Act
    stage = mfl.tc39_stage_filter()

    # Assert
    assert stage == 4


def test_maintenance_quarterly_message_mentions_finished_proposals() -> None:
    # Arrange
    maintenance = _load_maintenance()
    review_day = _dt.date(2026, 7, 6)

    # Act
    msg = maintenance._quarterly_message(review_day)

    # Assert
    assert "finished-proposals" in msg
    assert "Stage 3" in msg
    assert "Stage 4" in msg
