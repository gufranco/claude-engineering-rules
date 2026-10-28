from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from _helpers.cov_env import apply_coverage_env

HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / "retro-pointer.py"


SESSION_KEYS = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "SESSION_ID")
TIMEOUT_S = 30


def _make_env(home: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    inherited = {k: v for k, v in os.environ.items() if k not in SESSION_KEYS}
    return {
        **inherited,
        "HOME": str(home),
        "TMPDIR": str(home),
        "CLAUDE_HOOK_AUDIT_DISABLE": "1",
        "CLAUDE_BYPASS_STATE": os.devnull,
        **(extra or {}),
    }


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
        env=apply_coverage_env(env),
        timeout=TIMEOUT_S,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_stays_silent_without_a_log(tmp_path):
    # Arrange
    env = _make_env(tmp_path, {"CLAUDE_SESSION_ID": "test-session-1"})

    # Act
    code, stdout, stderr = _run(env)

    # Assert
    assert (code, stdout, stderr) == (0, "", "")


def test_ignores_blocks_from_another_session(tmp_path):
    # Arrange
    _write_log(
        tmp_path,
        json.dumps({"session_id": "other", "decision": "block", "hook": "x"}) + "\n",
    )
    env = _make_env(tmp_path, {"CLAUDE_SESSION_ID": "test-session-2"})

    # Act
    code, stdout, stderr = _run(env)

    # Assert
    assert (code, stdout, stderr) == (0, "", "")


def test_prints_nudge_when_blocks_present(tmp_path):
    # Arrange
    entries = [
        {"session_id": "sess-3", "decision": "block", "hook": "alpha"},
        {"session_id": "sess-3", "decision": "block", "hook": "beta"},
    ]
    _write_log(tmp_path, "\n".join(json.dumps(e) for e in entries) + "\n")
    env = _make_env(tmp_path, {"CLAUDE_SESSION_ID": "sess-3"})

    # Act
    code, stdout, _stderr = _run(env)

    # Assert
    assert code == 0
    assert json.loads(stdout) == {
        "systemMessage": "[retro] 2 block(s) this session (top: alpha, beta). "
        "Run /retro to propose upstream fixes."
    }


def test_invalid_json_log_lines_are_skipped_silently(tmp_path):
    # Arrange
    _write_log(tmp_path, "not json\n{also not json\n")
    env = _make_env(tmp_path, {"CLAUDE_SESSION_ID": "sess-4"})

    # Act
    code, stdout, stderr = _run(env)

    # Assert
    assert (code, stdout, stderr) == (0, "", "")


def test_invalid_json_stdin_is_reported_and_allowed(tmp_path):
    # Arrange
    env = _make_env(tmp_path, {"CLAUDE_SESSION_ID": "sess-5"})

    # Act
    code, stdout, stderr = _run(env, stdin_text="not valid json")

    # Assert
    assert (code, stdout) == (0, "")
    assert stderr.startswith("retro-pointer: unreadable payload: ")


def _entry(**fields: str) -> str:
    return json.dumps(fields) + "\n"


def test_a_large_log_is_read_from_its_tail(tmp_path):
    # Arrange
    padding = "x" * (70 * 1024) + "\n"
    _write_log(tmp_path, padding + _entry(session_id="s6", decision="block", hook="h"))
    env = _make_env(tmp_path, {"CLAUDE_SESSION_ID": "s6"})

    # Act
    code, stdout, _stderr = _run(env)

    # Assert
    assert (code, json.loads(stdout)["systemMessage"]) == (
        0,
        "[retro] 1 block(s) this session (top: h). Run /retro to propose upstream fixes.",
    )


def test_without_a_session_id_recent_entries_count(tmp_path):
    # Arrange
    recent = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime())
    _write_log(
        tmp_path,
        _entry(ts=recent, decision="bypass")
        + _entry(ts="not a time", decision="block", hook="old")
        + _entry(ts="2001-01-01T00:00:00Z", decision="block", hook="ancient"),
    )
    env = _make_env(tmp_path)

    # Act
    code, stdout, _stderr = _run(env)

    # Assert
    assert (code, json.loads(stdout)["systemMessage"]) == (
        0,
        "[retro] 1 bypass(es) this session. Run /retro to propose upstream fixes.",
    )


def test_blocks_count_once_per_hook_and_bypasses_add_up(tmp_path):
    # Arrange
    _write_log(
        tmp_path,
        _entry(session_id="s7", decision="block", hook="a")
        + _entry(session_id="s7", decision="block", hook="a")
        + _entry(session_id="s7", decision="block")
        + _entry(session_id="s7", decision="bypass")
        + _entry(session_id="s7", decision="allow"),
    )
    env = _make_env(tmp_path, {"CLAUDE_SESSION_ID": "s7"})

    # Act
    code, stdout, _stderr = _run(env)

    # Assert
    assert (code, json.loads(stdout)["systemMessage"]) == (
        0,
        "[retro] 3 block(s) and 1 bypass(es) this session (top: a). "
        "Run /retro to propose upstream fixes.",
    )


def test_transcript_patterns_produce_an_instinct_notice(tmp_path):
    # Arrange
    transcript = tmp_path / "t.jsonl"
    lines = [
        "no, not that one",
        "I said use the other file",
        *["ERROR: disk full"] * 3,
        *["hook blocked the call"] * 4,
        "Error:",
    ]
    transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")
    env = _make_env(tmp_path, {"CLAUDE_SESSION_ID": "s8"})

    # Act
    code, stdout, _stderr = _run(env, json.dumps({"transcript_path": str(transcript)}))

    # Assert
    assert (code, json.loads(stdout)["systemMessage"]) == (
        0,
        "[retro instinct] session patterns worth capturing: user corrections (2); "
        "repeated error: `disk full`; hook blocks (4). Run /retro instinct to record.",
    )


def test_the_notice_shows_once_per_session(tmp_path):
    # Arrange
    _write_log(tmp_path, _entry(session_id="s9", decision="block", hook="h"))
    env = _make_env(tmp_path, {"CLAUDE_SESSION_ID": "s9"})
    _run(env)

    # Act
    code, stdout, stderr = _run(env)

    # Assert
    assert (code, stdout, stderr) == (0, "", "")


def test_an_internal_failure_is_reported_and_allowed(tmp_path):
    # Arrange
    _write_log(tmp_path, _entry(session_id="s10", decision="block", hook="h"))
    log = tmp_path / ".claude" / "logs" / "hooks.log"
    log.chmod(0)
    env = _make_env(tmp_path, {"CLAUDE_SESSION_ID": "s10"})

    # Act
    code, stdout, stderr = _run(env)

    # Assert
    assert (code, stdout) == (0, "")
    assert stderr.startswith(
        "retro-pointer: summary failed: [Errno 13] Permission denied"
    )
