"""Date setter mutation coverage.

Item 121 of the plan. Validates the 16 Date prototype setters (local + UTC),
the new Date(d.setMonth(...)) constructor-chain anti-pattern, and confirms
date-fns immutable helpers stay clean.
"""

from __future__ import annotations

import pytest

from conftest import make_edit_payload, make_write_payload

DATE_SETTERS: list[tuple[str, str]] = [
    ("setDate", "myDate.setDate(15)"),
    ("setFullYear", "myDate.setFullYear(2026)"),
    ("setHours", "myDate.setHours(12)"),
    ("setMilliseconds", "myDate.setMilliseconds(500)"),
    ("setMinutes", "myDate.setMinutes(30)"),
    ("setMonth", "myDate.setMonth(0)"),
    ("setSeconds", "myDate.setSeconds(45)"),
    ("setTime", "myDate.setTime(0)"),
    ("setYear", "myDate.setYear(2026)"),
    ("setUTCDate", "myDate.setUTCDate(15)"),
    ("setUTCFullYear", "myDate.setUTCFullYear(2026)"),
    ("setUTCHours", "myDate.setUTCHours(12)"),
    ("setUTCMilliseconds", "myDate.setUTCMilliseconds(500)"),
    ("setUTCMinutes", "myDate.setUTCMinutes(30)"),
    ("setUTCMonth", "myDate.setUTCMonth(0)"),
    ("setUTCSeconds", "myDate.setUTCSeconds(45)"),
]


@pytest.mark.parametrize(("setter", "snippet"), DATE_SETTERS)
def test_date_setter_blocks(run_hook, setter, snippet):
    # Arrange
    content = f"const myDate = new Date()\n{snippet}\n"
    payload = make_write_payload("/repo/src/app.ts", content)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{setter}: expected block, got {code}\n{stderr}"
    assert f"date.{setter}" in stderr, f"{setter}: detector missing"


def test_date_constructor_chain_blocks(run_hook):
    # Arrange
    content = "const previousMonth = new Date(myDate.setMonth(myDate.getMonth() - 1))\n"
    payload = make_write_payload("/repo/src/app.ts", content)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "date.constructor-chain" in stderr


DATE_ALLOWED: list[tuple[str, str]] = [
    ("date-fns-sub-months", "const previousMonth = subMonths(myDate, 1)"),
    ("date-fns-add-days", "const nextWeek = addDays(myDate, 7)"),
    ("format-iso", "const isoTimestamp = formatISO(myDate)"),
    ("getter-only", "const month = myDate.getMonth()"),
    ("date-fns-set-hours", "const startOfDay = setHours(myDate, 0)"),
    ("now", "const nowTimestamp = Date.now()"),
]


@pytest.mark.parametrize(("label", "snippet"), DATE_ALLOWED)
def test_date_immutable_helpers_pass(run_hook, label, snippet):
    # Arrange
    content = f"const myDate = new Date()\n{snippet}\n"
    payload = make_write_payload("/repo/src/app.ts", content)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{label}: unexpected block\n{stderr}"


def test_date_setter_without_receiver_hint_skipped(run_hook):
    # Arrange
    snippet = "calendar.setMonth(0)"
    payload = make_edit_payload("/repo/src/app.ts", snippet)

    # Act
    code, _ = run_hook(payload)

    # Assert
    assert code == 0
