"""Tests for `scripts/bench_mutation_blocker.py`.

Covers `_percentile`, payload construction, fixture gathering, single-run
benchmarking, aggregation, CLI option handling, and budget enforcement.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import bench_mutation_blocker as bench  # noqa: E402


# --------------------------------------------------------------------------- #
# _percentile
# --------------------------------------------------------------------------- #


def test_percentile_empty_returns_zero() -> None:
    # Arrange
    values: list[float] = []

    # Act
    result = bench._percentile(values, 50.0)

    # Assert
    assert result == 0.0


def test_percentile_negative_returns_min() -> None:
    # Arrange
    values = [10.0, 20.0, 30.0]

    # Act
    result = bench._percentile(values, -5.0)

    # Assert
    assert result == 10.0


def test_percentile_over_hundred_returns_max() -> None:
    # Arrange
    values = [10.0, 20.0, 30.0]

    # Act
    result = bench._percentile(values, 150.0)

    # Assert
    assert result == 30.0


def test_percentile_at_zero_returns_min() -> None:
    # Arrange
    values = [5.0, 7.0, 9.0]

    # Act
    result = bench._percentile(values, 0.0)

    # Assert
    assert result == 5.0


def test_percentile_at_hundred_returns_max() -> None:
    # Arrange
    values = [5.0, 7.0, 9.0]

    # Act
    result = bench._percentile(values, 100.0)

    # Assert
    assert result == 9.0


def test_percentile_p50_interpolates_between_ranks() -> None:
    # Arrange
    values = [10.0, 20.0, 30.0, 40.0]

    # Act
    result = bench._percentile(values, 50.0)

    # Assert
    assert result == pytest.approx(25.0)


def test_percentile_p95_picks_correct_value() -> None:
    # Arrange
    values = [float(i) for i in range(1, 101)]

    # Act
    result = bench._percentile(values, 95.0)

    # Assert
    assert result == pytest.approx(95.05)


# --------------------------------------------------------------------------- #
# _build_payload
# --------------------------------------------------------------------------- #


def test_build_payload_wraps_fixture_as_write(tmp_path: Path) -> None:
    # Arrange
    fixture = tmp_path / "fixture.ts"
    fixture.write_text("const x = 1;\n", encoding="utf-8")

    # Act
    payload = bench._build_payload(fixture)

    # Assert
    parsed = json.loads(payload)
    assert parsed["tool_name"] == "Write"
    assert parsed["tool_input"]["file_path"] == str(fixture)
    assert parsed["tool_input"]["content"] == "const x = 1;\n"


# --------------------------------------------------------------------------- #
# _run_one
# --------------------------------------------------------------------------- #


def test_run_one_returns_duration_for_zero_exit(tmp_path: Path) -> None:
    # Arrange
    fixture = tmp_path / "demo.ts"
    fixture.write_text("ok", encoding="utf-8")
    payload = bench._build_payload(fixture)
    fake_proc = MagicMock(returncode=0, stderr="")

    # Act
    with patch("bench_mutation_blocker.subprocess.run", return_value=fake_proc):
        duration = bench._run_one(fixture, payload)

    # Assert
    assert duration > 0.0


def test_run_one_accepts_block_exit_code(tmp_path: Path) -> None:
    # Arrange
    fixture = tmp_path / "demo.ts"
    fixture.write_text("ok", encoding="utf-8")
    payload = bench._build_payload(fixture)
    fake_proc = MagicMock(returncode=2, stderr="")

    # Act
    with patch("bench_mutation_blocker.subprocess.run", return_value=fake_proc):
        duration = bench._run_one(fixture, payload)

    # Assert
    assert duration > 0.0


def test_run_one_raises_on_unexpected_exit(tmp_path: Path) -> None:
    # Arrange
    fixture = tmp_path / "demo.ts"
    fixture.write_text("ok", encoding="utf-8")
    payload = bench._build_payload(fixture)
    fake_proc = MagicMock(returncode=42, stderr="boom")

    # Act / Assert
    with patch("bench_mutation_blocker.subprocess.run", return_value=fake_proc):
        with pytest.raises(RuntimeError, match="unexpected hook exit"):
            bench._run_one(fixture, payload)


# --------------------------------------------------------------------------- #
# _bench_fixture
# --------------------------------------------------------------------------- #


def test_bench_fixture_aggregates_iters(tmp_path: Path, monkeypatch) -> None:
    # Arrange
    fixture = tmp_path / "demo.ts"
    fixture.write_text("ok", encoding="utf-8")
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    monkeypatch.setattr(bench, "_run_one", lambda _f, _p: 5.0)

    # Act
    result = bench._bench_fixture(fixture, iters=4)

    # Assert
    assert result["iters"] == 4
    assert result["p50"] == pytest.approx(5.0)
    assert result["p95"] == pytest.approx(5.0)
    assert result["p99"] == pytest.approx(5.0)
    assert result["mean"] == pytest.approx(5.0)
    assert result["min"] == pytest.approx(5.0)
    assert result["max"] == pytest.approx(5.0)


# --------------------------------------------------------------------------- #
# _gather_fixtures
# --------------------------------------------------------------------------- #


def test_gather_fixtures_returns_empty_when_corpus_missing(
    monkeypatch, tmp_path: Path
) -> None:
    # Arrange
    monkeypatch.setattr(bench, "CORPUS", tmp_path / "missing")

    # Act
    fixtures = bench._gather_fixtures()

    # Assert
    assert fixtures == []


def test_gather_fixtures_returns_sorted_ts_files(monkeypatch, tmp_path: Path) -> None:
    # Arrange
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.ts").write_text("a", encoding="utf-8")
    sub = corpus / "sub"
    sub.mkdir()
    (sub / "b.ts").write_text("b", encoding="utf-8")
    (corpus / "skip.txt").write_text("ignore", encoding="utf-8")
    monkeypatch.setattr(bench, "CORPUS", corpus)

    # Act
    fixtures = bench._gather_fixtures()

    # Assert
    names = [p.name for p in fixtures]
    assert names == ["a.ts", "b.ts"]


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def test_main_returns_one_when_no_fixtures(monkeypatch, capsys, tmp_path: Path) -> None:
    # Arrange
    monkeypatch.setattr(bench, "CORPUS", tmp_path / "missing")
    monkeypatch.setattr(sys, "argv", ["bench"])

    # Act
    rc = bench.main()
    captured = capsys.readouterr()

    # Assert
    assert rc == 1
    assert "No fixtures" in captured.err


def test_main_within_budget_returns_zero(monkeypatch, capsys, tmp_path: Path) -> None:
    # Arrange
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.ts").write_text("ok", encoding="utf-8")
    monkeypatch.setattr(bench, "CORPUS", corpus)
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    monkeypatch.setattr(bench, "_run_one", lambda _f, _p: 1.0)
    monkeypatch.setattr(sys, "argv", ["bench", "--iters", "2"])

    # Act
    rc = bench.main()
    captured = capsys.readouterr()

    # Assert
    assert rc == 0
    parsed = json.loads(captured.out)
    assert parsed["iters_per_fixture"] == 2
    assert parsed["aggregate"]["p95_ms"] == pytest.approx(1.0)


def test_main_writes_output_file(monkeypatch, capsys, tmp_path: Path) -> None:
    # Arrange
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.ts").write_text("ok", encoding="utf-8")
    monkeypatch.setattr(bench, "CORPUS", corpus)
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    monkeypatch.setattr(bench, "_run_one", lambda _f, _p: 1.0)
    out_file = tmp_path / "report.json"
    monkeypatch.setattr(
        sys, "argv", ["bench", "--iters", "1", "--output", str(out_file)]
    )

    # Act
    rc = bench.main()

    # Assert
    assert rc == 0
    assert out_file.exists()
    parsed = json.loads(out_file.read_text(encoding="utf-8"))
    assert "fixtures" in parsed


def test_main_returns_two_when_budget_exceeded(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    # Arrange
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.ts").write_text("ok", encoding="utf-8")
    monkeypatch.setattr(bench, "CORPUS", corpus)
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    monkeypatch.setattr(bench, "_run_one", lambda _f, _p: 1000.0)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bench",
            "--iters",
            "2",
            "--budget-p95",
            "1.0",
            "--budget-p99",
            "1.0",
            "--budget-mean",
            "1.0",
        ],
    )

    # Act
    rc = bench.main()
    captured = capsys.readouterr()

    # Assert
    assert rc == 2
    assert "Perf budget violation" in captured.err


def test_main_module_entry_runs_as_subprocess(tmp_path: Path) -> None:
    # Arrange
    script = SCRIPTS_DIR / "bench_mutation_blocker.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(script), "--iters", "1"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    # Assert
    assert proc.returncode in (0, 1, 2)
