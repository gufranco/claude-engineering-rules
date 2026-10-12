from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from _lib.hook_perf import DEFAULT_BUDGET_MS, with_perf_budget  # noqa: E402

SLOW_SECONDS = 0.05


def _sleepy(value: int, module: str | None = None) -> Callable[[], int]:
    def run() -> int:
        time.sleep(SLOW_SECONDS)
        return value

    if module is not None:
        run.__module__ = module
    return run


def _capture_audit(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    captured: list[dict[str, object]] = []
    fake_module = type(sys)("_lib.audit_log")
    fake_module.record = lambda **fields: captured.append(fields)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "_lib.audit_log", fake_module)
    return captured


def _failing_audit(monkeypatch: pytest.MonkeyPatch, error: type[Exception]) -> None:
    def boom(**_fields: object) -> None:
        raise error("audit failure")

    fake_module = type(sys)("_lib.audit_log")
    fake_module.record = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "_lib.audit_log", fake_module)


def _fake_main(monkeypatch: pytest.MonkeyPatch, file_name: str) -> None:
    fake_main = type(sys)("__main__")
    fake_main.__file__ = file_name  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "__main__", fake_main)


def test_under_budget_does_not_emit(monkeypatch):
    # Arrange
    captured = _capture_audit(monkeypatch)
    fast_hook = with_perf_budget(budget_ms=10000, hook_name="fast-hook")(lambda: 0)

    # Act
    code = fast_hook()

    # Assert
    assert code == 0
    assert captured == []


def test_over_budget_emits_event(monkeypatch):
    # Arrange
    captured = _capture_audit(monkeypatch)
    slow_hook = with_perf_budget(budget_ms=1, hook_name="slow-hook")(_sleepy(7))

    # Act
    code = slow_hook()

    # Assert
    assert code == 7
    assert len(captured) == 1
    entry = captured[0]
    assert entry["hook"] == "slow-hook"
    assert entry["decision"] == "budget_exceeded"
    assert entry["budget_ms"] == 1
    assert isinstance(entry["latency_ms"], int) is True
    assert entry["latency_ms"] >= 1


def test_disable_env_skips_emit(monkeypatch):
    # Arrange
    monkeypatch.setenv("CLAUDE_HOOK_PERF_DISABLE", "1")
    captured = _capture_audit(monkeypatch)
    hook = with_perf_budget(budget_ms=1, hook_name="x")(_sleepy(0))

    # Act
    code = hook()

    # Assert
    assert code == 0
    assert captured == []


def test_default_budget_constant_is_200ms():
    # Arrange
    expected_ms = 200

    # Act
    budget = DEFAULT_BUDGET_MS

    # Assert
    assert budget == expected_ms


def test_decorator_preserves_function_name():
    # Arrange
    my_hook = _sleepy(0)

    # Act
    decorated = with_perf_budget(hook_name="x")(my_hook)

    # Assert
    assert decorated.__name__ == "run"


@pytest.mark.parametrize("error", [OSError, TypeError, ValueError])
def test_decorator_swallows_audit_exceptions(monkeypatch, error):
    # Arrange
    _failing_audit(monkeypatch, error)
    slow = with_perf_budget(budget_ms=1, hook_name="x")(_sleepy(3))

    # Act
    result = slow()

    # Assert
    assert result == 3


def test_decorator_silent_when_audit_module_lacks_record(monkeypatch):
    # Arrange
    monkeypatch.setitem(sys.modules, "_lib.audit_log", type(sys)("_lib.audit_log"))
    slow = with_perf_budget(budget_ms=1, hook_name="x")(_sleepy(5))

    # Act
    result = slow()

    # Assert
    assert result == 5


def test_resolve_hook_name_uses_function_module(monkeypatch):
    # Arrange
    captured = _capture_audit(monkeypatch)
    slow = with_perf_budget(budget_ms=1)(_sleepy(0))

    # Act
    slow()

    # Assert
    assert len(captured) == 1
    assert captured[0]["hook"] != "unknown"


def test_resolve_hook_name_falls_back_to_main_module_basename(monkeypatch):
    # Arrange
    captured = _capture_audit(monkeypatch)
    _fake_main(monkeypatch, "/some/path/to/my-hook.py")
    decorated = with_perf_budget(budget_ms=1)(_sleepy(0, "__main__"))

    # Act
    decorated()

    # Assert
    assert len(captured) == 1
    assert captured[0]["hook"] == "my-hook"


def test_resolve_hook_name_unknown_when_no_main_file(monkeypatch):
    # Arrange
    captured = _capture_audit(monkeypatch)
    _fake_main(monkeypatch, "")
    decorated = with_perf_budget(budget_ms=1)(_sleepy(0, "__main__"))

    # Act
    decorated()

    # Assert
    assert captured[0]["hook"] == "unknown"


def test_resolve_hook_name_unknown_when_main_module_missing(monkeypatch):
    # Arrange
    captured = _capture_audit(monkeypatch)
    monkeypatch.delitem(sys.modules, "__main__", raising=False)
    decorated = with_perf_budget(budget_ms=1)(_sleepy(0, "__main__"))

    # Act
    decorated()

    # Assert
    assert captured[0]["hook"] == "unknown"


def test_resolve_hook_name_unknown_when_function_has_no_module(monkeypatch):
    # Arrange
    captured = _capture_audit(monkeypatch)
    monkeypatch.delitem(sys.modules, "__main__", raising=False)
    decorated = with_perf_budget(budget_ms=1)(_sleepy(0, ""))

    # Act
    decorated()

    # Assert
    assert captured[0]["hook"] == "unknown"
