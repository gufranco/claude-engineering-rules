from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from faker import Faker

from _helpers.audit_log_support import (
    DEFECT_PATTERN_TAG_LIMIT,
    DETECTOR_TAG_LIMIT,
    EXCERPT_LIMIT,
    _read_records,
    audit_log,
)


def test_cli_writes_record_with_legacy_flags(isolated_log: Path, faker: Faker) -> None:
    # Arrange
    reason = faker.sentence()
    command = f"echo {faker.word()}"
    argv = [
        "--hook",
        "large-file-blocker",
        "--decision",
        "block",
        "--tool",
        "Bash",
        "--reason",
        reason,
        "--command",
        command,
    ]

    # Act
    code = audit_log._cli(argv)

    # Assert
    assert code == 0
    records = _read_records(isolated_log)
    assert len(records) == 1
    entry = records[0]
    assert entry["hook"] == "large-file-blocker"
    assert entry["decision"] == "block"
    assert entry["tool"] == "Bash"
    assert entry["reason"] == reason
    assert entry["command_excerpt"] == command


def _new_schema_argv(file_path: str, latency: int) -> list[str]:
    return [
        "--hook",
        "mutation-method-blocker",
        "--decision",
        "block",
        "--decision-class",
        "block",
        "--detector-tag",
        "array.push",
        "--defect-pattern-tag",
        "missing-cleanup",
        "--confidence-score",
        "8",
        "--file-path",
        file_path,
        "--latency-ms",
        str(latency),
    ]


def test_cli_writes_record_with_new_schema_flags(
    isolated_log: Path, faker: Faker
) -> None:
    # Arrange
    file_path = f"/repo/src/{faker.word()}.ts"
    latency = faker.pyint(min_value=1, max_value=999)
    argv = _new_schema_argv(file_path, latency)

    # Act
    code = audit_log._cli(argv)

    # Assert
    assert code == 0
    records = _read_records(isolated_log)
    entry = records[0]
    assert entry["decision_class"] == "block"
    assert entry["detector_tag"] == "array.push"
    assert entry["defect_pattern_tag"] == "missing-cleanup"
    assert entry["confidence_score"] == 8
    assert entry["file_path"] == file_path
    assert entry["latency_ms"] == latency


def test_cli_rejects_unknown_decision_class(
    capsys: pytest.CaptureFixture[str], isolated_log: Path
) -> None:
    # Arrange
    argv = [
        "--hook",
        "x",
        "--decision",
        "block",
        "--decision-class",
        "nonsense",
    ]

    # Act
    with pytest.raises(SystemExit) as raised:
        audit_log._cli(argv)

    # Assert
    assert raised.value.code == 2
    assert "invalid choice: 'nonsense'" in capsys.readouterr().err
    assert _read_records(isolated_log) == []


def test_cli_rejects_invalid_decision(
    capsys: pytest.CaptureFixture[str], isolated_log: Path
) -> None:
    # Arrange
    argv = ["--hook", "x", "--decision", "wat"]

    # Act
    with pytest.raises(SystemExit) as raised:
        audit_log._cli(argv)

    # Assert
    assert raised.value.code == 2
    assert "invalid choice: 'wat'" in capsys.readouterr().err
    assert _read_records(isolated_log) == []


def test_cli_writes_a_minimal_allow_record(isolated_log: Path, faker: Faker) -> None:
    # Arrange
    hook = faker.word()
    argv = ["--hook", hook, "--decision", "allow"]

    # Act
    rc = audit_log._cli(argv)

    # Assert
    assert rc == 0
    records = _read_records(isolated_log)
    assert [(r["hook"], r["decision"]) for r in records] == [(hook, "allow")]


def test_module_can_be_imported_repeatedly() -> None:
    # Arrange
    module = audit_log

    # Act
    reloaded = importlib.reload(module)

    # Assert
    assert (
        reloaded.MAX_BYTES,
        reloaded.MAX_EXCERPT,
        reloaded.MAX_DETECTOR_TAG,
        reloaded.MAX_DEFECT_PATTERN_TAG,
    ) == (5 * 1024 * 1024, EXCERPT_LIMIT, DETECTOR_TAG_LIMIT, DEFECT_PATTERN_TAG_LIMIT)
