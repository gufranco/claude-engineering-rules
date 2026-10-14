from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.analyzer_batch import AnalyzerBatch  # noqa: E402


def test_pending_lists_each_existing_file_once_in_order(tmp_path):
    # Arrange
    first = tmp_path / "a.c"
    second = tmp_path / "b.go"
    first.write_text("x", encoding="utf-8")
    second.write_text("y", encoding="utf-8")
    batch = AnalyzerBatch(tmp_path / "cache", "session-1")
    batch.record(first)
    batch.record(second)
    batch.record(first)
    batch.record(tmp_path / "gone.c")

    # Act
    pending = batch.pending()

    # Assert
    assert pending == (first, second)


def test_clear_removes_the_record(tmp_path):
    # Arrange
    source = tmp_path / "a.c"
    source.write_text("x", encoding="utf-8")
    batch = AnalyzerBatch(tmp_path / "cache", "session-1")
    batch.record(source)

    # Act
    batch.clear()

    # Assert
    assert batch.pending() == ()


def test_sessions_do_not_share_records(tmp_path):
    # Arrange
    source = tmp_path / "a.c"
    source.write_text("x", encoding="utf-8")
    AnalyzerBatch(tmp_path / "cache", "one").record(source)

    # Act
    other = AnalyzerBatch(tmp_path / "cache", "two").pending()

    # Assert
    assert other == ()


def test_last_report_round_trips(tmp_path):
    # Arrange
    batch = AnalyzerBatch(tmp_path / "cache", "../odd id")
    batch.remember("abc123")

    # Act
    remembered = batch.remembered()

    # Assert
    assert (remembered, sorted(p.name for p in (tmp_path / "cache").iterdir())) == (
        "abc123",
        ["analyzer-batch-oddid.last"],
    )


def test_replace_keeps_only_the_given_files(tmp_path):
    # Arrange
    first = tmp_path / "a.c"
    second = tmp_path / "b.c"
    first.write_text("x", encoding="utf-8")
    second.write_text("y", encoding="utf-8")
    batch = AnalyzerBatch(tmp_path / "cache", "s")
    batch.record(first)
    batch.record(second)
    batch.remember("digest")

    # Act
    batch.replace((second,))

    # Assert
    assert (batch.pending(), batch.remembered()) == ((second,), "")


def test_replace_with_nothing_clears(tmp_path):
    # Arrange
    source = tmp_path / "a.c"
    source.write_text("x", encoding="utf-8")
    batch = AnalyzerBatch(tmp_path / "cache", "s")
    batch.record(source)

    # Act
    batch.replace(())

    # Assert
    assert batch.pending() == ()
