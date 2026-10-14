from __future__ import annotations
from _helpers.hook_assertions import assert_blocked
from _redis_atomicity_helpers import HOOK


def test_blocks_incr_then_expire(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "non-atomic Redis")


def test_blocks_incrby_then_pexpire(tool_use, run_hook):
    # Arrange
    content = "await client.incrBy('k', 1);\nawait client.pexpire('k', 60000);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/counter.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "non-atomic Redis")


def test_blocks_setnx_then_expire(tool_use, run_hook):
    # Arrange
    content = "await client.setnx('lock', '1');\nawait client.expire('lock', 30);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/lock.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "non-atomic Redis")


def test_blocks_hset_then_expire(tool_use, run_hook):
    # Arrange
    content = "await client.hset('h', 'f', 'v');\nawait client.expire('h', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/h.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "non-atomic Redis")


def test_blocks_sadd_then_expire(tool_use, run_hook):
    # Arrange
    content = "await client.sadd('s', 'm');\nawait client.expire('s', 60);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/s.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "non-atomic Redis")


def test_blocks_get_then_set_toctou(tool_use, run_hook):
    # Arrange
    content = (
        "const value = await client.get('k');\n"
        "await client.set('k', String(Number(value) + 1));\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/cas.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "non-atomic Redis")


def test_blocks_get_then_hset(tool_use, run_hook):
    # Arrange
    content = "const v = await client.get('k');\nawait client.hset('h', 'f', v);\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/c.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "non-atomic Redis")


def test_blocks_on_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/limiter.ts",
            "old_string": "old",
            "new_string": ("await client.incr('k');\nawait client.expire('k', 60);\n"),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "non-atomic Redis")


def test_blocks_on_multiedit(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "non-atomic Redis")


def test_blocks_lock_acquisition_without_a_ttl(tool_use, run_hook):
    # Arrange
    content = "const acquired = await client.set('lock:order', token, 'NX');\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/lock.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "lock without a TTL")


def test_blocks_setnx_lock_without_a_ttl(tool_use, run_hook):
    # Arrange
    content = "const ok = await client.setnx('lock:order', token);\nreturn ok;\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/lock.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "lock without a TTL")
