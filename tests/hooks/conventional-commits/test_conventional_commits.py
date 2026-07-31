"""Tests for `hooks/conventional-commits.py`."""

from __future__ import annotations

import json
import os
import subprocess
import sys
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
    result = _run("git commit -m 'feat(auth): add SSO login'")
    assert result.returncode == 0


def test_long_subject_shows_cut_marker_and_overflow() -> None:
    subject = "refactor: rewrite the nine remaining shell hooks into python modules"
    result = _run(f"git commit -m '{subject}'")

    assert result.returncode == 2
    assert f"Drop {len(subject) - 50} character(s)" in result.stderr
    assert f"{subject[:50]}|{subject[50:]}" in result.stderr


def test_long_subject_suggests_dropping_scope_when_that_fits() -> None:
    subject = "feat(authentication): add single sign on with Google"
    result = _run(f"git commit -m '{subject}'")

    assert result.returncode == 2
    assert "Dropping the scope fits: feat: add single sign on with Google" in (
        result.stderr
    )


def test_long_subject_omits_scope_hint_when_it_does_not_fit() -> None:
    subject = "feat(hooks): allow tool directives and ban every prose comment"
    result = _run(f"git commit -m '{subject}'")

    assert result.returncode == 2
    assert "Dropping the scope fits" not in result.stderr


def test_long_subject_without_scope_omits_scope_hint() -> None:
    subject = "refactor: rewrite the nine remaining shell hooks into python modules"
    result = _run(f"git commit -m '{subject}'")

    assert result.returncode == 2
    assert "Dropping the scope fits" not in result.stderr


def test_allows_breaking_change_bang() -> None:
    result = _run("git commit -m 'feat(api)!: drop v1 endpoints'")
    assert result.returncode == 0


def test_allows_no_scope() -> None:
    result = _run("git commit -m 'fix: handle null user'")
    assert result.returncode == 0


def test_ignores_non_commit_command() -> None:
    result = _run("git status")
    assert result.returncode == 0


def test_ignores_amend() -> None:
    result = _run("git commit --amend --no-edit")
    assert result.returncode == 0


def test_ignores_squash() -> None:
    result = _run("git commit --squash HEAD~1")
    assert result.returncode == 0


def test_blocks_subject_without_type() -> None:
    result = _run("git commit -m 'updated stuff'")
    assert result.returncode == 2
    assert "conventional commit format" in result.stderr


def test_blocks_subject_over_50_chars() -> None:
    long_subject = "feat(auth): " + "x" * 60
    result = _run(f"git commit -m '{long_subject}'")
    assert result.returncode == 2
    assert "characters (max 50)" in result.stderr


def test_blocks_body_line_over_72_chars() -> None:
    long_line = "x" * 80
    body = f"feat: tiny subject\n\n{long_line}"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    result = _run(command)
    assert result.returncode == 2
    assert "body line" in result.stderr.lower()


def test_allows_long_trailer_lines() -> None:
    long_url = "https://example.com/" + "x" * 80
    body = f"feat: ok subject\n\nFixes: {long_url}"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    result = _run(command)
    assert result.returncode == 0


def test_blocks_malformed_decision_trailer() -> None:
    body = "feat: ok subject\n\nRejected"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    result = _run(command)
    assert result.returncode == 0


def test_blocks_rejected_trailer_missing_pipe() -> None:
    body = "feat: ok subject\n\nRejected: alternative without reason"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    result = _run(command)
    assert result.returncode == 2
    assert "Rejected" in result.stderr


def test_allows_rejected_trailer_with_pipe() -> None:
    body = "feat: ok subject\n\nRejected: option A | rationale here"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    result = _run(command)
    assert result.returncode == 0


def test_allows_empty_message_extraction() -> None:
    result = _run("git commit --allow-empty")
    assert result.returncode == 0


def test_env_disable_short_circuits() -> None:
    result = _run(
        "git commit -m 'invalid subject without prefix'",
        env={"CONVENTIONAL_COMMITS_DISABLE": "1"},
    )
    assert result.returncode == 0


def test_file_bypass_short_circuits(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    set_bypass("conventional-commits", ttl_seconds=120, state_path=state)
    result = _run(
        "git commit -m 'no type prefix here'",
        env={"CLAUDE_BYPASS_STATE": str(state)},
    )
    assert result.returncode == 0


def test_malformed_json_allows() -> None:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json",
        capture_output=True,
        text=True,
        env=apply_coverage_env(os.environ.copy()),
        timeout=5,
    )
    assert result.returncode == 0


def test_non_dict_root_allows() -> None:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="[1,2,3]",
        capture_output=True,
        text=True,
        env=apply_coverage_env(os.environ.copy()),
        timeout=5,
    )
    assert result.returncode == 0


def test_non_dict_tool_input_allows() -> None:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input='{"tool_input": "scalar"}',
        capture_output=True,
        text=True,
        env=apply_coverage_env(os.environ.copy()),
        timeout=5,
    )
    assert result.returncode == 0


def test_blocks_malformed_constraint_trailer() -> None:
    body = "feat: ok subject\n\nConstraint:"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    result = _run(command)
    assert result.returncode == 2
    assert "Malformed decision trailer" in result.stderr


def test_allows_constraint_trailer_with_description() -> None:
    body = "feat: ok subject\n\nConstraint: must run before 2026"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    result = _run(command)
    assert result.returncode == 0


def test_allows_risk_trailer() -> None:
    body = "feat: ok subject\n\nRisk: rollback path untested"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    result = _run(command)
    assert result.returncode == 0


def test_allows_indented_long_body_line() -> None:
    long_line = "    " + "x" * 200
    body = f"feat: ok subject\n\n{long_line}"
    command = f"git commit -m $(cat <<'PAYLOAD'\n{body}\nPAYLOAD\n)"
    result = _run(command)
    assert result.returncode == 0


def test_audit_swallows_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util as _util

    spec = _util.spec_from_file_location("_cc_mod", str(HOOK))
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def boom(**_kwargs: object) -> None:
        raise RuntimeError("audit explosion")

    monkeypatch.setattr(module, "_audit_record", boom)
    module._audit("reason", "git commit -m msg")


def test_audit_noop_when_record_none(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util as _util

    spec = _util.spec_from_file_location("_cc_mod2", str(HOOK))
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_audit_record", None)
    module._audit("reason", "git commit -m msg")
