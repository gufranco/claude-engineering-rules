"""Direct-import unit tests for `hooks/rtk-rewrite.py`.

Subprocess-based tests in `test_rtk_rewrite.py` cover end-to-end behavior;
these import the hook module directly so coverage records line hits
regardless of the pytest-cov subprocess stitch.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = ROOT / "hooks" / "rtk-rewrite.py"
sys.path.insert(0, str(ROOT / "hooks"))


@pytest.fixture()
def hook(monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location("_rtk_mod", str(HOOK_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.delenv("RTK_REWRITE_DISABLE", raising=False)
    monkeypatch.delenv("CLAUDE_BYPASS_STATE", raising=False)
    return module


def _stdin_with(payload: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


def test_read_payload_returns_empty_on_malformed_json(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    # Act
    result = hook._read_payload()
    # Assert
    assert result == {}


def test_read_payload_returns_empty_on_non_dict_root(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(sys, "stdin", io.StringIO("[1,2,3]"))
    # Act
    result = hook._read_payload()
    # Assert
    assert result == {}


def test_command_too_old_true_when_binary_missing(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    def raise_fnf(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError

    monkeypatch.setattr(hook.subprocess, "run", raise_fnf)
    # Act
    result = hook._command_too_old()
    # Assert
    assert result is True


def test_command_too_old_false_when_recent(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    def fake(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(stdout="rtk 0.25.0\n", returncode=0)

    monkeypatch.setattr(hook.subprocess, "run", fake)
    # Act
    result = hook._command_too_old()
    # Assert
    assert result is False


def test_command_too_old_true_when_minor_too_low(
    hook, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    def fake(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(stdout="rtk 0.20.0\n", returncode=0)

    monkeypatch.setattr(hook.subprocess, "run", fake)
    # Act
    result = hook._command_too_old()
    # Assert
    captured = capsys.readouterr()
    assert result is True
    assert "too old" in captured.err


def test_command_too_old_false_when_version_unparseable(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    def fake(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(stdout="unknown\n", returncode=0)

    monkeypatch.setattr(hook.subprocess, "run", fake)
    # Act
    result = hook._command_too_old()
    # Assert
    assert result is False


def test_emit_allow_writes_envelope(hook, capsys: pytest.CaptureFixture[str]) -> None:
    # Arrange
    # Act
    hook._emit_allow({"command": "rtk x"})
    # Assert
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert body["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert body["hookSpecificOutput"]["updatedInput"]["command"] == "rtk x"


def test_emit_ask_writes_envelope_without_permission_decision(
    hook, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    # Act
    hook._emit_ask({"command": "rtk ask"})
    # Assert
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert "permissionDecision" not in body["hookSpecificOutput"]
    assert body["hookSpecificOutput"]["updatedInput"]["command"] == "rtk ask"


def test_main_env_disable_short_circuits(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("RTK_REWRITE_DISABLE", "1")
    # Act
    result = hook.main()
    # Assert
    assert result == 0


def test_main_file_bypass_short_circuits(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(hook, "is_bypassed", lambda _name: True)
    # Act
    result = hook.main()
    # Assert
    assert result == 0


def test_main_returns_zero_when_rtk_missing(
    hook, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    monkeypatch.setattr(hook.shutil, "which", lambda _name: None)
    # Act
    result = hook.main()
    # Assert
    captured = capsys.readouterr()
    assert result == 0
    assert "WARNING" in captured.err


def test_main_returns_zero_when_too_old(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(hook.shutil, "which", lambda _name: "/usr/bin/rtk")
    monkeypatch.setattr(hook, "_command_too_old", lambda: True)
    # Act
    result = hook.main()
    # Assert
    assert result == 0


def test_main_passes_through_when_no_command(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(hook.shutil, "which", lambda _name: "/usr/bin/rtk")
    monkeypatch.setattr(hook, "_command_too_old", lambda: False)
    _stdin_with({"tool_input": {"command": ""}}, monkeypatch)
    # Act
    result = hook.main()
    # Assert
    assert result == 0


def test_main_emits_allow_when_rtk_rewrites(
    hook, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    monkeypatch.setattr(hook.shutil, "which", lambda _name: "/usr/bin/rtk")
    monkeypatch.setattr(hook, "_command_too_old", lambda: False)
    _stdin_with({"tool_input": {"command": "git status"}}, monkeypatch)

    def fake_run(_argv: list[str], **_kwargs: object) -> object:
        return SimpleNamespace(stdout="rtk git status", returncode=0)

    monkeypatch.setattr(hook.subprocess, "run", fake_run)
    # Act
    result = hook.main()
    # Assert
    captured = capsys.readouterr()
    assert result == 0
    body = json.loads(captured.out)
    assert body["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_main_noop_when_rewrite_matches(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(hook.shutil, "which", lambda _name: "/usr/bin/rtk")
    monkeypatch.setattr(hook, "_command_too_old", lambda: False)
    _stdin_with({"tool_input": {"command": "x"}}, monkeypatch)
    monkeypatch.setattr(
        hook.subprocess, "run", lambda *_a, **_k: SimpleNamespace(stdout="x", returncode=0)
    )
    # Act
    result = hook.main()
    # Assert
    assert result == 0


def test_main_no_equivalent_passes_through(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(hook.shutil, "which", lambda _name: "/usr/bin/rtk")
    monkeypatch.setattr(hook, "_command_too_old", lambda: False)
    _stdin_with({"tool_input": {"command": "x"}}, monkeypatch)
    monkeypatch.setattr(
        hook.subprocess, "run", lambda *_a, **_k: SimpleNamespace(stdout="", returncode=1)
    )
    # Act
    result = hook.main()
    # Assert
    assert result == 0


def test_main_deny_rule_passes_through(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(hook.shutil, "which", lambda _name: "/usr/bin/rtk")
    monkeypatch.setattr(hook, "_command_too_old", lambda: False)
    _stdin_with({"tool_input": {"command": "rm -rf /"}}, monkeypatch)
    monkeypatch.setattr(
        hook.subprocess, "run", lambda *_a, **_k: SimpleNamespace(stdout="", returncode=2)
    )
    # Act
    result = hook.main()
    # Assert
    assert result == 0


def test_main_ask_rule_emits_envelope(
    hook, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    monkeypatch.setattr(hook.shutil, "which", lambda _name: "/usr/bin/rtk")
    monkeypatch.setattr(hook, "_command_too_old", lambda: False)
    _stdin_with({"tool_input": {"command": "x"}}, monkeypatch)
    monkeypatch.setattr(
        hook.subprocess, "run", lambda *_a, **_k: SimpleNamespace(stdout="rtk x", returncode=3)
    )
    # Act
    result = hook.main()
    # Assert
    captured = capsys.readouterr()
    assert result == 0
    body = json.loads(captured.out)
    assert "permissionDecision" not in body["hookSpecificOutput"]


def test_main_returns_zero_on_unknown_rtk_exit_code(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(hook.shutil, "which", lambda _name: "/usr/bin/rtk")
    monkeypatch.setattr(hook, "_command_too_old", lambda: False)
    _stdin_with({"tool_input": {"command": "x"}}, monkeypatch)
    monkeypatch.setattr(
        hook.subprocess, "run", lambda *_a, **_k: SimpleNamespace(stdout="", returncode=99)
    )
    # Act
    result = hook.main()
    # Assert
    assert result == 0


def test_main_returns_zero_on_rtk_invocation_failure(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(hook.shutil, "which", lambda _name: "/usr/bin/rtk")
    monkeypatch.setattr(hook, "_command_too_old", lambda: False)
    _stdin_with({"tool_input": {"command": "x"}}, monkeypatch)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated")

    monkeypatch.setattr(hook.subprocess, "run", boom)
    # Act
    result = hook.main()
    # Assert
    assert result == 0


def test_main_returns_zero_on_non_dict_tool_input(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(hook.shutil, "which", lambda _name: "/usr/bin/rtk")
    monkeypatch.setattr(hook, "_command_too_old", lambda: False)
    _stdin_with({"tool_input": "scalar"}, monkeypatch)
    # Act
    result = hook.main()
    # Assert
    assert result == 0


def test_main_returns_zero_on_non_string_command(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(hook.shutil, "which", lambda _name: "/usr/bin/rtk")
    monkeypatch.setattr(hook, "_command_too_old", lambda: False)
    _stdin_with({"tool_input": {"command": 42}}, monkeypatch)
    # Act
    result = hook.main()
    # Assert
    assert result == 0
