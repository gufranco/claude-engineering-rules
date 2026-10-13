from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = ROOT / "hooks" / "rtk-rewrite.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

RECENT_VERSION = "0.25.0"
BYPASS_TTL_S = 120
StubFactory = Callable[..., Path]


@pytest.fixture()
def hook(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    spec = importlib.util.spec_from_file_location("_rtk_mod", str(HOOK_PATH))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.delenv("RTK_REWRITE_DISABLE", raising=False)
    monkeypatch.setenv("CLAUDE_HOOK_AUDIT_DISABLE", "1")
    monkeypatch.setattr("_lib.bypass.STATE_PATH", Path(os.devnull))
    return module


@pytest.fixture()
def rtk_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> StubFactory:
    def _install(
        *,
        version: str = RECENT_VERSION,
        rewrite_exit: int = 0,
        rewrite_stdout: str = "",
        break_after_version: bool = False,
    ) -> Path:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        log = tmp_path / "rtk-calls.log"
        corrupt = (
            "printf '#!/nonexistent/interpreter\\n' > \"$0\"\n"
            if break_after_version
            else ""
        )
        stub = bin_dir / "rtk"
        stub.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$*\" >> '{log}'\n"
            'if [ "$1" = "--version" ]; then\n'
            f"  printf 'rtk %s\\n' '{version}'\n"
            f"  {corrupt}"
            "  exit 0\n"
            "fi\n"
            'if [ "$1" = "rewrite" ]; then\n'
            f"  printf '%s' '{rewrite_stdout}'\n"
            f"  exit {rewrite_exit}\n"
            "fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
        monkeypatch.setenv("PATH", str(bin_dir))
        return log

    return _install


def _stdin_with(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))


def _calls(log: Path) -> list[str]:
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_read_payload_returns_empty_on_malformed_json(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    _stdin_with(monkeypatch, "not json")

    # Act
    result = hook._read_payload()

    # Assert
    assert result == {}


def test_read_payload_returns_empty_on_non_dict_root(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    _stdin_with(monkeypatch, "[1,2,3]")

    # Act
    result = hook._read_payload()

    # Assert
    assert result == {}


def test_command_too_old_true_when_binary_missing(
    hook: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    # Act
    result = hook._command_too_old()

    # Assert
    assert result is True


def test_command_too_old_false_when_recent(
    hook: ModuleType, rtk_on_path: StubFactory
) -> None:
    # Arrange
    rtk_on_path(version="0.25.0")

    # Act
    result = hook._command_too_old()

    # Assert
    assert result is False


def test_command_too_old_true_and_warns_when_minor_too_low(
    hook: ModuleType, rtk_on_path: StubFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    rtk_on_path(version="0.20.0")

    # Act
    result = hook._command_too_old()

    # Assert
    assert result is True
    assert "rtk 0.20.0 is too old (need >= 0.23.0)" in capsys.readouterr().err


def test_command_too_old_false_when_version_unparseable(
    hook: ModuleType, rtk_on_path: StubFactory
) -> None:
    # Arrange
    rtk_on_path(version="unknown")

    # Act
    result = hook._command_too_old()

    # Assert
    assert result is False


def test_emit_allow_writes_envelope(
    hook: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    updated_input = {"command": "rtk x"}

    # Act
    hook._emit_allow(updated_input)

    # Assert
    output = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert output["permissionDecision"] == "allow"
    assert output["updatedInput"] == {"command": "rtk x"}


def test_emit_ask_writes_envelope_without_permission_decision(
    hook: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    updated_input = {"command": "rtk ask"}

    # Act
    hook._emit_ask(updated_input)

    # Assert
    output = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert output["updatedInput"] == {"command": "rtk ask"}


def test_main_env_disable_never_calls_rtk(
    hook: ModuleType,
    rtk_on_path: StubFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    log = rtk_on_path(rewrite_stdout="rtk x")
    monkeypatch.setenv("RTK_REWRITE_DISABLE", "1")
    _stdin_with(monkeypatch, {"tool_input": {"command": "x"}})

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert _calls(log) == []
    assert capsys.readouterr().out == ""


def test_main_file_bypass_never_calls_rtk(
    hook: ModuleType,
    rtk_on_path: StubFactory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    log = rtk_on_path(rewrite_stdout="rtk x")
    state = tmp_path / "bypass-state.json"
    set_bypass("rtk-rewrite", ttl_seconds=BYPASS_TTL_S, state_path=state)
    monkeypatch.setattr("_lib.bypass.STATE_PATH", state)
    _stdin_with(monkeypatch, {"tool_input": {"command": "x"}})

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert _calls(log) == []
    assert capsys.readouterr().out == ""


def test_main_passes_through_on_unknown_rtk_exit_code(
    hook: ModuleType,
    rtk_on_path: StubFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    log = rtk_on_path(rewrite_exit=99, rewrite_stdout="rtk x")
    _stdin_with(monkeypatch, {"tool_input": {"command": "x"}})

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert _calls(log) == ["--version", "rewrite x"]
    assert capsys.readouterr().out == ""


def test_main_passes_through_when_rtk_cannot_start(
    hook: ModuleType,
    rtk_on_path: StubFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    log = rtk_on_path(rewrite_stdout="rtk x", break_after_version=True)
    _stdin_with(monkeypatch, {"tool_input": {"command": "x"}})

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert _calls(log) == ["--version"]
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "tool_input",
    ["scalar", {"command": 42}, {"command": ""}],
    ids=["non-dict-tool-input", "non-string-command", "empty-command"],
)
def test_main_skips_rewrite_for_unusable_command(
    hook: ModuleType,
    rtk_on_path: StubFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tool_input: object,
) -> None:
    # Arrange
    log = rtk_on_path(rewrite_stdout="rtk x")
    _stdin_with(monkeypatch, {"tool_input": tool_input})

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert _calls(log) == ["--version"]
    assert capsys.readouterr().out == ""


def test_main_rewrites_through_the_rtk_binary(
    hook: ModuleType,
    rtk_on_path: StubFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    rtk_on_path(rewrite_stdout="rtk git status")
    _stdin_with(monkeypatch, {"tool_input": {"command": "git status", "timeout": 5}})

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    output = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert output["permissionDecision"] == "allow"
    assert output["updatedInput"] == {"command": "rtk git status", "timeout": 5}
