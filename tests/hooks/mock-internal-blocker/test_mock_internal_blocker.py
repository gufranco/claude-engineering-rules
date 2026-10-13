from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "mock-internal-blocker"

JEST = "jest" + ".mock"
VI = "vi" + ".mock"
VITEST = "vitest" + ".mock"
SINON = "sinon" + ".mock"
PY_PATCH = "pat" + "ch"


@pytest.mark.parametrize(
    "target",
    [
        "./services/userService",
        "../services/userService",
        "./repositories/userRepository",
        "../repositories/userRepository",
        "./repository/userRepo",
        "../repository/userRepo",
        "./controllers/userController",
        "../controllers/userController",
        "./controller/userController",
        "./domain/order",
        "../domain/order",
        "@repo/db",
        "@org/auth",
        "@/services/userService",
        "@/db/client",
        "~/services/x",
        "./db",
        "../db",
        "prisma",
        "@prisma/client",
        "mongoose",
        "knex",
        "ioredis",
        "redis",
        "redis/dist",
        "valkey",
        "bull",
        "bullmq",
        "@aws-sdk/client-sqs",
        "kafkajs",
    ],
)
def test_blocks_jest_mock_internal_targets(tool_use, run_hook, target):
    # Arrange
    content = f"{JEST}('{target}');\n"
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/user.test.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal infrastructure")


def test_blocks_vi_mock_in_spec(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/order.spec.ts",
            "content": f"{VI}('./services/order');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal infrastructure")


def test_blocks_vitest_mock(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.test.ts",
            "content": f"{VITEST}('@repo/queue');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal infrastructure")


def test_blocks_sinon_mock(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.test.ts",
            "content": f"{SINON}('./db');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal infrastructure")


def test_blocks_python_patch_of_prisma_in_tests_dir(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/tests/test_users.py",
            "content": f"{PY_PATCH}('prisma');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal infrastructure")


def test_blocks_python_mock_patch_in_underscore_test(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/app/users_test.py",
            "content": f"mock.{PY_PATCH}('@repo/x');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal infrastructure")


def test_blocks_in_underscored_tests_dir(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/__tests__/user.ts",
            "content": f"{JEST}('./services/user');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal infrastructure")


def test_blocks_on_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/user.test.ts",
            "old_string": "old",
            "new_string": f"{JEST}('./services/user');",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal infrastructure")


def test_blocks_on_multiedit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/user.test.ts",
            "edits": [
                {"old_string": "a", "new_string": f"{VI}('./services/user');"},
                {"old_string": "b", "new_string": "// ok"},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "internal infrastructure")


def test_allows_jest_mock_external_axios(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.test.ts",
            "content": f"{JEST}('axios');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_jest_mock_external_stripe(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.test.ts",
            "content": f"{JEST}('stripe');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_mock_in_non_test_file(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/user.ts",
            "content": f"// {JEST}('./services/x') would block in a test.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_disable_env_bypasses(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.test.ts",
            "content": f"{JEST}('./services/user');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"MOCK_INTERNAL_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_other_value_does_not_bypass(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/user.test.ts",
            "content": f"{JEST}('./services/user');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"MOCK_INTERNAL_DISABLE": "0"})

    # Assert
    assert_blocked(result, "internal infrastructure")


def test_unknown_tool_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/user.test.ts"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/user.test.ts", "content": 42},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_edit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/user.test.ts",
            "old_string": "old",
            "new_string": 999,
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_multiedit_non_dict_edits_block(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/user.test.ts",
            "edits": ["nope", None, 42],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_multiedit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/user.test.ts",
            "edits": [{"old_string": "a", "new_string": 12345}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_empty_file_path_is_safe(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": f"{JEST}('./services/x');\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_clean_test_file_passes(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/x.test.ts",
            "content": "describe('x', () => { it('works', () => {}); });\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "mock-internal-blocker.py"
    )
    env = {**os.environ, "CLAUDE_HOOK_AUDIT_DISABLE": "1"}

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
