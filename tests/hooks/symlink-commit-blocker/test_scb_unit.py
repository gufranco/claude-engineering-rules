from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = ROOT / "hooks" / "symlink-commit-blocker.py"
sys.path.insert(0, str(ROOT / "hooks"))


@pytest.fixture()
def hook(monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location("_scb_mod", str(HOOK_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.delenv("SYMLINK_COMMIT_DISABLE", raising=False)
    monkeypatch.delenv("CLAUDE_BYPASS_STATE", raising=False)
    monkeypatch.setattr("_lib.bypass.STATE_PATH", Path(os.devnull))
    return module


def test_read_command_returns_command_and_cwd(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    payload = {"tool_input": {"command": "git commit -m x"}, "cwd": "/repo"}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    # Act
    result = hook._read_command()

    # Assert
    assert result == ("git commit -m x", "/repo")


def test_read_command_defaults_a_missing_cwd_to_empty(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    payload = {"tool_input": {"command": "git commit -m x"}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    # Act
    result = hook._read_command()

    # Assert
    assert result == ("git commit -m x", "")


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
    assert "symlink-commit-blocker could not read its input" in capsys.readouterr().err


def test_git_returns_none_when_git_cannot_start(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    def missing(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", missing)

    # Act
    result = hook._git("/repo", "status")

    # Assert
    assert result is None


def test_staged_links_reads_only_the_new_mode(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    raw = (
        ":000000 120000 0000000 abc1234 A\0link\0"
        ":120000 100644 abc1234 def5678 T\0was-link\0"
    )
    monkeypatch.setattr(hook, "_git", lambda *_args: raw)

    # Act
    result = hook._staged_links("/repo")

    # Assert
    assert result == {"link"}


def test_audit_records_the_block(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    calls: list[dict[str, str]] = []
    monkeypatch.setattr(hook, "_audit_record", lambda **kwargs: calls.append(kwargs))

    # Act
    hook._audit("git commit -m x")

    # Assert
    assert calls == [
        {
            "hook": "symlink-commit-blocker",
            "decision": "block",
            "decision_class": "block",
            "reason": "commit would record a symbolic link",
            "tool": "Bash",
            "command_excerpt": "git commit -m x",
        }
    ]


def test_audit_record_is_none_when_the_audit_log_cannot_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setitem(sys.modules, "_lib.audit_log", None)
    spec = importlib.util.spec_from_file_location("_scb_no_audit", str(HOOK_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None

    # Act
    spec.loader.exec_module(module)

    # Assert
    assert module._audit_record is None


def test_audit_noop_when_record_unavailable(
    hook, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    # Arrange
    monkeypatch.setattr(hook, "_audit_record", None)

    # Act
    hook._audit("git commit -m x")

    # Assert
    assert capsys.readouterr().err == ""
