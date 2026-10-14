from __future__ import annotations

import io
import sys
from pathlib import Path
from types import ModuleType

import pytest
from _usag_support import HOOK_NAME, _stage, _stdin_with


def test_read_command_blocks_on_malformed_json(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))

    # Act
    with pytest.raises(SystemExit) as exit_info:
        hook._read_command()

    # Assert
    assert exit_info.value.code == 2
    assert f"{HOOK_NAME} could not read its input" in capsys.readouterr().err


def test_read_command_blocks_on_non_dict_root(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    monkeypatch.setattr(sys, "stdin", io.StringIO("[1, 2, 3]"))

    # Act
    with pytest.raises(SystemExit) as exit_info:
        hook._read_command()

    # Assert
    assert exit_info.value.code == 2
    assert f"{HOOK_NAME} could not read its input" in capsys.readouterr().err


def test_read_command_blocks_on_non_dict_tool_input(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    _stdin_with({"tool_input": "scalar"}, monkeypatch)

    # Act
    with pytest.raises(SystemExit) as exit_info:
        hook._read_command()

    # Assert
    assert exit_info.value.code == 2
    assert f"{HOOK_NAME} could not read its input" in capsys.readouterr().err


def test_read_command_blocks_when_command_non_string(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": 42}}, monkeypatch)

    # Act
    with pytest.raises(SystemExit) as exit_info:
        hook._read_command()

    # Assert
    assert exit_info.value.code == 2
    assert "tool_input.command is not a string" in capsys.readouterr().err


def test_read_command_returns_string(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)

    # Act
    result = hook._read_command()

    # Assert
    assert result == "git commit -m x"


def test_git_returns_empty_when_binary_missing(
    hook: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    # Act
    result = hook._git(["status"])

    # Assert
    assert result == []


def test_git_returns_empty_on_non_zero_returncode(
    hook: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.chdir(tmp_path)

    # Act
    result = hook._git(["diff", "--cached", "--name-only"])

    # Assert
    assert result == []


def test_staged_files_returns_empty_outside_git_repo(
    hook, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.chdir(tmp_path)

    # Act
    result = hook._staged_files()

    # Assert
    assert result == []


def test_git_returns_output_lines_inside_a_repo(
    hook: ModuleType, git_repo: Path
) -> None:
    # Arrange
    _stage(git_repo, "b.txt", b"b")
    _stage(git_repo, "a.txt", b"a")

    # Act
    result = hook._git(["diff", "--cached", "--name-only"])

    # Assert
    assert result == ["a.txt", "b.txt"]
