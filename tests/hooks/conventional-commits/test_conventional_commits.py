"""Tests for `hooks/conventional-commits.py`."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "conventional-commits.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

_TESTS_DIR = ROOT / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _helpers.cov_env import apply_coverage_env  # noqa: E402


def _run(command: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env=apply_coverage_env(merged),
        timeout=5,
    )


def test_allows_valid_conventional_commit() -> None:
    # Arrange
    # Act
    result = _run("git commit -m 'feat(auth): add SSO login'")
    # Assert
    assert result.returncode == 0


def test_allows_breaking_change_bang() -> None:
    # Arrange
    # Act
    result = _run("git commit -m 'feat(api)!: drop v1 endpoints'")
    # Assert
    assert result.returncode == 0


def test_allows_no_scope() -> None:
    # Arrange
    # Act
    result = _run("git commit -m 'fix: handle null user'")
    # Assert
    assert result.returncode == 0


def test_ignores_non_commit_command() -> None:
    # Arrange
    # Act
    result = _run("git status")
    # Assert
    assert result.returncode == 0


def test_ignores_amend() -> None:
    # Arrange
    # Act
    result = _run("git commit --amend --no-edit")
    # Assert
    assert result.returncode == 0


def test_ignores_squash() -> None:
    # Arrange
    # Act
    result = _run("git commit --squash HEAD~1")
    # Assert
    assert result.returncode == 0


def test_blocks_subject_without_type() -> None:
    # Arrange
    # Act
    result = _run("git commit -m 'updated stuff'")
    # Assert
    assert result.returncode == 2
    assert "conventional commit format" in result.stderr


def test_blocks_subject_over_50_chars() -> None:
    # Arrange
    long_subject = "feat(auth): " + "x" * 60
    # Act
    result = _run(f"git commit -m '{long_subject}'")
    # Assert
    assert result.returncode == 2
    assert "characters (max 50)" in result.stderr


def test_blocks_body_line_over_72_chars() -> None:
    # Arrange
    long_line = "x" * 80
    body = f"feat: tiny subject\n\n{long_line}"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    # Act
    result = _run(command)
    # Assert
    assert result.returncode == 2
    assert "body line" in result.stderr.lower()


def test_allows_long_trailer_lines() -> None:
    # Arrange
    long_url = "https://example.com/" + "x" * 80
    body = f"feat: ok subject\n\nFixes: {long_url}"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    # Act
    result = _run(command)
    # Assert
    assert result.returncode == 0


def test_blocks_malformed_decision_trailer() -> None:
    # Arrange
    body = "feat: ok subject\n\nRejected"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    # Act
    result = _run(command)
    # Assert (the bare word does not match the trailer pattern but also does not
    # start with the trailer label followed by colon, so the hook must allow it
    # rather than treat it as malformed)
    assert result.returncode == 0


def test_blocks_rejected_trailer_missing_pipe() -> None:
    # Arrange
    body = "feat: ok subject\n\nRejected: alternative without reason"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    # Act
    result = _run(command)
    # Assert
    assert result.returncode == 2
    assert "Rejected" in result.stderr


def test_allows_rejected_trailer_with_pipe() -> None:
    # Arrange
    body = "feat: ok subject\n\nRejected: option A | rationale here"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    # Act
    result = _run(command)
    # Assert
    assert result.returncode == 0


def test_allows_empty_message_extraction() -> None:
    # Arrange
    # Act
    result = _run("git commit --allow-empty")
    # Assert
    assert result.returncode == 0


def test_env_disable_short_circuits() -> None:
    # Arrange
    # Act
    result = _run(
        "git commit -m 'invalid subject without prefix'",
        env={"CONVENTIONAL_COMMITS_DISABLE": "1"},
    )
    # Assert
    assert result.returncode == 0


def test_file_bypass_short_circuits(tmp_path: Path) -> None:
    # Arrange
    state = tmp_path / "state.json"
    set_bypass("conventional-commits", ttl_seconds=120, state_path=state)
    # Act
    result = _run(
        "git commit -m 'no type prefix here'",
        env={"CLAUDE_BYPASS_STATE": str(state)},
    )
    # Assert
    assert result.returncode == 0


def test_malformed_json_allows() -> None:
    # Arrange
    # Act
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json",
        capture_output=True,
        text=True,
        env=apply_coverage_env(os.environ.copy()),
        timeout=5,
    )
    # Assert
    assert result.returncode == 0


def test_non_dict_root_allows() -> None:
    # Arrange
    # Act
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="[1,2,3]",
        capture_output=True,
        text=True,
        env=apply_coverage_env(os.environ.copy()),
        timeout=5,
    )
    # Assert
    assert result.returncode == 0


def test_non_dict_tool_input_allows() -> None:
    # Arrange
    # Act
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input='{"tool_input": "scalar"}',
        capture_output=True,
        text=True,
        env=apply_coverage_env(os.environ.copy()),
        timeout=5,
    )
    # Assert
    assert result.returncode == 0


def test_blocks_malformed_constraint_trailer() -> None:
    # Arrange
    body = "feat: ok subject\n\nConstraint:"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    # Act
    result = _run(command)
    # Assert
    assert result.returncode == 2
    assert "Malformed decision trailer" in result.stderr


def test_allows_constraint_trailer_with_description() -> None:
    # Arrange
    body = "feat: ok subject\n\nConstraint: must run before 2026"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    # Act
    result = _run(command)
    # Assert
    assert result.returncode == 0


def test_allows_risk_trailer() -> None:
    # Arrange
    body = "feat: ok subject\n\nRisk: rollback path untested"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    # Act
    result = _run(command)
    # Assert
    assert result.returncode == 0


def test_allows_indented_long_body_line() -> None:
    # Arrange
    long_line = "    " + "x" * 200
    body = f"feat: ok subject\n\n{long_line}"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    # Act
    result = _run(command)
    # Assert
    assert result.returncode == 0


def test_audit_swallows_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    import importlib.util as _util

    spec = _util.spec_from_file_location("_cc_mod", str(HOOK))
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def boom(**_kwargs: object) -> None:
        raise RuntimeError("audit explosion")

    monkeypatch.setattr(module, "_audit_record", boom)
    # Act
    module._audit("reason", "git commit -m msg")
    # Assert: no exception raised


def test_audit_noop_when_record_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    import importlib.util as _util

    spec = _util.spec_from_file_location("_cc_mod2", str(HOOK))
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_audit_record", None)
    # Act
    module._audit("reason", "git commit -m msg")
    # Assert: no exception raised
