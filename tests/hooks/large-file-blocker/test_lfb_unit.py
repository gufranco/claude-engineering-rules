from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from pathlib import Path

import pytest
from _helpers.audit_log_support import _read_records, isolate_audit_log

ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = ROOT / "hooks" / "large-file-blocker.py"
sys.path.insert(0, str(ROOT / "hooks"))


@pytest.fixture()
def hook(monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location("_lfb_mod", str(HOOK_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.delenv("LARGE_FILE_DISABLE", raising=False)
    monkeypatch.delenv("CLAUDE_BYPASS_STATE", raising=False)
    monkeypatch.setattr("_lib.bypass.STATE_PATH", Path(os.devnull))
    return module


def _stdin_with(payload: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


def test_read_command_blocks_on_malformed_json(
    hook, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    # Arrange
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))

    # Act
    with pytest.raises(SystemExit) as exit_info:
        hook._read_command()

    # Assert
    assert exit_info.value.code == 2
    assert "large-file-blocker could not read its input" in capsys.readouterr().err


def test_read_command_blocks_on_non_dict_root(
    hook, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    # Arrange
    monkeypatch.setattr(sys, "stdin", io.StringIO("[1, 2, 3]"))

    # Act
    with pytest.raises(SystemExit) as exit_info:
        hook._read_command()

    # Assert
    assert exit_info.value.code == 2
    assert "large-file-blocker could not read its input" in capsys.readouterr().err


def test_read_command_blocks_on_non_dict_tool_input(
    hook, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    # Arrange
    _stdin_with({"tool_input": "scalar"}, monkeypatch)

    # Act
    with pytest.raises(SystemExit) as exit_info:
        hook._read_command()

    # Assert
    assert exit_info.value.code == 2
    assert "large-file-blocker could not read its input" in capsys.readouterr().err


def test_read_command_returns_string(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    _stdin_with(
        {"tool_input": {"command": "git commit -m x"}, "cwd": "/repo"}, monkeypatch
    )

    # Act
    result = hook._read_command()

    # Assert
    assert result == ("git commit -m x", "/repo")


def test_read_command_blocks_when_command_non_string(
    hook, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": 42}}, monkeypatch)

    # Act
    with pytest.raises(SystemExit) as exit_info:
        hook._read_command()

    # Assert
    assert exit_info.value.code == 2
    assert "large-file-blocker could not read its input" in capsys.readouterr().err


def test_audit_records_the_block(
    hook, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    log_path = isolate_audit_log(monkeypatch, tmp_path)

    # Act
    hook._audit("git commit -m x")

    # Assert
    record = _read_records(log_path)[-1]
    assert (record["hook"], record["decision"]) == ("large-file-blocker", "block")
