"""Phase 35 integration tests: AsyncIterator helpers, Stage 3/4 features.

Covers the two new Phase 35 detectors:

  - `detect_for_await_push_pattern` (MMB086, async-iterable.for-await-push)
  - `detect_uint8_base64_setter` (MMB088, uint8.set-from-base64 / set-from-hex)

Plus no-false-positive assertions for the recognized non-mutating Stage 4
primitives (Promise.try, Error.isError, RegExp.escape, Promise.withResolvers,
Array.fromAsync, Atomics.pause) and the corpus pair `stage4_features/clean.ts`
vs `stage4_features/dirty.ts`.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from mutation_detectors_methods import (  # noqa: E402
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


def test_stage4_clean_corpus_has_no_phase35_hits() -> None:
    # Arrange
    text = (CORPUS / "clean.ts").read_text()

    # Act
    matches = detect_for_await_push_pattern(text, "ts", str(CORPUS / "clean.ts"))
    matches += detect_uint8_base64_setter(text, "ts", str(CORPUS / "clean.ts"))

    # Assert
    assert matches == []


def test_stage4_dirty_corpus_flags_for_await_and_uint8() -> None:
    # Arrange
    text = (CORPUS / "dirty.ts").read_text()

    # Act
    for_await = detect_for_await_push_pattern(text, "ts", str(CORPUS / "dirty.ts"))
    base64 = detect_uint8_base64_setter(text, "ts", str(CORPUS / "dirty.ts"))

    # Assert
    assert len(for_await) >= 2
    assert {m.metadata.get("owner") for m in for_await} >= {"out", "result"}
    methods = {m.metadata.get("method") for m in base64}
    assert methods == {"setFromBase64", "setFromHex"}


def test_tc39_stage_filter_default_4_suppresses_stage3() -> None:
    # Arrange
    os.environ.pop("MUTATION_METHOD_TC39_STAGE_FILTER", None)
    import mutation_fix_lookup as mfl

    importlib.reload(mfl)

    # Act
    helper_collect = mfl.suggest_fix("async-iterator.helper-collect")
    for_await = mfl.suggest_fix("async-iterable.for-await-push")

    # Assert
    assert helper_collect is None
    assert for_await is not None


def test_tc39_stage_filter_3_includes_stage3() -> None:
    # Arrange
    os.environ["MUTATION_METHOD_TC39_STAGE_FILTER"] = "3"
    import mutation_fix_lookup as mfl

    importlib.reload(mfl)

    # Act
    helper_collect = mfl.suggest_fix("async-iterator.helper-collect")
    range_repl = mfl.suggest_fix("iterator.range-replacement")

    # Assert
    assert helper_collect is not None
    assert range_repl is None

    # Cleanup
    os.environ.pop("MUTATION_METHOD_TC39_STAGE_FILTER", None)
    importlib.reload(mfl)


def test_tc39_stage_filter_2_prepends_volatility_marker() -> None:
    # Arrange
    os.environ["MUTATION_METHOD_TC39_STAGE_FILTER"] = "2"
    import mutation_fix_lookup as mfl

    importlib.reload(mfl)

    # Act
    range_repl = mfl.suggest_fix("iterator.range-replacement")

    # Assert
    assert range_repl is not None
    assert "Stage 2 proposal" in range_repl

    # Cleanup
    os.environ.pop("MUTATION_METHOD_TC39_STAGE_FILTER", None)
    importlib.reload(mfl)


def test_tc39_stage_filter_invalid_value_falls_back_to_default() -> None:
    # Arrange
    os.environ["MUTATION_METHOD_TC39_STAGE_FILTER"] = "notanumber"
    import mutation_fix_lookup as mfl

    importlib.reload(mfl)

    # Act
    helper_collect = mfl.suggest_fix("async-iterator.helper-collect")

    # Assert
    assert helper_collect is None

    # Cleanup
    os.environ.pop("MUTATION_METHOD_TC39_STAGE_FILTER", None)
    importlib.reload(mfl)


def test_tc39_stage_filter_clamps_above_4() -> None:
    # Arrange
    os.environ["MUTATION_METHOD_TC39_STAGE_FILTER"] = "9"
    import mutation_fix_lookup as mfl

    importlib.reload(mfl)

    # Act
    stage = mfl.tc39_stage_filter()

    # Assert
    assert stage == 4

    # Cleanup
    os.environ.pop("MUTATION_METHOD_TC39_STAGE_FILTER", None)
    importlib.reload(mfl)


def test_maintenance_quarterly_message_mentions_finished_proposals() -> None:
    # Arrange
    import maintenance

    # Act
    import datetime as _dt

    msg = maintenance._quarterly_message(_dt.date(2026, 7, 6))

    # Assert
    assert "finished-proposals" in msg
    assert "Stage 3" in msg
    assert "Stage 4" in msg
