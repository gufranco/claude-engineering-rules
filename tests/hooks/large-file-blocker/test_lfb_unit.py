"""Direct-import unit tests for `hooks/large-file-blocker.py`.

Subprocess-based tests in `test_large_file_blocker.py` cover end-to-end
behavior; these import the hook module directly so coverage records line
hits regardless of the pytest-cov subprocess stitch.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

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
    return module


def _stdin_with(payload: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


def test_read_command_returns_empty_on_malformed_json(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    # Act
    result = hook._read_command()
    # Assert
    assert result == ""


def test_read_command_returns_empty_on_non_dict_root(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(sys, "stdin", io.StringIO("[1, 2, 3]"))
    # Act
    result = hook._read_command()
    # Assert
    assert result == ""


def test_read_command_returns_empty_on_non_dict_tool_input(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    _stdin_with({"tool_input": "scalar"}, monkeypatch)
    # Act
    result = hook._read_command()
    # Assert
    assert result == ""


def test_read_command_returns_string(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)
    # Act
    result = hook._read_command()
    # Assert
    assert result == "git commit -m x"


def test_read_command_returns_empty_when_command_non_string(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": 42}}, monkeypatch)
    # Act
    result = hook._read_command()
    # Assert
    assert result == ""


def test_file_size_kb_handles_missing_file(hook, tmp_path: Path) -> None:
    # Arrange
    missing = tmp_path / "nope"
    # Act
    result = hook._file_size_kb(missing)
    # Assert
    assert result is None


def test_file_size_kb_rounds_up(hook, tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "tiny"
    target.write_bytes(b"x")
    # Act
    result = hook._file_size_kb(target)
    # Assert
    assert result == 1


def test_staged_files_returns_empty_outside_git_repo(
    hook, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.chdir(tmp_path)
    # Act
    result = hook._staged_files()
    # Assert
    assert result == []


def test_audit_noop_when_record_unavailable(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(hook, "_audit_record", None)
    # Act
    hook._audit("git commit -m x")
    # Assert: no exception, no record call


def test_audit_swallows_record_exception(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    def boom(**_kwargs: object) -> None:
        raise RuntimeError("audit explosion")

    monkeypatch.setattr(hook, "_audit_record", boom)
    # Act
    hook._audit("git commit -m x")
    # Assert: no exception propagated


def test_main_env_disable_short_circuits(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("LARGE_FILE_DISABLE", "1")
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


def test_main_returns_zero_on_non_commit_command(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": "ls"}}, monkeypatch)
    # Act
    result = hook.main()
    # Assert
    assert result == 0


def test_main_allows_when_no_offenders(hook, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)
    monkeypatch.setattr(hook, "_staged_files", lambda: [])
    # Act
    result = hook.main()
    # Assert
    assert result == 0


def test_staged_files_returns_empty_when_git_errors(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    def boom(*_args: object, **_kwargs: object) -> object:
        raise OSError("simulated")

    monkeypatch.setattr(hook.subprocess, "run", boom)
    # Act
    result = hook._staged_files()
    # Assert
    assert result == []


def test_staged_files_returns_empty_on_non_zero_returncode(
    hook, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    from types import SimpleNamespace

    monkeypatch.setattr(
        hook.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(stdout="", returncode=128),
    )
    # Act
    result = hook._staged_files()
    # Assert
    assert result == []


def test_main_skips_non_file_paths_and_small_files(
    hook, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    small = tmp_path / "small.txt"
    small.write_bytes(b"x" * 1024)
    missing = str(tmp_path / "ghost.bin")
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)
    monkeypatch.setattr(hook, "_staged_files", lambda: [missing, str(small)])
    # Act
    result = hook.main()
    # Assert
    assert result == 0


def test_main_blocks_when_offender_present(
    hook,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    big = tmp_path / "huge.bin"
    big.write_bytes(b"x" * (6 * 1024 * 1024))
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)
    monkeypatch.setattr(hook, "_staged_files", lambda: [str(big)])
    # Act
    result = hook.main()
    # Assert
    captured = capsys.readouterr()
    assert result == 2
    assert "BLOCKED" in captured.err
    assert "huge.bin" in captured.err
