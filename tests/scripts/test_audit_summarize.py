"""Tests for `scripts/audit_summarize.py`.

Spec: `specs/2026-05-09-claude-config-state-of-art/plan.md` 1.3.4.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import audit_summarize  # noqa: E402


# --------------------------------------------------------------------------- #
# parse_window
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("30s", 30),
        ("5m", 300),
        ("1h", 3600),
        ("24h", 86400),
        ("7d", 604800),
        (" 24h ", 86400),
    ],
)
def test_parse_window_supported_units(spec, expected):
    # Arrange/Act
    out = audit_summarize.parse_window(spec)

    # Assert
    assert out == expected


@pytest.mark.parametrize("spec", [None, ""])
def test_parse_window_none_or_empty_returns_none(spec):
    assert audit_summarize.parse_window(spec) is None


@pytest.mark.parametrize(
    "spec",
    ["24", "24x", "abc", "h24", "-3h", " ", "1.5h"],
)
def test_parse_window_invalid_raises(spec):
    with pytest.raises(ValueError):
        audit_summarize.parse_window(spec)


# --------------------------------------------------------------------------- #
# _percentile
# --------------------------------------------------------------------------- #


def test_percentile_empty_returns_zero():
    assert audit_summarize._percentile([], 0.5) == 0


def test_percentile_single_value_returns_value():
    assert audit_summarize._percentile([42], 0.99) == 42


def test_percentile_p50_on_evenly_spaced():
    assert audit_summarize._percentile(list(range(1, 11)), 0.50) == 6


def test_percentile_p95_on_evenly_spaced():
    # range 1..10 sorted; p95 lands between 9 and 10 with weight 0.55
    assert audit_summarize._percentile(list(range(1, 11)), 0.95) == 10


def test_percentile_p99_on_evenly_spaced():
    assert audit_summarize._percentile(list(range(1, 11)), 0.99) == 10


def test_percentile_handles_unsorted_pretransposed_caller():
    # Function expects sorted input; verify caller uses sorted() upstream.
    sorted_values = sorted([5, 1, 9, 3, 7])
    assert audit_summarize._percentile(sorted_values, 0.5) == 5


# --------------------------------------------------------------------------- #
# iter_records / file IO
# --------------------------------------------------------------------------- #


def _write_log(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n"
    )


def test_iter_records_reads_jsonl(tmp_path):
    # Arrange
    log = tmp_path / "hooks.log"
    _write_log(
        log,
        [
            {"ts": "2026-05-01T00:00:00Z", "hook": "a", "decision": "allow"},
            {"ts": "2026-05-01T00:00:01Z", "hook": "b", "decision": "block"},
        ],
    )

    # Act
    out = list(audit_summarize.iter_records([str(log)]))

    # Assert
    assert len(out) == 2
    assert out[0]["hook"] == "a"
    assert out[1]["hook"] == "b"


def test_iter_records_skips_blank_lines(tmp_path):
    # Arrange
    log = tmp_path / "hooks.log"
    log.write_text(
        '{"ts":"2026-05-01T00:00:00Z","hook":"a"}\n\n   \n'
        '{"ts":"2026-05-01T00:00:01Z","hook":"b"}\n'
    )

    # Act
    out = list(audit_summarize.iter_records([str(log)]))

    # Assert
    assert [r["hook"] for r in out] == ["a", "b"]


def test_iter_records_skips_invalid_json(tmp_path):
    # Arrange
    log = tmp_path / "hooks.log"
    log.write_text('{"hook":"a"}\nnot json\n{"hook":"b"}\n')

    # Act
    out = list(audit_summarize.iter_records([str(log)]))

    # Assert
    assert [r["hook"] for r in out] == ["a", "b"]


def test_iter_records_skips_top_level_lists(tmp_path):
    # Arrange
    log = tmp_path / "hooks.log"
    log.write_text('[1,2,3]\n{"hook":"x"}\n')

    # Act
    out = list(audit_summarize.iter_records([str(log)]))

    # Assert
    assert [r["hook"] for r in out] == ["x"]


def test_iter_records_skips_missing_files(tmp_path):
    # Arrange
    primary = tmp_path / "exists.log"
    backup = tmp_path / "missing.log"
    _write_log(primary, [{"hook": "p"}])

    # Act
    out = list(audit_summarize.iter_records([str(primary), str(backup)]))

    # Assert
    assert [r["hook"] for r in out] == ["p"]


def test_iter_records_handles_none_in_paths(tmp_path):
    # Arrange
    log = tmp_path / "hooks.log"
    _write_log(log, [{"hook": "a"}])

    # Act
    out = list(audit_summarize.iter_records([None, "", str(log)]))

    # Assert
    assert [r["hook"] for r in out] == ["a"]


def test_iter_records_filters_by_window(tmp_path):
    # Arrange
    now = time.time()
    recent_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 60))
    old_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 86400 * 30))
    log = tmp_path / "hooks.log"
    _write_log(
        log,
        [
            {"ts": recent_ts, "hook": "fresh"},
            {"ts": old_ts, "hook": "stale"},
        ],
    )

    # Act
    out = list(audit_summarize.iter_records([str(log)], since_epoch=now - 3600))

    # Assert
    assert [r["hook"] for r in out] == ["fresh"]


def test_iter_records_with_window_drops_record_without_ts(tmp_path):
    # Arrange
    log = tmp_path / "hooks.log"
    _write_log(log, [{"hook": "no-ts"}])

    # Act
    out = list(audit_summarize.iter_records([str(log)], since_epoch=time.time() - 60))

    # Assert: missing ts under filtering means the record is dropped
    assert out == []


def test_iter_records_without_window_keeps_record_without_ts(tmp_path):
    # Arrange
    log = tmp_path / "hooks.log"
    _write_log(log, [{"hook": "no-ts"}])

    # Act
    out = list(audit_summarize.iter_records([str(log)]))

    # Assert
    assert out == [{"hook": "no-ts"}]


def test_iter_records_handles_oserror_silently(monkeypatch, tmp_path):
    # Arrange: real path that raises on open
    import builtins

    log = tmp_path / "hooks.log"
    _write_log(log, [{"hook": "x"}])
    real_open = builtins.open

    def boom(path, *args, **kwargs):
        if str(path) == str(log):
            raise OSError("permission denied")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", boom)

    # Act/Assert
    out = list(audit_summarize.iter_records([str(log)]))
    assert out == []


# --------------------------------------------------------------------------- #
# summarize
# --------------------------------------------------------------------------- #


def test_summarize_empty_returns_zero_totals():
    # Arrange/Act
    summary = audit_summarize.summarize([])

    # Assert
    assert summary["total_records"] == 0
    assert summary["counts_by_hook"] == {}
    assert summary["counts_by_decision"] == {}
    assert summary["latency_by_hook"] == {}
    assert summary["top_reasons"] == []
    assert summary["top_detector_tags"] == []
    assert summary["top_defect_pattern_tags"] == []


def test_summarize_counts_by_hook_and_decision():
    # Arrange
    records = [
        {"hook": "h1", "decision": "block"},
        {"hook": "h1", "decision": "block"},
        {"hook": "h2", "decision": "allow"},
        {"hook_name": "h3", "decision_class": "modify"},
    ]

    # Act
    summary = audit_summarize.summarize(records)

    # Assert
    assert summary["total_records"] == 4
    assert summary["counts_by_hook"]["h1"] == 2
    assert summary["counts_by_hook"]["h2"] == 1
    assert summary["counts_by_hook"]["h3"] == 1
    assert summary["counts_by_decision"]["block"] == 2
    assert summary["counts_by_decision"]["allow"] == 1
    assert summary["counts_by_decision"]["modify"] == 1


def test_summarize_records_with_no_hook_become_unknown():
    # Arrange/Act
    summary = audit_summarize.summarize([{"decision": "allow"}, {"decision": "block"}])

    # Assert
    assert summary["counts_by_hook"]["unknown"] == 2


def test_summarize_records_with_no_decision_become_unknown():
    # Arrange/Act
    summary = audit_summarize.summarize([{"hook": "x"}])

    # Assert
    assert summary["counts_by_decision"]["unknown"] == 1


def test_summarize_latency_percentiles():
    # Arrange
    records = [
        {"hook": "h", "decision": "allow", "latency_ms": v} for v in range(1, 101)
    ]

    # Act
    summary = audit_summarize.summarize(records)
    stats = summary["latency_by_hook"]["h"]

    # Assert
    assert stats["n"] == 100
    assert stats["p50"] == 50
    assert stats["p95"] == 95
    assert stats["p99"] == 99


def test_summarize_skips_non_numeric_latency():
    # Arrange
    records = [
        {"hook": "h", "decision": "allow", "latency_ms": "fast"},
        {"hook": "h", "decision": "allow", "latency_ms": True},  # bool excluded
        {"hook": "h", "decision": "allow", "latency_ms": 12},
    ]

    # Act
    summary = audit_summarize.summarize(records)

    # Assert
    assert summary["latency_by_hook"]["h"]["n"] == 1
    assert summary["latency_by_hook"]["h"]["p50"] == 12


def test_summarize_false_positive_rate():
    # Arrange
    records = [
        {"hook": "h", "decision": "block", "suppressed": False},
        {"hook": "h", "decision": "block", "suppressed": True},
        {"hook": "h", "decision": "block", "suppressed": True},
        {"hook": "h", "decision": "block"},
    ]

    # Act
    summary = audit_summarize.summarize(records)

    # Assert
    fp = summary["false_positive_by_hook"]["h"]
    assert fp["suppressed_count"] == 2
    assert fp["sample_count"] == 4
    assert fp["suppression_rate"] == 0.5


def test_summarize_top_reasons():
    # Arrange
    records = [
        {"hook": "h1", "decision": "block", "reason": "r1"},
        {"hook": "h1", "decision": "block", "reason": "r1"},
        {"hook": "h2", "decision": "block", "reason": "r2"},
    ]

    # Act
    summary = audit_summarize.summarize(records, top=5)

    # Assert
    top = summary["top_reasons"]
    assert top[0] == {"reason": "r1", "hook": "h1", "count": 2}
    assert {"reason": "r2", "hook": "h2", "count": 1} in top


def test_summarize_top_reasons_respects_top_argument():
    # Arrange
    records = [{"hook": "h", "decision": "block", "reason": f"r{i}"} for i in range(50)]

    # Act
    summary = audit_summarize.summarize(records, top=3)

    # Assert
    assert len(summary["top_reasons"]) == 3


def test_summarize_top_detector_tags():
    # Arrange
    records = [
        {"hook": "h", "detector_tag": "d1"},
        {"hook": "h", "detector_tag": "d1"},
        {"hook": "h", "detector": "d2"},  # legacy key
    ]

    # Act
    summary = audit_summarize.summarize(records)

    # Assert
    tags = {
        entry["detector_tag"]: entry["count"] for entry in summary["top_detector_tags"]
    }
    assert tags == {"d1": 2, "d2": 1}


def test_summarize_top_defect_pattern_tags_supports_legacy_key():
    # Arrange
    records = [
        {"hook": "h", "defect_pattern_tag": "missing-cleanup"},
        {"hook": "h", "defect_pattern": "missing-cleanup"},  # legacy
        {"hook": "h", "defect_pattern": "shallow-validation"},
    ]

    # Act
    summary = audit_summarize.summarize(records)

    # Assert
    tags = {
        entry["defect_pattern_tag"]: entry["count"]
        for entry in summary["top_defect_pattern_tags"]
    }
    assert tags == {"missing-cleanup": 2, "shallow-validation": 1}


def test_summarize_skips_blank_reasons_and_tags():
    # Arrange
    records = [
        {"hook": "h", "reason": "", "detector_tag": "", "defect_pattern_tag": ""},
        {"hook": "h", "reason": None, "detector_tag": None, "defect_pattern_tag": None},
        {"hook": "h", "reason": 123, "detector_tag": 456, "defect_pattern_tag": []},
    ]

    # Act
    summary = audit_summarize.summarize(records)

    # Assert
    assert summary["top_reasons"] == []
    assert summary["top_detector_tags"] == []
    assert summary["top_defect_pattern_tags"] == []


# --------------------------------------------------------------------------- #
# _format_table
# --------------------------------------------------------------------------- #


def test_format_table_includes_total_and_sections():
    # Arrange
    records = [
        {
            "hook": "h",
            "decision": "block",
            "latency_ms": 10,
            "reason": "boom",
            "detector_tag": "d",
            "defect_pattern_tag": "missing-cleanup",
            "suppressed": False,
        }
    ]
    summary = audit_summarize.summarize(records)

    # Act
    text = audit_summarize._format_table(summary)

    # Assert
    assert "Total records: 1" in text
    assert "Counts by hook:" in text
    assert "Counts by decision:" in text
    assert "Latency by hook" in text
    assert "False-positive estimates" in text
    assert "Top reasons:" in text
    assert "Top detector tags:" in text
    assert "Top defect pattern tags:" in text


def test_format_table_omits_latency_section_when_empty():
    # Arrange
    records = [{"hook": "h", "decision": "allow"}]
    summary = audit_summarize.summarize(records)

    # Act
    text = audit_summarize._format_table(summary)

    # Assert
    assert "Latency by hook" not in text


# --------------------------------------------------------------------------- #
# _resolve_log_paths
# --------------------------------------------------------------------------- #


def test_resolve_log_paths_default_includes_backup():
    # Arrange/Act
    paths = audit_summarize._resolve_log_paths(None)

    # Assert
    assert paths == [
        audit_summarize.DEFAULT_LOG_PATH,
        audit_summarize.DEFAULT_BACKUP_PATH,
    ]


def test_resolve_log_paths_default_skips_backup():
    # Arrange/Act
    paths = audit_summarize._resolve_log_paths(None, include_backup=False)

    # Assert
    assert paths == [audit_summarize.DEFAULT_LOG_PATH]


def test_resolve_log_paths_custom_includes_backup_suffix():
    # Arrange/Act
    paths = audit_summarize._resolve_log_paths("/tmp/custom.log")

    # Assert
    assert paths == ["/tmp/custom.log", "/tmp/custom.log.1"]


def test_resolve_log_paths_custom_no_backup():
    # Arrange/Act
    paths = audit_summarize._resolve_log_paths("/tmp/custom.log", include_backup=False)

    # Assert
    assert paths == ["/tmp/custom.log"]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_table_output(tmp_path, capsys):
    # Arrange
    log = tmp_path / "hooks.log"
    _write_log(
        log,
        [
            {"ts": "2026-05-01T00:00:00Z", "hook": "h", "decision": "block"},
            {"ts": "2026-05-01T00:00:01Z", "hook": "h", "decision": "allow"},
        ],
    )

    # Act
    code = audit_summarize._cli(
        ["--log-path", str(log), "--no-backup", "--format", "table"]
    )

    # Assert
    assert code == 0
    captured = capsys.readouterr()
    assert "Total records: 2" in captured.out
    assert "block" in captured.out
    assert "allow" in captured.out


def test_cli_json_output(tmp_path, capsys):
    # Arrange
    log = tmp_path / "hooks.log"
    _write_log(
        log,
        [
            {"ts": "2026-05-01T00:00:00Z", "hook": "h", "decision": "block"},
            {"ts": "2026-05-01T00:00:01Z", "hook": "h", "decision": "allow"},
        ],
    )

    # Act
    code = audit_summarize._cli(
        ["--log-path", str(log), "--no-backup", "--format", "json"]
    )

    # Assert
    assert code == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["total_records"] == 2
    assert parsed["counts_by_hook"]["h"] == 2


def test_cli_window_filters(tmp_path, capsys):
    # Arrange
    now = time.time()
    fresh = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 60))
    stale = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 86400 * 30))
    log = tmp_path / "hooks.log"
    _write_log(
        log,
        [
            {"ts": fresh, "hook": "fresh"},
            {"ts": stale, "hook": "stale"},
        ],
    )

    # Act
    code = audit_summarize._cli(
        [
            "--log-path",
            str(log),
            "--no-backup",
            "--window",
            "1h",
            "--format",
            "json",
        ]
    )

    # Assert
    assert code == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["total_records"] == 1
    assert "fresh" in parsed["counts_by_hook"]
    assert "stale" not in parsed["counts_by_hook"]


def test_cli_invalid_window_returns_2(capsys):
    # Arrange/Act
    code = audit_summarize._cli(["--window", "abc"])

    # Assert
    assert code == 2
    err = capsys.readouterr().err
    assert "invalid window spec" in err


def test_cli_top_zero_clamps_to_one(tmp_path, capsys):
    # Arrange
    log = tmp_path / "hooks.log"
    _write_log(
        log,
        [
            {"ts": "2026-05-01T00:00:00Z", "hook": "h", "reason": "r1"},
            {"ts": "2026-05-01T00:00:01Z", "hook": "h", "reason": "r2"},
        ],
    )

    # Act
    code = audit_summarize._cli(
        [
            "--log-path",
            str(log),
            "--no-backup",
            "--top",
            "0",
            "--format",
            "json",
        ]
    )

    # Assert
    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert len(parsed["top_reasons"]) == 1


def test_cli_default_log_path(monkeypatch, tmp_path, capsys):
    # Arrange: redirect default to a temp log
    log = tmp_path / "hooks.log"
    _write_log(log, [{"hook": "h", "decision": "allow"}])
    monkeypatch.setattr(audit_summarize, "DEFAULT_LOG_PATH", str(log))
    monkeypatch.setattr(audit_summarize, "DEFAULT_BACKUP_PATH", str(log) + ".1")

    # Act
    code = audit_summarize._cli(["--format", "json"])

    # Assert
    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["total_records"] == 1


def test_cli_main_runs_through_argv(monkeypatch, tmp_path, capsys):
    # Arrange
    log = tmp_path / "hooks.log"
    _write_log(log, [{"hook": "h", "decision": "allow"}])
    argv = [
        "audit_summarize.py",
        "--log-path",
        str(log),
        "--no-backup",
        "--format",
        "table",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    # Act
    code = audit_summarize._cli(sys.argv[1:])

    # Assert
    assert code == 0


# --------------------------------------------------------------------------- #
# parse_ts
# --------------------------------------------------------------------------- #


def test_parse_ts_valid_format():
    out = audit_summarize._parse_ts("2026-05-01T00:00:00Z")
    assert out is not None


def test_parse_ts_invalid_format():
    assert audit_summarize._parse_ts("not a timestamp") is None


def test_parse_ts_non_string():
    assert audit_summarize._parse_ts(12345) is None  # type: ignore[arg-type]


def test_parse_ts_none():
    assert audit_summarize._parse_ts(None) is None  # type: ignore[arg-type]
