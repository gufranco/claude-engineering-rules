from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "prisma-raw-sql-blocker"


@pytest.mark.parametrize(
    "method",
    ["queryRaw", "executeRaw", "queryRawUnsafe", "executeRawUnsafe", "queryRawTyped"],
)
def test_blocks_dollar_method_on_prisma(tool_use, run_hook, method):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/user.service.ts",
            "content": f"const rows = await prisma.${method}('SELECT 1');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "raw SQL")


def test_blocks_dollar_query_raw_tagged(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/order.service.ts",
            "content": "const rows = await prisma.$queryRaw`SELECT 1`;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "raw SQL")


def test_blocks_on_alternative_client_names(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "content": "const r = await db.$executeRaw('UPDATE users SET x = 1');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "raw SQL")


def test_blocks_on_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "old_string": "old",
            "new_string": "await prisma.$queryRaw('SELECT 1');",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "raw SQL")


def test_blocks_on_multiedit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "edits": [
                {"old_string": "a", "new_string": "prisma.$queryRaw`SELECT 1`"},
                {"old_string": "b", "new_string": "// clean"},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "raw SQL")


def test_allows_findMany(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/user.service.ts",
            "content": "const users = await prisma.user.findMany();\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_clean_create(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/order.service.ts",
            "content": "const order = await prisma.order.create({ data });\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_migration_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/prisma/migrations/20260101000000_init/migration.sql",
            "content": "CREATE TABLE foo (id uuid PRIMARY KEY);\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_sql_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/scripts/seed.sql",
            "content": "INSERT INTO foo VALUES (1);\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_raw_sql_in_test_paths(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/__tests__/seed.ts",
            "content": "await prisma.$executeRaw('TRUNCATE TABLE foo CASCADE');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Blocked: Prisma raw SQL is banned in application code.")


def test_disable_env_bypasses(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "content": "await prisma.$queryRaw('SELECT 1');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"PRISMA_RAW_SQL_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_other_value_does_not_bypass(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "content": "await prisma.$queryRaw('SELECT 1');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"PRISMA_RAW_SQL_DISABLE": "0"})

    # Assert
    assert_blocked(result, "raw SQL")


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "prisma-raw-sql-blocker.py"
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
    assert "could not read its input" in proc.stderr


def test_unknown_tool_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/services/x.ts"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/x.ts", "content": 42},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: prisma-raw-sql-blocker could not read its input: tool_input.content is not a",
    )


def test_multiedit_non_dict_edits_block(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/x.ts",
            "edits": ["not a dict", None, 42],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: prisma-raw-sql-blocker could not read its input: tool_input.edits is not a",
    )


def test_empty_file_path_with_clean_content(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "const x = await prisma.user.findMany();\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_seed_sql_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/prisma/seed/migrations/init.sql",
            "content": "INSERT INTO users VALUES (1);\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_multiedit_with_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/x.ts",
            "edits": [{"old_string": "a", "new_string": 999}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: prisma-raw-sql-blocker could not read its input: tool_input.edits is not a",
    )


def test_allows_the_anti_pattern_inside_documentation(tool_use, run_hook):
    # Arrange
    content = "# Locking\n\nNever do this in application code:\n\n```typescript\nawait db.$queryRaw`SELECT 1`;\n```\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/standards/concurrency.md", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_still_blocks_the_same_call_in_application_code(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/account.service.ts",
            "content": "await db.$queryRaw`SELECT 1`;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Blocked: Prisma raw SQL is banned in application code.")
