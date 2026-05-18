"""Coverage for retro-pointer hook.

This is a Stop hook that nudges the user to run /retro when block/bypass
events accumulated in the current session.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / "retro-pointer.py"


def _make_env(extra: dict | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    for k in ("COVERAGE_PROCESS_START", "PYTHONPATH"):
        if k in os.environ:
            env[k] = os.environ[k]
    if extra:
        env.update(extra)
    return env


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


def test_exits_zero_on_empty_log():
    # Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        env = _make_env({"HOME": tmpdir, "CLAUDE_SESSION_ID": "test-session-1"})

        # Act
        code, _stdout, _stderr = _run(env)

        # Assert
        assert code == 0


def test_exits_zero_on_unknown_session():
    # Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir) / ".claude" / "logs"
        logs_dir.mkdir(parents=True)
        log = logs_dir / "hooks.log"
        log.write_text(
            json.dumps({"session_id": "other", "decision": "block", "hook": "x"}) + "\n"
        )
        env = _make_env({"HOME": tmpdir, "CLAUDE_SESSION_ID": "test-session-2"})

        # Act
        code, _stdout, _stderr = _run(env)

        # Assert
        assert code == 0


def test_prints_nudge_when_blocks_present():
    # Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir) / ".claude" / "logs"
        logs_dir.mkdir(parents=True)
        log = logs_dir / "hooks.log"
        entries = [
            {"session_id": "sess-3", "decision": "block", "hook": "alpha"},
            {"session_id": "sess-3", "decision": "block", "hook": "beta"},
        ]
        log.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        env = _make_env({"HOME": tmpdir, "CLAUDE_SESSION_ID": "sess-3"})

        # Act
        code, _stdout, stderr = _run(env)

        # Assert
        assert code == 0
        assert "[retro]" in stderr or stderr == ""


def test_invalid_json_log_lines_do_not_crash():
    # Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir) / ".claude" / "logs"
        logs_dir.mkdir(parents=True)
        log = logs_dir / "hooks.log"
        log.write_text("not json\n{also not json\n")
        env = _make_env({"HOME": tmpdir, "CLAUDE_SESSION_ID": "sess-4"})

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
