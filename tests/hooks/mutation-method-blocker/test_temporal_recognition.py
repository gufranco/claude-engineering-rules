"""Temporal API recognition (Stage 4, ES2026).

Items 162-165 of the plan. Verifies:

  - Date setter fix hints adapt: files that import or reference `Temporal.*`
    get a Temporal-first hint; other files get the date-fns fallback hint.
  - Temporal chain methods (`.add`, `.subtract`, `.with`, `.until`, `.since`,
    `.round`) do not collide with the Map / Set detectors when called on a
    tracked Temporal receiver, even when the surrounding window contains
    a `new Set(...)` declaration.
  - Legitimate Temporal usage (`Temporal.PlainDate.from(...).with({...})`,
    `Temporal.Now.instant().add({ hours: 1 })`) is not flagged.
"""

from __future__ import annotations

from conftest import make_write_payload

TEMPORAL_POLYFILL_HEADER = "import { Temporal } from '@js-temporal/polyfill';\n"
TEMPORAL_NATIVE_HEADER = (
    "// Temporal is Stage 4 / ES2026; native in Chrome 144+, Firefox 139+.\n"
)


def test_date_setter_with_temporal_import_suggests_temporal(run_hook):
    # Arrange
    content = TEMPORAL_POLYFILL_HEADER + "const d = new Date();\n" + "d.setMonth(5);\n"
    payload = make_write_payload("/repo/src/calendar.ts", content)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "Temporal" in stderr
    assert "Temporal.PlainDate" in stderr or ".with(" in stderr


def test_date_setter_without_temporal_suggests_date_fns(run_hook):
    # Arrange
    content = "const d = new Date();\n" + "d.setMonth(5);\n"
    payload = make_write_payload("/repo/src/calendar.ts", content)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "date-fns" in stderr
    assert "subMonths" in stderr or "addMonths" in stderr or "setMonth(d, m)" in stderr


def test_date_setter_with_native_temporal_use_suggests_temporal(run_hook):
    # Arrange
    content = (
        TEMPORAL_NATIVE_HEADER
        + "const now = Temporal.Now.instant();\n"
        + "const legacy = new Date();\n"
        + "legacy.setHours(10);\n"
    )
    payload = make_write_payload("/repo/src/calendar.ts", content)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "Temporal" in stderr


def test_temporal_now_instant_add_not_flagged_as_set_add(run_hook):
    # Arrange
    content = (
        TEMPORAL_POLYFILL_HEADER
        + "const expirations = new Set<string>();\n"
        + "const now = Temporal.Now.instant();\n"
        + "const future = now.add({ hours: 1 });\n"
        + "expirations.has(future.toString());\n"
    )
    payload = make_write_payload("/repo/src/expiry.ts", content)

    # Act
    code, _stderr = run_hook(payload)

    # Assert
    assert code == 0


def test_temporal_plain_date_with_not_flagged(run_hook):
    # Arrange
    content = (
        TEMPORAL_POLYFILL_HEADER
        + "const start = Temporal.PlainDate.from('2026-01-01');\n"
        + "const next = start.with({ month: 2 });\n"
        + "const later = start.add({ days: 7 });\n"
    )
    payload = make_write_payload("/repo/src/dates.ts", content)

    # Act
    code, _stderr = run_hook(payload)

    # Assert
    assert code == 0


def test_temporal_zoned_datetime_chain_not_flagged(run_hook):
    # Arrange
    content = (
        TEMPORAL_POLYFILL_HEADER
        + "const zoned = Temporal.ZonedDateTime.from({\n"
        + "  timeZone: 'America/Sao_Paulo',\n"
        + "  year: 2026,\n"
        + "  month: 5,\n"
        + "  day: 10,\n"
        + "});\n"
        + "const tomorrow = zoned.add({ days: 1 });\n"
        + "const earlier = zoned.subtract({ hours: 3 });\n"
        + "const rounded = zoned.round('day');\n"
    )
    payload = make_write_payload("/repo/src/zoned.ts", content)

    # Act
    code, _stderr = run_hook(payload)

    # Assert
    assert code == 0


def test_temporal_duration_arithmetic_not_flagged(run_hook):
    # Arrange
    content = (
        TEMPORAL_POLYFILL_HEADER
        + "const dur = Temporal.Duration.from({ hours: 1, minutes: 30 });\n"
        + "const doubled = dur.add(dur);\n"
        + "const negated = dur.negated();\n"
        + "const total = dur.total('minutes');\n"
    )
    payload = make_write_payload("/repo/src/duration.ts", content)

    # Act
    code, _stderr = run_hook(payload)

    # Assert
    assert code == 0


def test_temporal_chain_inside_set_window_still_safe(run_hook):
    # Arrange
    content = (
        TEMPORAL_POLYFILL_HEADER
        + "const cache: Set<string> = new Set();\n"
        + "function refresh(t: Temporal.Instant) {\n"
        + "  const future = t.add({ minutes: 5 });\n"
        + "  return future.toString();\n"
        + "}\n"
    )
    payload = make_write_payload("/repo/src/cache.ts", content)

    # Act
    code, _stderr = run_hook(payload)

    # Assert
    assert code == 0


def test_real_set_add_still_flagged_when_temporal_in_file(run_hook):
    # Arrange
    content = (
        TEMPORAL_POLYFILL_HEADER
        + "const now = Temporal.Now.instant();\n"
        + "const tags: Set<string> = new Set();\n"
        + "tags.add('hello');\n"
    )
    payload = make_write_payload("/repo/src/tags.ts", content)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "set.add" in stderr.lower() or "collection.set.add" in stderr.lower()


def test_real_map_set_still_flagged_when_temporal_in_file(run_hook):
    # Arrange
    content = (
        TEMPORAL_POLYFILL_HEADER
        + "const now = Temporal.Now.instant();\n"
        + "const lookup: Map<string, number> = new Map();\n"
        + "lookup.set('a', 1);\n"
    )
    payload = make_write_payload("/repo/src/lookup.ts", content)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "map.set" in stderr.lower() or "collection.map.set" in stderr.lower()
