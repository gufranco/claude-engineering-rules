"""Tests for `scripts/maintenance.py`.

Covers the watch list formatting, quarter detection, quarterly reminder
output, and CLI dispatch.
"""

from __future__ import annotations

import datetime as _dt
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import maintenance  # noqa: E402


# --------------------------------------------------------------------------- #
# WATCH_LIST and _format_watch_list
# --------------------------------------------------------------------------- #


def test_watch_list_is_non_empty() -> None:
    assert len(maintenance.WATCH_LIST) > 0
    for entry in maintenance.WATCH_LIST:
        assert entry.name
        assert 0 <= entry.stage <= 4
        assert entry.url
        assert entry.rationale
        assert entry.recognition_target


def test_format_watch_list_renders_each_entry() -> None:
    # Arrange / Act
    rendered = maintenance._format_watch_list(maintenance.WATCH_LIST)

    # Assert
    assert "# TC39 Watch List" in rendered
    for entry in maintenance.WATCH_LIST:
        assert entry.name in rendered
        assert entry.url in rendered


def test_format_watch_list_with_empty_tuple() -> None:
    # Arrange / Act
    rendered = maintenance._format_watch_list(())

    # Assert
    assert "# TC39 Watch List" in rendered
    # Body lines after the heading should not contain entry-specific markers.
    assert "## " not in rendered


# --------------------------------------------------------------------------- #
# _quarter_first_monday and is_quarterly_review_day
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "input_date, expected",
    [
        # Q1 2026: Jan 1 is a Thursday, first Monday is Jan 5.
        (_dt.date(2026, 1, 1), _dt.date(2026, 1, 5)),
        # Q2 2026: Apr 1 is a Wednesday, first Monday is Apr 6.
        (_dt.date(2026, 4, 15), _dt.date(2026, 4, 6)),
        # Q3 2026: Jul 1 is a Wednesday, first Monday is Jul 6.
        (_dt.date(2026, 7, 31), _dt.date(2026, 7, 6)),
        # Q4 2026: Oct 1 is a Thursday, first Monday is Oct 5.
        (_dt.date(2026, 10, 5), _dt.date(2026, 10, 5)),
    ],
)
def test_quarter_first_monday_known_dates(input_date, expected) -> None:
    # Arrange / Act
    result = maintenance._quarter_first_monday(input_date)

    # Assert
    assert result == expected


def test_quarter_first_monday_when_quarter_starts_on_monday() -> None:
    # 2024-04-01 was a Monday: first Monday equals quarter start.
    assert maintenance._quarter_first_monday(_dt.date(2024, 4, 1)) == _dt.date(
        2024, 4, 1
    )


def test_is_quarterly_review_day_true_on_first_monday() -> None:
    assert maintenance.is_quarterly_review_day(_dt.date(2026, 1, 5)) is True


def test_is_quarterly_review_day_false_on_other_days() -> None:
    assert maintenance.is_quarterly_review_day(_dt.date(2026, 1, 6)) is False


def test_is_quarterly_review_day_uses_today_by_default(monkeypatch) -> None:
    # Arrange
    fake_today = _dt.date(2026, 1, 5)

    class _FakeDate(_dt.date):
        @classmethod
        def today(cls):
            return fake_today

    monkeypatch.setattr(maintenance._dt, "date", _FakeDate)

    # Act
    result = maintenance.is_quarterly_review_day()

    # Assert
    assert result is True


# --------------------------------------------------------------------------- #
# _quarterly_message
# --------------------------------------------------------------------------- #


def test_quarterly_message_includes_iso_date() -> None:
    # Arrange
    today = _dt.date(2026, 5, 10)

    # Act
    message = maintenance._quarterly_message(today)

    # Assert
    assert "2026-05-10" in message
    assert "watch-list" in message


# --------------------------------------------------------------------------- #
# _cmd_watch_list
# --------------------------------------------------------------------------- #


def test_cmd_watch_list_prints_to_stdout(capsys) -> None:
    # Arrange / Act
    rc = maintenance._cmd_watch_list(None)
    captured = capsys.readouterr()

    # Assert
    assert rc == 0
    assert "# TC39 Watch List" in captured.out


# --------------------------------------------------------------------------- #
# _cmd_quarterly_check
# --------------------------------------------------------------------------- #


def test_cmd_quarterly_check_force_prints_message(capsys) -> None:
    # Arrange
    class _Args:
        force = True

    # Act
    rc = maintenance._cmd_quarterly_check(_Args())
    captured = capsys.readouterr()

    # Assert
    assert rc == 0
    assert "Quarterly review due" in captured.out


def test_cmd_quarterly_check_silent_when_not_due(monkeypatch, capsys) -> None:
    # Arrange
    class _Args:
        force = False

    fake_today = _dt.date(2026, 5, 10)  # not first Monday of any quarter

    class _FakeDate(_dt.date):
        @classmethod
        def today(cls):
            return fake_today

    monkeypatch.setattr(maintenance._dt, "date", _FakeDate)

    # Act
    rc = maintenance._cmd_quarterly_check(_Args())
    captured = capsys.readouterr()

    # Assert
    assert rc == 0
    assert captured.out == ""


def test_cmd_quarterly_check_due_prints_message(monkeypatch, capsys) -> None:
    # Arrange
    class _Args:
        force = False

    fake_today = _dt.date(2026, 1, 5)  # first Monday of Q1 2026

    class _FakeDate(_dt.date):
        @classmethod
        def today(cls):
            return fake_today

    monkeypatch.setattr(maintenance._dt, "date", _FakeDate)

    # Act
    rc = maintenance._cmd_quarterly_check(_Args())
    captured = capsys.readouterr()

    # Assert
    assert rc == 0
    assert "Quarterly review due" in captured.out


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def test_main_dispatches_watch_list(capsys) -> None:
    rc = maintenance.main(["watch-list"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "# TC39 Watch List" in captured.out


def test_main_dispatches_quarterly_check_force(capsys) -> None:
    rc = maintenance.main(["quarterly-check", "--force"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "Quarterly review due" in captured.out


def test_main_module_entry_runs_as_subprocess(tmp_path: Path) -> None:
    # Arrange
    script = SCRIPTS_DIR / "maintenance.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(script), "watch-list"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    # Assert
    assert proc.returncode == 0
    assert "TC39 Watch List" in proc.stdout
