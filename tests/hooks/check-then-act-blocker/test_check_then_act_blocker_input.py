from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from _helpers.hook_assertions import assert_allowed, assert_blocked
from check_then_act_test_data import (
    ENFORCE,
    FIND_THEN_CREATE,
    HOOK,
)


def test_disable_env_short_circuits(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "content": FIND_THEN_CREATE,
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"CHECK_THEN_ACT_DISABLE": "1", **ENFORCE})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_ignores_unrelated_tools(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "ls"})

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_blocks_a_payload_that_is_not_an_object(run_hook):
    # Arrange
    payload = "not-json"

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "could not read its input")


OFFENDING = FIND_THEN_CREATE


OFFENDING_PATH = "/repo/src/services/seat.service.ts"


def _run_raw(hook_name: str, stdin_text: str, env_extra=None):
    import os
    import subprocess
    import sys
    from pathlib import Path

    hook_path = Path(__file__).resolve().parents[3] / "hooks" / f"{hook_name}.py"
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    for key in ("COVERAGE_PROCESS_START", "PYTHONPATH"):
        if key in os.environ:
            env[key] = os.environ[key]
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )
    return proc.returncode, proc.stderr


def test_raw_invalid_json_blocks():
    # Arrange
    stdin_text = "{not json at all"

    # Act
    code, _stderr = _run_raw(HOOK, stdin_text)

    # Assert
    assert code == 2


def test_empty_file_path_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": "", "content": OFFENDING})

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": 42})

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(
        result,
        "Blocked: check-then-act-blocker could not read its input: tool_input.content is not a",
    )


def test_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit", {"file_path": OFFENDING_PATH, "old_string": "a", "new_string": 42}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(
        result,
        "Blocked: check-then-act-blocker could not read its input: tool_input.new_string is not",
    )


def test_non_dict_edits_block(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit", {"file_path": OFFENDING_PATH, "edits": ["not-a-dict", None]}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(
        result,
        "Blocked: check-then-act-blocker could not read its input: tool_input.edits is not a",
    )


def test_multiedit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {"file_path": OFFENDING_PATH, "edits": [{"old_string": "a", "new_string": 7}]},
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(
        result,
        "Blocked: check-then-act-blocker could not read its input: tool_input.edits is not a",
    )


def test_profile_disable_short_circuits(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": OFFENDING})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": HOOK, **ENFORCE})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_live_bypass_entry_short_circuits(tmp_path, tool_use, run_hook):
    # Arrange
    state = tmp_path / "bypass.json"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    state.write_text(
        json.dumps(
            {"bypasses": [{"hook": HOOK, "expires_at": expires, "reason": "test"}]}
        )
    )
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": OFFENDING})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(state), **ENFORCE})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""
