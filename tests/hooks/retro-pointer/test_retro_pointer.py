from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / "retro-pointer.py"


SESSION_KEYS = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "SESSION_ID")


def _make_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    inherited = {k: v for k, v in os.environ.items() if k not in SESSION_KEYS}
    return {**inherited, "CLAUDE_HOOK_AUDIT_DISABLE": "1", **(extra or {})}


def _write_log(home: Path, text: str) -> None:
    logs_dir = home / ".claude" / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / "hooks.log").write_text(text)


def _run(env: dict[str, str], stdin_text: str = "{}") -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_exits_zero_on_empty_log(tmp_path):
    # Arrange
    env = _make_env({"HOME": str(tmp_path), "CLAUDE_SESSION_ID": "test-session-1"})

    # Act
    code, _stdout, _stderr = _run(env)

    # Assert
    assert code == 0


def test_exits_zero_on_unknown_session(tmp_path):
    # Arrange
    _write_log(
        tmp_path,
        json.dumps({"session_id": "other", "decision": "block", "hook": "x"}) + "\n",
    )
    env = _make_env({"HOME": str(tmp_path), "CLAUDE_SESSION_ID": "test-session-2"})

    # Act
    code, _stdout, _stderr = _run(env)

    # Assert
    assert code == 0


def test_prints_nudge_when_blocks_present(tmp_path):
    # Arrange
    entries = [
        {"session_id": "sess-3", "decision": "block", "hook": "alpha"},
        {"session_id": "sess-3", "decision": "block", "hook": "beta"},
    ]
    _write_log(tmp_path, "\n".join(json.dumps(e) for e in entries) + "\n")
    env = _make_env(
        {"HOME": str(tmp_path), "TMPDIR": str(tmp_path), "CLAUDE_SESSION_ID": "sess-3"}
    )

    # Act
    code, _stdout, stderr = _run(env)

    # Assert
    assert code == 0
    assert stderr == (
        "[retro] 2 block(s) this session (top: alpha, beta). "
        "Run /retro to propose upstream fixes.\n"
    )


def test_invalid_json_log_lines_do_not_crash(tmp_path):
    # Arrange
    _write_log(tmp_path, "not json\n{also not json\n")
    env = _make_env({"HOME": str(tmp_path), "CLAUDE_SESSION_ID": "sess-4"})

    # Act
    code, _stdout, _stderr = _run(env)

    # Assert
    assert code == 0


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    env = _make_env()

    # Act
    code, _stdout, _stderr = _run(env, stdin_text="not valid json")

    # Assert
    assert code == 0
