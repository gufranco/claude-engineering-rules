from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from _helpers.cov_env import apply_coverage_env


ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "rtk-rewrite.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

TIMEOUT_S = 30


def _make_rtk_stub(
    tmp_path: Path, *, version: str, rewrite_exit: int, rewrite_stdout: str = ""
) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "rtk"
    body = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        import sys
        argv = sys.argv[1:]
        if argv and argv[0] == "--version":
            sys.stdout.write("rtk {version}\\n")
            sys.exit(0)
        if argv and argv[0] == "rewrite":
            sys.stdout.write({rewrite_stdout!r})
            sys.exit({rewrite_exit})
        sys.exit(0)
        """
    )
    stub.write_text(body, encoding="utf-8")
    stub.chmod(0o755)
    return bin_dir


def _run(
    payload: dict, *, bin_dir: Path | None = None, env: dict | None = None
) -> subprocess.CompletedProcess[str]:
    merged = {
        **os.environ,
        "CLAUDE_BYPASS_STATE": os.devnull,
        "CLAUDE_HOOK_AUDIT_DISABLE": "1",
    }
    if bin_dir is not None:
        merged["PATH"] = f"{bin_dir}:{merged.get('PATH', '')}"
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=apply_coverage_env(merged),
        timeout=TIMEOUT_S,
        check=False,
    )


def test_missing_rtk_warns_and_exits_zero(tmp_path: Path) -> None:
    # Arrange
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    payload = {"tool_input": {"command": "ls"}}

    # Act
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=apply_coverage_env(
            {
                "PATH": str(empty),
                "CLAUDE_BYPASS_STATE": os.devnull,
                "CLAUDE_HOOK_AUDIT_DISABLE": "1",
            }
        ),
        timeout=TIMEOUT_S,
        check=False,
    )

    # Assert
    assert result.returncode == 0
    assert "rtk is not installed or not in PATH" in result.stderr
    assert result.stdout == ""


def test_old_rtk_warns_and_exits_zero(tmp_path: Path) -> None:
    # Arrange
    bin_dir = _make_rtk_stub(tmp_path, version="0.20.0", rewrite_exit=1)
    payload = {"tool_input": {"command": "ls"}}

    # Act
    result = _run(payload, bin_dir=bin_dir)

    # Assert
    assert result.returncode == 0
    assert "too old" in result.stderr


def test_rewrite_allow_emits_updated_input(tmp_path: Path) -> None:
    # Arrange
    bin_dir = _make_rtk_stub(
        tmp_path, version="0.25.0", rewrite_exit=0, rewrite_stdout="rtk git status"
    )
    payload = {"tool_input": {"command": "git status"}}

    # Act
    result = _run(payload, bin_dir=bin_dir)

    # Assert
    assert result.returncode == 0
    body = json.loads(result.stdout)
    output = body["hookSpecificOutput"]
    assert output["permissionDecision"] == "allow"
    assert output["updatedInput"]["command"] == "rtk git status"


def test_rewrite_same_command_is_no_op(tmp_path: Path) -> None:
    # Arrange
    bin_dir = _make_rtk_stub(
        tmp_path, version="0.25.0", rewrite_exit=0, rewrite_stdout="git status"
    )
    payload = {"tool_input": {"command": "git status"}}

    # Act
    result = _run(payload, bin_dir=bin_dir)

    # Assert
    assert result.returncode == 0
    assert result.stdout == ""


def test_no_equivalent_passes_through(tmp_path: Path) -> None:
    # Arrange
    bin_dir = _make_rtk_stub(tmp_path, version="0.25.0", rewrite_exit=1)
    payload = {"tool_input": {"command": "do-nothing"}}

    # Act
    result = _run(payload, bin_dir=bin_dir)

    # Assert
    assert result.returncode == 0
    assert result.stdout == ""


def test_deny_rule_passes_through(tmp_path: Path) -> None:
    # Arrange
    bin_dir = _make_rtk_stub(tmp_path, version="0.25.0", rewrite_exit=2)
    payload = {"tool_input": {"command": "rm -rf /"}}

    # Act
    result = _run(payload, bin_dir=bin_dir)

    # Assert
    assert result.returncode == 0
    assert result.stdout == ""


def test_ask_rule_emits_without_permission_decision(tmp_path: Path) -> None:
    # Arrange
    bin_dir = _make_rtk_stub(
        tmp_path, version="0.25.0", rewrite_exit=3, rewrite_stdout="rtk ask cmd"
    )
    payload = {"tool_input": {"command": "ask cmd"}}

    # Act
    result = _run(payload, bin_dir=bin_dir)

    # Assert
    assert result.returncode == 0
    body = json.loads(result.stdout)
    output = body["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert output["updatedInput"]["command"] == "rtk ask cmd"


def test_empty_command_passes_through(tmp_path: Path) -> None:
    # Arrange
    bin_dir = _make_rtk_stub(
        tmp_path, version="0.25.0", rewrite_exit=0, rewrite_stdout="x"
    )
    payload = {"tool_input": {"command": ""}}

    # Act
    result = _run(payload, bin_dir=bin_dir)

    # Assert
    assert result.returncode == 0
    assert result.stdout == ""


def test_env_disable_short_circuits(tmp_path: Path) -> None:
    # Arrange
    bin_dir = _make_rtk_stub(
        tmp_path, version="0.25.0", rewrite_exit=0, rewrite_stdout="rtk x"
    )
    payload = {"tool_input": {"command": "x"}}

    # Act
    result = _run(payload, bin_dir=bin_dir, env={"RTK_REWRITE_DISABLE": "1"})

    # Assert
    assert result.returncode == 0
    assert result.stdout == ""


def test_file_bypass_short_circuits(tmp_path: Path) -> None:
    # Arrange
    bin_dir = _make_rtk_stub(
        tmp_path, version="0.25.0", rewrite_exit=0, rewrite_stdout="rtk x"
    )
    state = tmp_path / "state.json"
    set_bypass("rtk-rewrite", ttl_seconds=120, state_path=state)
    payload = {"tool_input": {"command": "x"}}

    # Act
    result = _run(payload, bin_dir=bin_dir, env={"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    assert result.returncode == 0
    assert result.stdout == ""


def test_malformed_json_passes_through_without_rewrite(tmp_path: Path) -> None:
    # Arrange
    bin_dir = _make_rtk_stub(
        tmp_path, version="0.25.0", rewrite_exit=0, rewrite_stdout="rtk x"
    )

    # Act
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json",
        capture_output=True,
        text=True,
        env=apply_coverage_env(
            {
                **os.environ,
                "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
                "CLAUDE_BYPASS_STATE": os.devnull,
                "CLAUDE_HOOK_AUDIT_DISABLE": "1",
            }
        ),
        timeout=TIMEOUT_S,
        check=False,
    )

    # Assert
    assert result.returncode == 0
    assert result.stdout == ""
