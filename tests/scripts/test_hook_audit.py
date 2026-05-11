"""Tests for `scripts/hook_audit.py`.

Spec: `specs/2026-05-09-claude-config-state-of-art/plan.md` 1.1.9.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from hook_audit import ALLOWED_DECISIONS, emit  # noqa: E402


@pytest.fixture
def captured(monkeypatch):
    rows: list[dict[str, object]] = []

    def fake_record(**fields):
        rows.append(fields)

    fake_module = type(sys)("audit_log")
    fake_module.record = fake_record  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)
    return rows


def test_minimum_payload(captured):
    # Arrange/Act
    emit("block", hook_name="x")

    # Assert
    assert captured == [{"hook": "x", "decision": "block"}]


def test_full_payload(captured):
    # Arrange/Act
    emit(
        "block",
        hook_name="my-hook",
        detector_tag="redis-incr-expire",
        reason="non-atomic",
        file_path="/repo/a.ts",
        latency_ms=42,
        suppressed=False,
        defect_pattern="optimistic-error-handling",
        confidence_score=8,
        extra={"command_excerpt": "incr foo"},
    )

    # Assert
    assert len(captured) == 1
    entry = captured[0]
    assert entry["hook"] == "my-hook"
    assert entry["decision"] == "block"
    assert entry["detector_tag"] == "redis-incr-expire"
    assert entry["reason"] == "non-atomic"
    assert entry["file_path"] == "/repo/a.ts"
    assert entry["latency_ms"] == 42
    assert entry["suppressed"] is False
    assert entry["defect_pattern"] == "optimistic-error-handling"
    assert entry["confidence_score"] == 8
    assert entry["command_excerpt"] == "incr foo"


def test_unknown_event_is_warned(captured):
    # Arrange/Act
    emit("nonsense", hook_name="x")

    # Assert
    assert captured == [
        {"hook": "x", "decision": "warn", "original_decision": "nonsense"}
    ]


def test_confidence_clamps_to_range(captured):
    # Arrange/Act
    emit("allow", hook_name="x", confidence_score=99)
    emit("allow", hook_name="x", confidence_score=-3)

    # Assert
    assert captured[0]["confidence_score"] == 10
    assert captured[1]["confidence_score"] == 1


def test_extra_does_not_override_known_keys(captured):
    # Arrange/Act
    emit(
        "block",
        hook_name="x",
        reason="real",
        extra={"reason": "hijacked"},
    )

    # Assert
    assert captured == [{"hook": "x", "decision": "block", "reason": "real"}]


def test_allowed_decisions_contains_canonical_set():
    # Assert
    assert "block" in ALLOWED_DECISIONS
    assert "allow" in ALLOWED_DECISIONS
    assert "modify" in ALLOWED_DECISIONS
    assert "defer" in ALLOWED_DECISIONS
    assert "ask" in ALLOWED_DECISIONS
    assert "bypass" in ALLOWED_DECISIONS
    assert "warn" in ALLOWED_DECISIONS
    assert "budget_exceeded" in ALLOWED_DECISIONS


def test_emit_swallows_record_exceptions(monkeypatch):
    # Arrange
    def boom(**_fields):
        raise OSError("disk full")

    fake_module = type(sys)("audit_log")
    fake_module.record = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    # Act/Assert: must not raise
    emit("block", hook_name="x")


def test_emit_returns_silently_when_audit_log_unavailable(monkeypatch):
    # Arrange: audit_log module exists but lacks `record` -> ImportError
    fake_module = type(sys)("audit_log")
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    # Act/Assert: must not raise even though `from audit_log import record` fails
    emit("block", hook_name="x", reason="r")


def test_emit_swallows_typeerror_from_record(monkeypatch):
    # Arrange
    def boom(**_fields):
        raise TypeError("bad signature")

    fake_module = type(sys)("audit_log")
    fake_module.record = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    # Act/Assert
    emit("allow", hook_name="x")


def test_emit_swallows_valueerror_from_record(monkeypatch):
    # Arrange
    def boom(**_fields):
        raise ValueError("invalid")

    fake_module = type(sys)("audit_log")
    fake_module.record = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    # Act/Assert
    emit("allow", hook_name="x")
