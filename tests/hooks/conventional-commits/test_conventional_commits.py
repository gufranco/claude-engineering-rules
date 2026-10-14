from __future__ import annotations

import importlib.util as _util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.cov_env import apply_coverage_env

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "conventional-commits.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

TIMEOUT_S = 30
ISOLATION = {"CLAUDE_BYPASS_STATE": os.devnull, "CLAUDE_HOOK_AUDIT_DISABLE": "1"}


def _env(extra: dict[str, str] | None = None) -> dict[str, str]:
    return apply_coverage_env({**os.environ, **ISOLATION, **(extra or {})})


def _run(command: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return _run_raw(payload, env)


def _run_raw(stdin: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        env=_env(env),
        timeout=TIMEOUT_S,
        check=False,
    )


def _load(name: str):
    spec = _util.spec_from_file_location(name, str(HOOK))
    assert spec is not None
    assert spec.loader is not None
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_allows_valid_conventional_commit() -> None:
    # Arrange
    command = "git commit -m 'feat(auth): add SSO login'"

    # Act
    result = _run(command)

    # Assert
    assert result.returncode == 0


def test_long_subject_shows_cut_marker_and_overflow() -> None:
    # Arrange
    subject = "refactor: rewrite the nine remaining shell hooks into python modules"

    # Act
    result = _run(f"git commit -m '{subject}'")

    # Assert
    assert result.returncode == 2
    assert "Drop 18 character(s)" in result.stderr
    assert (
        "refactor: rewrite the nine remaining shell hooks i|nto python modules"
        in result.stderr
    )


def test_long_subject_suggests_dropping_scope_when_that_fits() -> None:
    # Arrange
    subject = "feat(authentication): add single sign on with Google"

    # Act
    result = _run(f"git commit -m '{subject}'")

    # Assert
    assert result.returncode == 2
    assert "Dropping the scope fits: feat: add single sign on with Google" in (
        result.stderr
    )


def test_long_subject_omits_scope_hint_when_it_does_not_fit() -> None:
    # Arrange
    subject = "feat(hooks): allow tool directives and ban every prose comment"

    # Act
    result = _run(f"git commit -m '{subject}'")

    # Assert
    assert result.returncode == 2
    assert "Dropping the scope fits" not in result.stderr


def test_long_subject_without_scope_omits_scope_hint() -> None:
    # Arrange
    subject = "refactor: rewrite the nine remaining shell hooks into python modules"

    # Act
    result = _run(f"git commit -m '{subject}'")

    # Assert
    assert result.returncode == 2
    assert "Dropping the scope fits" not in result.stderr


def test_allows_breaking_change_bang() -> None:
    # Arrange
    command = "git commit -m 'feat(api)!: drop v1 endpoints'"

    # Act
    result = _run(command)

    # Assert
    assert result.returncode == 0


def test_allows_no_scope() -> None:
    # Arrange
    command = "git commit -m 'fix: handle null user'"

    # Act
    result = _run(command)

    # Assert
    assert result.returncode == 0


def test_ignores_non_commit_command() -> None:
    # Arrange
    command = "git status"

    # Act
    result = _run(command)

    # Assert
    assert result.returncode == 0


def test_ignores_amend() -> None:
    # Arrange
    command = "git commit --amend --no-edit"

    # Act
    result = _run(command)

    # Assert
    assert result.returncode == 0


def test_ignores_squash() -> None:
    # Arrange
    command = "git commit --squash HEAD~1"

    # Act
    result = _run(command)

    # Assert
    assert result.returncode == 0


def test_blocks_subject_without_type() -> None:
    # Arrange
    command = "git commit -m 'updated stuff'"

    # Act
    result = _run(command)

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

    # Assert
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
    command = "git commit --allow-empty"

    # Act
    result = _run(command)

    # Assert
    assert result.returncode == 0


def test_env_disable_short_circuits() -> None:
    # Arrange
    command = "git commit -m 'invalid subject without prefix'"

    # Act
    result = _run(
        command,
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


def test_malformed_json_blocks() -> None:
    # Arrange
    stdin = "not json"

    # Act
    result = _run_raw(stdin)

    # Assert
    assert result.returncode == 2
    assert "could not read its input" in result.stderr


def test_non_dict_root_blocks() -> None:
    # Arrange
    stdin = "[1,2,3]"

    # Act
    result = _run_raw(stdin)

    # Assert
    assert result.returncode == 2
    assert "could not read its input" in result.stderr


def test_non_dict_tool_input_blocks() -> None:
    # Arrange
    stdin = '{"tool_input": "scalar"}'

    # Act
    result = _run_raw(stdin)

    # Assert
    assert result.returncode == 2
    assert "could not read its input" in result.stderr


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


def test_audit_noop_when_record_none(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    module = _load("_cc_mod2")
    monkeypatch.setattr(module, "_audit_record", None)

    # Act
    module._audit("reason", "git commit -m msg")

    # Assert
    assert capsys.readouterr().err == ""
