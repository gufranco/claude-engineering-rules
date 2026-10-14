from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_cli import allowlist_tables, handle_cli_flags  # noqa: E402

VERSION = "9.9.9"


def test_no_flag_returns_none() -> None:
    # Arrange
    argv: list[str] = []

    # Act
    rc = handle_cli_flags(argv, VERSION, str(HOOKS_DIR))

    # Assert
    assert rc is None


def test_unknown_flag_returns_none() -> None:
    # Arrange
    argv = ["--batch"]

    # Act
    rc = handle_cli_flags(argv, VERSION, str(HOOKS_DIR))

    # Assert
    assert rc is None


def test_version_flag_prints_the_version(capsys: pytest.CaptureFixture[str]) -> None:
    # Arrange
    argv = ["-V"]

    # Act
    rc = handle_cli_flags(argv, VERSION, str(HOOKS_DIR))

    # Assert
    assert rc == 0
    assert capsys.readouterr().out == f"mutation-method-blocker {VERSION}\n"


def test_print_detectors_reads_the_catalog_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    catalog = {
        "exact": {"a": {"code": "MMB-2"}, "b": {"hint": "no code"}},
        "by_category": {"c": {"code": "MMB-1"}},
    }
    (tmp_path / "mutation_fix_suggestions.json").write_text(
        json.dumps(catalog), encoding="utf-8"
    )

    # Act
    rc = handle_cli_flags(["--print-detectors"], VERSION, str(tmp_path))

    # Assert
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == {
        "version": VERSION,
        "detectors": ["MMB-1", "MMB-2"],
    }


def test_print_detectors_reports_a_missing_catalog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    argv = ["--print-detectors"]

    # Act
    rc = handle_cli_flags(argv, VERSION, str(tmp_path))

    # Assert
    assert rc == 1
    assert "failed to read detector catalog" in capsys.readouterr().err


def test_allowlist_tables_are_sorted_and_stringified() -> None:
    # Arrange
    expected_member = ".ts"

    # Act
    tables = allowlist_tables()

    # Assert
    assert list(tables) == sorted(tables)
    assert expected_member in tables["JS_EXTS"]
    assert "STATE_MGMT_FILENAME_PATTERNS" in tables
    assert "TEMPORAL_IMMUTABLE_METHODS" in tables
