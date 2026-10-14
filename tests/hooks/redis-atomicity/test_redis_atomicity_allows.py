from __future__ import annotations
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _redis_atomicity_helpers import HOOK, _redis_write


def test_allows_set_with_ex_options(tool_use, run_hook):
    # Arrange
    content = "await client.set('k', '1', { EX: 60, NX: true });\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/lock.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_multi_exec_pipeline(tool_use, run_hook):
    # Arrange
    content = "await client.multi()\n  .incr('k')\n  .expire('k', 60)\n  .exec();\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/pipe.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_eval_script(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_increment_then_unrelated(tool_use, run_hook):
    # Arrange
    content = "await client.incr('k');\nconsole.log('ok');\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/x.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_expire_after_window(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_atomic_markers_in_window_break_pairing(tool_use, run_hook):
    # Arrange
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_lock_acquisition_with_nx_and_ttl(tool_use, run_hook):
    # Arrange
    content = (
        "const acquired = await client.set('lock:order', token, 'NX', 'EX', 30);\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/lock.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_lock_acquisition_with_options_object(tool_use, run_hook):
    # Arrange
    content = "const acquired = await client.set('lock:order', token, { NX: true, EX: 30 });\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/lock.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_suppression_on_the_first_command_skips_the_pair(tool_use, run_hook):
    # Arrange
    content = (
        "// eslint-disable-next-line no-restricted-syntax\n"
        "await client.incr('k');\n"
        "await client.expire('k', 60);\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/limiter.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_suppression_on_the_second_command_skips_the_pair(tool_use, run_hook):
    # Arrange
    content = (
        "await client.incr('k');\n"
        "// eslint-disable-next-line no-restricted-syntax\n"
        "await client.expire('k', 60);\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/limiter.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_map_get_then_set_is_not_a_redis_race(tool_use, run_hook):
    # Arrange
    content = (
        "const cache = new Map<string, number>();\n"
        "const hit = cache.get(key);\n"
        "cache.set(key, (hit ?? 0) + 1);\n"
    )

    # Act
    result = run_hook(HOOK, _redis_write(tool_use, content))

    # Assert
    assert_allowed(result)


def test_get_and_set_on_different_receivers_is_not_a_race(tool_use, run_hook):
    # Arrange
    content = "const v = await redis.get(key);\nawait audit.set(key, v);\n"

    # Act
    result = run_hook(HOOK, _redis_write(tool_use, content))

    # Assert
    assert_allowed(result)


def test_unrelated_transactions_elsewhere_do_not_hide_a_race(tool_use, run_hook):
    # Arrange
    content = (
        "await redis.multi().set('a', 1).exec();\n"
        "await redis.multi().set('b', 2).exec();\n"
        "\n\n\n\n\n\n"
        "await redis.incr(key);\n"
        "await redis.expire(key, 60);\n"
    )

    # Act
    result = run_hook(HOOK, _redis_write(tool_use, content))

    # Assert
    assert_blocked(result, "Blocked: non-atomic Redis sequence detected.")
