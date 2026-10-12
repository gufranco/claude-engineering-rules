from __future__ import annotations

import datetime as _dt
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "maintenance.py"

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("maintenance", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
maintenance = importlib.util.module_from_spec(_spec)
sys.modules["maintenance"] = maintenance
_spec.loader.exec_module(maintenance)


def _date_fixed_at(day: _dt.date) -> type[_dt.date]:
    return type("_FakeDate", (_dt.date,), {"today": classmethod(lambda cls: day)})


def test_watch_list_is_non_empty() -> None:
    # Arrange
    entries = maintenance.WATCH_LIST

    # Act
    invalid = [
        entry
        for entry in entries
        if not (
            entry.name
            and 0 <= entry.stage <= 4
            and entry.url
            and entry.rationale
            and entry.recognition_target
        )
    ]

    # Assert
    assert len(entries) >= 1
    assert invalid == []


def test_format_watch_list_renders_each_entry() -> None:
    # Arrange
    entries = maintenance.WATCH_LIST

    # Act
    rendered = maintenance._format_watch_list(entries)

    # Assert
    assert "# TC39 Watch List" in rendered
    assert [(e.name in rendered, e.url in rendered) for e in entries] == [
        (True, True)
    ] * len(entries)


def test_format_watch_list_with_empty_tuple() -> None:
    # Arrange
    entries = ()

    # Act
    rendered = maintenance._format_watch_list(entries)

    # Assert
    assert "# TC39 Watch List" in rendered
    assert "## " not in rendered


@pytest.mark.parametrize(
    "input_date, expected",
    [
        (_dt.date(2026, 1, 1), _dt.date(2026, 1, 5)),
        (_dt.date(2026, 4, 15), _dt.date(2026, 4, 6)),
        (_dt.date(2026, 7, 31), _dt.date(2026, 7, 6)),
        (_dt.date(2026, 10, 5), _dt.date(2026, 10, 5)),
        (_dt.date(2024, 4, 1), _dt.date(2024, 4, 1)),
    ],
)
def test_quarter_first_monday_known_dates(input_date, expected) -> None:
    # Arrange
    day = input_date

    # Act
    result = maintenance._quarter_first_monday(day)

    # Assert
    assert result == expected


def test_is_quarterly_review_day_true_on_first_monday() -> None:
    # Arrange
    today = _dt.date(2026, 1, 5)

    # Act
    result = maintenance.is_quarterly_review_day(today)

    # Assert
    assert result is True


def test_is_quarterly_review_day_false_on_other_days() -> None:
    # Arrange
    today = _dt.date(2026, 1, 6)

    # Act
    result = maintenance.is_quarterly_review_day(today)

    # Assert
    assert result is False


def test_is_quarterly_review_day_uses_today_by_default(monkeypatch) -> None:
    # Arrange
    monkeypatch.setattr(maintenance._dt, "date", _date_fixed_at(_dt.date(2026, 1, 5)))

    # Act
    result = maintenance.is_quarterly_review_day()

    # Assert
    assert result is True


def test_quarterly_message_includes_iso_date() -> None:
    # Arrange
    today = _dt.date(2026, 5, 10)

    # Act
    message = maintenance._quarterly_message(today)

    # Assert
    assert "2026-05-10" in message
    assert "watch-list" in message


def test_cmd_watch_list_prints_to_stdout(capsys) -> None:
    # Arrange
    args = None

    # Act
    rc = maintenance._cmd_watch_list(args)

    # Assert
    captured = capsys.readouterr()
    assert rc == 0
    assert "# TC39 Watch List" in captured.out


def test_cmd_quarterly_check_force_prints_message(capsys) -> None:
    # Arrange
    class _Args:
        force = True

    # Act
    rc = maintenance._cmd_quarterly_check(_Args())

    # Assert
    captured = capsys.readouterr()
    assert rc == 0
    assert "Quarterly review due" in captured.out


def test_cmd_quarterly_check_silent_when_not_due(monkeypatch, capsys) -> None:
    # Arrange
    args = SimpleNamespace(force=False)
    monkeypatch.setattr(maintenance._dt, "date", _date_fixed_at(_dt.date(2026, 5, 10)))

    # Act
    rc = maintenance._cmd_quarterly_check(args)

    # Assert
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""


def test_cmd_quarterly_check_due_prints_message(monkeypatch, capsys) -> None:
    # Arrange
    args = SimpleNamespace(force=False)
    monkeypatch.setattr(maintenance._dt, "date", _date_fixed_at(_dt.date(2026, 1, 5)))

    # Act
    rc = maintenance._cmd_quarterly_check(args)

    # Assert
    captured = capsys.readouterr()
    assert rc == 0
    assert "Quarterly review due" in captured.out


def test_main_dispatches_watch_list(capsys) -> None:
    # Arrange
    argv = ["watch-list"]

    # Act
    rc = maintenance.main(argv)

    # Assert
    captured = capsys.readouterr()
    assert rc == 0
    assert "# TC39 Watch List" in captured.out


def test_main_dispatches_quarterly_check_force(capsys) -> None:
    # Arrange
    argv = ["quarterly-check", "--force"]

    # Act
    rc = maintenance.main(argv)

    # Assert
    captured = capsys.readouterr()
    assert rc == 0
    assert "Quarterly review due" in captured.out


def test_main_module_entry_runs_as_subprocess() -> None:
    # Arrange
    script = REPO_ROOT / ".github" / "scripts" / "maintenance.py"

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
