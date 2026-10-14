from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked
import json as _json
from datetime import datetime, timedelta, timezone
from _redis_atomicity_helpers import HOOK


def test_allows_when_bypass_env_set(tool_use, run_hook):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env={"REDIS_ATOMICITY_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_skips_test_file_path(tool_use, run_hook):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.test.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_spec_file_path(tool_use, run_hook):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.spec.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_tests_dir(tool_use, run_hook):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/tests/limiter.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_non_supported_extension(tool_use, run_hook):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.txt", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_unknown_tool(tool_use, run_hook):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/limiter.ts"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.ts", "content": 42},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: redis-atomicity could not read its input: tool_input.content is not a string.",
    )


def test_edit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/limiter.ts",
            "old_string": "old",
            "new_string": 999,
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: redis-atomicity could not read its input: tool_input.new_string is not a",
    )


def test_multiedit_non_dict_edits_block(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/limiter.ts",
            "edits": ["nope", None, 42],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: redis-atomicity could not read its input: tool_input.edits is not a list of",
    )


def test_multiedit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/limiter.ts",
            "edits": [{"old_string": "a", "new_string": 12345}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: redis-atomicity could not read its input: tool_input.edits is not a list of",
    )


def test_empty_file_path_is_safe(tool_use, run_hook):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_disable_env_other_value_does_not_bypass(tool_use, run_hook):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env={"REDIS_ATOMICITY_DISABLE": "0"})

    # Assert
    assert_blocked(result, "non-atomic Redis")


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "redis-atomicity.py"
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    env["CLAUDE_BYPASS_STATE"] = os.devnull

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not valid json",
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr


def test_profile_disable_short_circuits(tool_use, run_hook):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/src/limiter.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": "redis-atomicity"})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_live_bypass_entry_short_circuits(tmp_path, tool_use, run_hook):
    # Arrange
    state = tmp_path / "bypass.json"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    state.write_text(
        _json.dumps(
            {
                "bypasses": [
                    {"hook": "redis-atomicity", "expires_at": expires, "reason": "t"}
                ]
            }
        )
    )
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/src/limiter.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""
