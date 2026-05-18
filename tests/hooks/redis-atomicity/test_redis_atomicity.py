"""Coverage for redis-atomicity hook.

Source rule: standards/redis.md and checklist.md cat 4.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


HOOK = "redis-atomicity"


def test_blocks_incr_then_expire(tool_use, assert_blocks):
    # Arrange
    content = (
        "async function bump() {\n"
        "  await client.incr('k');\n"
        "  await client.expire('k', 60);\n"
        "}\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.ts", "content": content},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "non-atomic Redis")


def test_blocks_incrby_then_pexpire(tool_use, assert_blocks):
    # Arrange
    content = "await client.incrBy('k', 1);\nawait client.pexpire('k', 60000);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/counter.ts", "content": content},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "non-atomic Redis")


def test_blocks_setnx_then_expire(tool_use, assert_blocks):
    # Arrange
    content = "await client.setnx('lock', '1');\nawait client.expire('lock', 30);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/lock.ts", "content": content},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "non-atomic Redis")


def test_blocks_hset_then_expire(tool_use, assert_blocks):
    # Arrange
    content = "await client.hset('h', 'f', 'v');\nawait client.expire('h', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/h.ts", "content": content},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "non-atomic Redis")


def test_blocks_sadd_then_expire(tool_use, assert_blocks):
    # Arrange
    content = "await client.sadd('s', 'm');\nawait client.expire('s', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/s.ts", "content": content},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "non-atomic Redis")


def test_blocks_get_then_set_toctou(tool_use, assert_blocks):
    # Arrange
    content = (
        "const value = await client.get('k');\n"
        "await client.set('k', String(Number(value) + 1));\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/cas.ts", "content": content},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "non-atomic Redis")


def test_blocks_get_then_hset(tool_use, assert_blocks):
    # Arrange
    content = "const v = await client.get('k');\nawait client.hset('h', 'f', v);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/c.ts", "content": content},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "non-atomic Redis")


def test_blocks_on_edit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/limiter.ts",
            "old_string": "old",
            "new_string": ("await client.incr('k');\nawait client.expire('k', 60);\n"),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "non-atomic Redis")


def test_blocks_on_multiedit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/limiter.ts",
            "edits": [
                {
                    "old_string": "x",
                    "new_string": (
                        "await client.incr('k');\nawait client.expire('k', 60);\n"
                    ),
                },
                {"old_string": "y", "new_string": "// ok\n"},
            ],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "non-atomic Redis")


def test_allows_set_with_ex_options(tool_use, assert_allows):
    # Arrange
    content = "await client.set('k', '1', { EX: 60, NX: true });\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/lock.ts", "content": content},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_multi_exec_pipeline(tool_use, assert_allows):
    # Arrange
    content = "await client.multi()\n  .incr('k')\n  .expire('k', 60)\n  .exec();\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/pipe.ts", "content": content},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_eval_script(tool_use, assert_allows):
    # Arrange
    content = (
        "await client.eval(\n"
        '  \'redis.call("incr", KEYS[1]); redis.call("expire", KEYS[1], ARGV[1])\',\n'
        "  1, 'k', 60);\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/script.ts", "content": content},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_when_bypass_env_set(tool_use, assert_allows):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.ts", "content": content},
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"REDIS_ATOMICITY_DISABLE": "1"})


def test_skips_test_file_path(tool_use, assert_allows):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.test.ts", "content": content},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_spec_file_path(tool_use, assert_allows):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.spec.ts", "content": content},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_tests_dir(tool_use, assert_allows):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/tests/limiter.ts", "content": content},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_non_supported_extension(tool_use, assert_allows):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.txt", "content": content},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_unknown_tool(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/limiter.ts"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_non_string_content_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.ts", "content": 42},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_edit_non_string_new_string_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/limiter.ts",
            "old_string": "old",
            "new_string": 999,
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_non_dict_edits_are_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/limiter.ts",
            "edits": ["nope", None, 42],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_non_string_new_string_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/limiter.ts",
            "edits": [{"old_string": "a", "new_string": 12345}],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_empty_file_path_is_safe(tool_use, assert_allows):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "", "content": content},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_increment_then_unrelated(tool_use, assert_allows):
    # Arrange
    content = "await client.incr('k');\nconsole.log('ok');\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/x.ts", "content": content},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_expire_after_window(tool_use, assert_allows):
    # Arrange
    content = (
        "await client.incr('k');\n"
        "// 1\n// 2\n// 3\n// 4\n// 5\n// 6\n"
        "await client.expire('k', 60);\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/x.ts", "content": content},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_env_bypasses(tool_use, assert_allows):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.ts", "content": content},
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"REDIS_ATOMICITY_DISABLE": "1"})


def test_disable_env_other_value_does_not_bypass(tool_use, assert_blocks):
    # Arrange
    content = "await client.incr('k');\nawait client.expire('k', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.ts", "content": content},
    )

    # Act / Assert
    assert_blocks(
        HOOK,
        payload,
        "non-atomic Redis",
        env={"REDIS_ATOMICITY_DISABLE": "0"},
    )


def test_atomic_markers_in_window_break_pairing(tool_use, assert_allows):
    # Arrange
    # An atomic marker between the incr and expire breaks the unsafe pair.
    content = (
        "await client.incr('k');\n"
        "// MULTI/EXEC begin\n"
        "await pipeline.exec();\n"
        "await client.expire('k', 60);\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/limiter.ts", "content": content},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "redis-atomicity.py"
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    for k in ("COVERAGE_PROCESS_START", "PYTHONPATH"):
        if k in os.environ:
            env[k] = os.environ[k]

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
    assert proc.returncode == 0
