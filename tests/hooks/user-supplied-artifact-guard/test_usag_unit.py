from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from _usag_support import BYPASS_TTL_S, HOOK_NAME, _stage, _stdin_with

from _lib.bypass_writer import set_bypass
from _lib.output import validate_block_message


def test_audit_noop_when_record_unavailable(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    monkeypatch.setattr(hook, "_audit_record", None)

    # Act
    hook._audit("git commit -m x", [("game.gba", "reason")])

    # Assert
    assert capsys.readouterr().err == ""


def test_main_env_disable_allows_a_staged_artifact(
    hook: ModuleType,
    staged_rom: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    monkeypatch.setenv("USER_SUPPLIED_ARTIFACT_DISABLE", "1")
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert capsys.readouterr().err == ""


def test_main_profile_gate_allows_a_staged_artifact(
    hook: ModuleType,
    staged_rom: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    monkeypatch.setenv("CLAUDE_DISABLED_HOOKS", HOOK_NAME)
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert capsys.readouterr().err == ""


def test_main_file_bypass_allows_a_staged_artifact(
    hook: ModuleType,
    staged_rom: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    state = tmp_path / "bypass-state.json"
    set_bypass(HOOK_NAME, ttl_seconds=BYPASS_TTL_S, state_path=state)
    monkeypatch.setattr("_lib.bypass.STATE_PATH", state)
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert capsys.readouterr().err == ""


def test_main_ignores_an_unrelated_command_with_an_artifact_staged(
    hook: ModuleType,
    staged_rom: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": "ls -la"}}, monkeypatch)

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert capsys.readouterr().err == ""


def test_main_allows_a_commit_when_nothing_is_staged(
    hook: ModuleType,
    git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert capsys.readouterr().err == ""


def test_main_allows_when_no_candidate_is_an_artifact(
    hook: ModuleType,
    git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    _stage(git_repo, "notes.md", b"# notes\n")
    _stdin_with(
        {"tool_input": {"command": "git add ghost.bin && git commit -m x"}}, monkeypatch
    )

    # Act
    result = hook.main()

    # Assert
    assert result == 0
    assert capsys.readouterr().err == ""


def test_main_deduplicates_repeated_candidates(
    hook: ModuleType,
    staged_rom: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    _stdin_with(
        {"tool_input": {"command": "git add game.gba && git commit -m x"}}, monkeypatch
    )

    # Act
    result = hook.main()

    # Assert
    stderr = capsys.readouterr().err
    assert result == 2
    assert stderr.count("game.gba:") == 1
    assert "1 user-supplied artifact(s)" in stderr


def test_main_blocks_and_renders_canonical_message(
    hook: ModuleType,
    git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    faker,
) -> None:
    # Arrange
    _stage(git_repo, "game.z64", faker.binary(length=64))
    _stdin_with({"tool_input": {"command": "git commit -m x"}}, monkeypatch)

    # Act
    result = hook.main()

    # Assert
    stderr = capsys.readouterr().err
    assert result == 2
    assert "game.z64: .z64 is a user-supplied artifact extension" in stderr
    assert validate_block_message(stderr) == []
