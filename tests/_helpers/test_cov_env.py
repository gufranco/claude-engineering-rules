"""Companion test for `tests/_helpers/cov_env.py`."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests"))

from _helpers.cov_env import apply_coverage_env  # noqa: E402


def test_adds_no_coverage_vars_when_inactive(monkeypatch) -> None:
    monkeypatch.delenv("COVERAGE_PROCESS_START", raising=False)
    monkeypatch.delenv("COVERAGE_RUN", raising=False)
    base = {"FOO": "bar"}
    result = apply_coverage_env(base, force_active=False)
    assert result["FOO"] == "bar"
    assert "COVERAGE_PROCESS_START" not in result


def test_suppresses_audit_writes_when_inactive(monkeypatch) -> None:
    monkeypatch.delenv("COVERAGE_PROCESS_START", raising=False)
    monkeypatch.delenv("COVERAGE_RUN", raising=False)
    result = apply_coverage_env({"FOO": "bar"}, force_active=False)
    assert result["CLAUDE_HOOK_AUDIT_DISABLE"] == "1"


def test_suppresses_audit_writes_when_active() -> None:
    result = apply_coverage_env({"FOO": "bar"}, force_active=True)
    assert result["CLAUDE_HOOK_AUDIT_DISABLE"] == "1"


def test_does_not_mutate_caller_env() -> None:
    base = {"FOO": "bar"}
    apply_coverage_env(base, force_active=True)
    assert base == {"FOO": "bar"}


def test_adds_coverage_env_when_active() -> None:
    base = {"FOO": "bar"}
    result = apply_coverage_env(base, force_active=True)
    assert "COVERAGE_PROCESS_START" in result
    assert "PYTHONPATH" in result
    assert "FOO" in result
    assert "_subprocess_cov" in result["PYTHONPATH"]


def test_preserves_existing_pythonpath() -> None:
    base = {"PYTHONPATH": "/existing/path"}
    result = apply_coverage_env(base, force_active=True)
    assert "/existing/path" in result["PYTHONPATH"]
    assert "_subprocess_cov" in result["PYTHONPATH"]
