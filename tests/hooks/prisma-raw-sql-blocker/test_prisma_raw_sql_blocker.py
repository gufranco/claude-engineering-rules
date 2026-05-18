"""Coverage for prisma-raw-sql-blocker hook.

Source rule: `~/.claude/rules/code-style.md` No raw SQL.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = "prisma-raw-sql-blocker"


@pytest.mark.parametrize(
    "method",
    ["queryRaw", "executeRaw", "queryRawUnsafe", "executeRawUnsafe", "queryRawTyped"],
)
def test_blocks_dollar_method_on_prisma(tool_use, assert_blocks, method):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/user.service.ts",
            "content": f"const rows = await prisma.${method}('SELECT 1');\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "raw SQL")


def test_blocks_dollar_query_raw_tagged(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/order.service.ts",
            "content": "const rows = await prisma.$queryRaw`SELECT 1`;\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "raw SQL")


def test_blocks_on_alternative_client_names(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "content": "const r = await db.$executeRaw('UPDATE users SET x = 1');\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "raw SQL")


def test_blocks_on_edit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "old_string": "old",
            "new_string": "await prisma.$queryRaw('SELECT 1');",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "raw SQL")


def test_blocks_on_multiedit(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "raw SQL")


def test_allows_findMany(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/user.service.ts",
            "content": "const users = await prisma.user.findMany();\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_clean_create(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/order.service.ts",
            "content": "const order = await prisma.order.create({ data });\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_migration_files(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/prisma/migrations/20260101000000_init/migration.sql",
            "content": "CREATE TABLE foo (id uuid PRIMARY KEY);\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_sql_files(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/scripts/seed.sql",
            "content": "INSERT INTO foo VALUES (1);\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_test_paths(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/__tests__/seed.ts",
            "content": "await prisma.$executeRaw('TRUNCATE TABLE foo CASCADE');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_env_bypasses(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "content": "await prisma.$queryRaw('SELECT 1');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"PRISMA_RAW_SQL_DISABLE": "1"})


def test_disable_env_other_value_does_not_bypass(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "content": "await prisma.$queryRaw('SELECT 1');\n",
        },
    )

    # Act / Assert
    assert_blocks(
        HOOK,
        payload,
        "raw SQL",
        env={"PRISMA_RAW_SQL_DISABLE": "0"},
    )


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "prisma-raw-sql-blocker.py"
    )
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


def test_unknown_tool_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/services/x.ts"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_non_string_content_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/x.ts", "content": 42},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_non_dict_edits_are_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/x.ts",
            "edits": ["not a dict", None, 42],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_empty_file_path_with_clean_content(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "const x = await prisma.user.findMany();\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_seed_sql_path(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/prisma/seed/migrations/init.sql",
            "content": "INSERT INTO users VALUES (1);\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_with_non_string_new_string(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/x.ts",
            "edits": [{"old_string": "a", "new_string": 999}],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)
