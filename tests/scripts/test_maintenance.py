from __future__ import annotations

import datetime as _dt
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "maintenance.py"
WATCH_LIST_HEADER = (
    "# TC39 Watch List\n"
    "\n"
    "Tracks proposals that may require new mutation detectors.\n"
    "Recognition becomes appropriate at Stage 2.\n"
)

_spec = importlib.util.spec_from_file_location("maintenance", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
maintenance = importlib.util.module_from_spec(_spec)
sys.modules["maintenance"] = maintenance
_spec.loader.exec_module(maintenance)


def _date_fixed_at(day: _dt.date) -> type[_dt.date]:
    return type("_FakeDate", (_dt.date,), {"today": classmethod(lambda cls: day)})


def test_watch_list_entries_are_complete() -> None:
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


def test_format_watch_list_renders_each_entry(faker: Faker) -> None:
    # Arrange
    entry = maintenance.WatchListEntry(
        name=faker.word(),
        stage=faker.pyint(min_value=0, max_value=4),
        last_seen=faker.date(),
        url=faker.url(),
        rationale=faker.sentence(),
        recognition_target=faker.sentence(),
    )

    # Act
    rendered = maintenance._format_watch_list((entry,))

    # Assert
    assert rendered == (
        WATCH_LIST_HEADER
        + "\n"
        + f"## {entry.name} (Stage {entry.stage})\n"
        + "\n"
        + f"- Last seen: {entry.last_seen}\n"
        + f"- URL: {entry.url}\n"
        + f"- Recognition target: {entry.recognition_target}\n"
        + f"- Rationale: {entry.rationale}\n"
    )


def test_format_watch_list_with_empty_tuple() -> None:
    # Arrange
    entries: tuple[object, ...] = ()

    # Act
    rendered = maintenance._format_watch_list(entries)

    # Assert
    assert rendered == WATCH_LIST_HEADER


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
def test_quarter_first_monday_known_dates(
    input_date: _dt.date, expected: _dt.date
) -> None:
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


def test_is_quarterly_review_day_uses_today_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    assert message == (
        "[2026-05-10] Quarterly review due. Review the TC39 finished-proposals "
        "list for new shipped features that may need fix-suggestion entries: "
        "https://github.com/tc39/proposals/blob/main/finished-proposals.md. "
        "On promotion of a Stage 3 proposal to Stage 4, evaluate adding an entry "
        "to hooks/mutation_fix_suggestions.json with the matching MMB code and a "
        '`"stage": 4` field; remove or update any pre-Stage-4 draft entry that '
        "referenced the same feature. "
        "Run: python3 .github/scripts/maintenance.py watch-list"
    )


def test_cmd_watch_list_prints_to_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    args = SimpleNamespace()

    # Act
    rc = maintenance._cmd_watch_list(args)

    # Assert
    assert rc == 0
    assert capsys.readouterr().out == maintenance._format_watch_list(
        maintenance.WATCH_LIST
    )


def test_cmd_quarterly_check_force_prints_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    today = _dt.date(2026, 5, 10)
    args = SimpleNamespace(force=True)
    monkeypatch.setattr(maintenance._dt, "date", _date_fixed_at(today))

    # Act
    rc = maintenance._cmd_quarterly_check(args)

    # Assert
    assert rc == 0
    assert capsys.readouterr().out == maintenance._quarterly_message(today) + "\n"


def test_cmd_quarterly_check_silent_when_not_due(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    args = SimpleNamespace(force=False)
    monkeypatch.setattr(maintenance._dt, "date", _date_fixed_at(_dt.date(2026, 5, 10)))

    # Act
    rc = maintenance._cmd_quarterly_check(args)

    # Assert
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""


def test_cmd_quarterly_check_due_prints_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    today = _dt.date(2026, 1, 5)
    args = SimpleNamespace(force=False)
    monkeypatch.setattr(maintenance._dt, "date", _date_fixed_at(today))

    # Act
    rc = maintenance._cmd_quarterly_check(args)

    # Assert
    assert rc == 0
    assert capsys.readouterr().out == maintenance._quarterly_message(today) + "\n"


def test_main_dispatches_watch_list(capsys: pytest.CaptureFixture[str]) -> None:
    # Arrange
    argv = ["watch-list"]

    # Act
    rc = maintenance.main(argv)

    # Assert
    assert rc == 0
    assert capsys.readouterr().out == maintenance._format_watch_list(
        maintenance.WATCH_LIST
    )


def test_main_dispatches_quarterly_check_force(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    today = _dt.date(2026, 5, 10)
    argv = ["quarterly-check", "--force"]
    monkeypatch.setattr(maintenance._dt, "date", _date_fixed_at(today))

    # Act
    rc = maintenance.main(argv)

    # Assert
    assert rc == 0
    assert capsys.readouterr().out == maintenance._quarterly_message(today) + "\n"


def test_main_module_entry_runs_as_subprocess() -> None:
    # Arrange
    argv = [sys.executable, str(SCRIPT_PATH), "watch-list"]

    # Act
    proc = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        env=apply_coverage_env(dict(os.environ)),
        timeout=15,
        check=False,
    )

    # Assert
    assert proc.returncode == 0
    assert proc.stdout.startswith(WATCH_LIST_HEADER) is True
