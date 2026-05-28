"""Tests for `scripts/hook_perf.py`.

Spec: `specs/2026-05-09-claude-config-state-of-art/plan.md` 1.1.7.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib.hook_perf import DEFAULT_BUDGET_MS, with_perf_budget  # noqa: E402


def test_under_budget_does_not_emit(monkeypatch):
    # Arrange
    captured: list[dict[str, object]] = []

    def fake_record(**fields):
        captured.append(fields)

    fake_module = type(sys)("audit_log")
    fake_module.record = fake_record  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    @with_perf_budget(budget_ms=10000, hook_name="fast-hook")
    def fast_hook():
        return 0

    # Act
    code = fast_hook()

    # Assert
    assert code == 0
    assert captured == []


def test_over_budget_emits_event(monkeypatch):
    # Arrange
    captured: list[dict[str, object]] = []

    def fake_record(**fields):
        captured.append(fields)

    fake_module = type(sys)("audit_log")
    fake_module.record = fake_record  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    @with_perf_budget(budget_ms=1, hook_name="slow-hook")
    def slow_hook():
        time.sleep(0.05)
        return 7

    # Act
    code = slow_hook()

    # Assert
    assert code == 7
    assert len(captured) == 1
    entry = captured[0]
    assert entry["hook"] == "slow-hook"
    assert entry["decision"] == "budget_exceeded"
    assert entry["budget_ms"] == 1
    assert isinstance(entry["latency_ms"], int)
    assert entry["latency_ms"] >= 1


def test_disable_env_skips_emit(monkeypatch):
    # Arrange
    monkeypatch.setenv("CLAUDE_HOOK_PERF_DISABLE", "1")
    captured: list[dict[str, object]] = []
    fake_module = type(sys)("audit_log")
    fake_module.record = lambda **f: captured.append(f)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    @with_perf_budget(budget_ms=1, hook_name="x")
    def hook():
        time.sleep(0.05)
        return 0

    # Act
    code = hook()

    # Assert
    assert code == 0
    assert captured == []


def test_default_budget_constant_is_200ms():
    assert DEFAULT_BUDGET_MS == 200


def test_decorator_preserves_function_name():
    @with_perf_budget(hook_name="x")
    def my_hook():
        return 0

    assert my_hook.__name__ == "my_hook"


def test_decorator_swallows_audit_exceptions(monkeypatch):
    # Arrange
    def boom(**_fields):
        raise OSError("disk full")

    fake_module = type(sys)("audit_log")
    fake_module.record = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    @with_perf_budget(budget_ms=1, hook_name="x")
    def slow():
        time.sleep(0.05)
        return 3

    # Act/Assert
    assert slow() == 3


def test_decorator_swallows_typeerror_from_record(monkeypatch):
    # Arrange
    def boom(**_fields):
        raise TypeError("bad signature")

    fake_module = type(sys)("audit_log")
    fake_module.record = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    @with_perf_budget(budget_ms=1, hook_name="x")
    def slow():
        time.sleep(0.05)
        return 3

    # Act/Assert
    assert slow() == 3


def test_decorator_swallows_valueerror_from_record(monkeypatch):
    # Arrange
    def boom(**_fields):
        raise ValueError("invalid")

    fake_module = type(sys)("audit_log")
    fake_module.record = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    @with_perf_budget(budget_ms=1, hook_name="x")
    def slow():
        time.sleep(0.05)
        return 3

    # Act/Assert
    assert slow() == 3


def test_decorator_silent_when_audit_module_lacks_record(monkeypatch):
    # Arrange: audit_log module without `record` -> ImportError on `from import`
    fake_module = type(sys)("audit_log")
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    @with_perf_budget(budget_ms=1, hook_name="x")
    def slow():
        time.sleep(0.05)
        return 5

    # Act/Assert: must not raise
    assert slow() == 5


def test_resolve_hook_name_uses_function_module(monkeypatch):
    # Arrange: function with non-__main__ module
    captured: list[dict[str, object]] = []
    fake_module = type(sys)("audit_log")
    fake_module.record = lambda **f: captured.append(f)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    @with_perf_budget(budget_ms=1)
    def slow():
        time.sleep(0.05)
        return 0

    # Act
    slow()

    # Assert
    assert len(captured) == 1
    assert captured[0]["hook"] != "unknown"


def test_resolve_hook_name_falls_back_to_main_module_basename(monkeypatch):
    # Arrange: function whose __module__ is __main__, real __main__ has __file__
    captured: list[dict[str, object]] = []
    fake_module = type(sys)("audit_log")
    fake_module.record = lambda **f: captured.append(f)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    fake_main = type(sys)("__main__")
    fake_main.__file__ = "/some/path/to/my-hook.py"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "__main__", fake_main)

    def slow():
        time.sleep(0.05)
        return 0

    slow.__module__ = "__main__"
    decorated = with_perf_budget(budget_ms=1)(slow)

    # Act
    decorated()

    # Assert
    assert len(captured) == 1
    assert captured[0]["hook"] == "my-hook"


def test_resolve_hook_name_unknown_when_no_main_file(monkeypatch):
    # Arrange: __main__ exists but has empty __file__
    captured: list[dict[str, object]] = []
    fake_module = type(sys)("audit_log")
    fake_module.record = lambda **f: captured.append(f)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)

    fake_main = type(sys)("__main__")
    fake_main.__file__ = ""  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "__main__", fake_main)

    def slow():
        time.sleep(0.05)
        return 0

    slow.__module__ = "__main__"
    decorated = with_perf_budget(budget_ms=1)(slow)

    # Act
    decorated()

    # Assert
    assert captured[0]["hook"] == "unknown"


def test_resolve_hook_name_unknown_when_main_module_missing(monkeypatch):
    # Arrange: no __main__ in sys.modules
    captured: list[dict[str, object]] = []
    fake_module = type(sys)("audit_log")
    fake_module.record = lambda **f: captured.append(f)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)
    monkeypatch.delitem(sys.modules, "__main__", raising=False)

    def slow():
        time.sleep(0.05)
        return 0

    slow.__module__ = "__main__"
    decorated = with_perf_budget(budget_ms=1)(slow)

    # Act
    decorated()

    # Assert
    assert captured[0]["hook"] == "unknown"


def test_resolve_hook_name_unknown_when_function_has_no_module(monkeypatch):
    # Arrange
    captured: list[dict[str, object]] = []
    fake_module = type(sys)("audit_log")
    fake_module.record = lambda **f: captured.append(f)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audit_log", fake_module)
    monkeypatch.delitem(sys.modules, "__main__", raising=False)

    def slow():
        time.sleep(0.05)
        return 0

    slow.__module__ = ""
    decorated = with_perf_budget(budget_ms=1)(slow)

    # Act
    decorated()

    # Assert
    assert captured[0]["hook"] == "unknown"
