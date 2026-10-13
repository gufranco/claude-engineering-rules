from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "drizzle-raw-sql-blocker"


@pytest.mark.parametrize("method", ["execute", "run", "all", "get"])
@pytest.mark.parametrize("receiver", ["db", "database", "drizzle", "conn", "client"])
def test_blocks_db_method_with_sql_tag(tool_use, run_hook, receiver, method):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "content": (
                "import { sql } from 'drizzle-orm';\n"
                f"const rows = await {receiver}.{method}(sql`SELECT 1`);\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, f"{receiver}.{method}")


def test_blocks_sql_raw_call(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/y.service.ts",
            "content": (
                "import { sql } from 'drizzle-orm';\n"
                "const fragment = sql.raw('SELECT 1');\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "sql.raw")


def test_blocks_on_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/services/z.service.ts",
            "old_string": "// nothing",
            "new_string": "const r = await db.execute(sql`SELECT 1`);",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "db.execute")


def test_blocks_on_multiedit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/billing.service.ts",
            "edits": [
                {"old_string": "x", "new_string": "db.run(sql`SELECT 1`)"},
                {"old_string": "y", "new_string": "// clean"},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "db.run")


def test_allows_db_select(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/user.service.ts",
            "content": (
                "import { users } from '../db/schema/users';\n"
                "const rows = await db.select().from(users);\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_sql_fragment_in_where(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/user.service.ts",
            "content": (
                "import { sql } from 'drizzle-orm';\n"
                "const rows = await db.select().from(users)\n"
                "  .where(sql`${users.email} ILIKE ${pattern}`);\n"
            ),
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
            "file_path": "/repo/drizzle/0001_init.sql",
            "content": "CREATE TABLE foo (id uuid PRIMARY KEY);\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_drizzle_meta_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/drizzle/0002_add_users.sql",
            "content": "ALTER TABLE foo ADD COLUMN name text;\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_drizzle_dir_non_sql_file(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/drizzle/0003_custom.ts",
            "content": "await db.execute(sql`SELECT 1`);\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_schema_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/db/schema/users.ts",
            "content": (
                "import { sql } from 'drizzle-orm';\n"
                "import { pgTable, text, timestamp } from 'drizzle-orm/pg-core';\n"
                "export const users = pgTable('users', {\n"
                "  id: text().default(sql`gen_random_uuid()`).primaryKey(),\n"
                "});\n"
            ),
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
            "file_path": "/repo/src/__tests__/db-setup.ts",
            "content": (
                "import { sql } from 'drizzle-orm';\n"
                "await db.execute(sql`TRUNCATE TABLE users CASCADE`);\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_disable_env_bypasses(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "content": "await db.execute(sql`SELECT 1`);\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"DRIZZLE_RAW_SQL_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_other_value_does_not_bypass(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "content": "await db.execute(sql`SELECT 1`);\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"DRIZZLE_RAW_SQL_DISABLE": "0"})

    # Assert
    assert_blocked(result, "db.execute")


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "drizzle-raw-sql-blocker.py"
    )
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"

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


def test_invalid_json_via_run_hook(run_hook):
    # Arrange
    payload = {"_invalid": True}

    # Act
    code, _stdout, _stderr = run_hook(HOOK, payload)

    # Assert
    assert code == 0


def test_empty_file_path_with_clean_content_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "const rows = await db.select().from(t);\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/x.ts", "content": 42},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_multiedit_non_dict_items_block(tool_use, run_hook):
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
    assert_blocked(result)


def test_multiedit_with_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/x.ts",
            "edits": [{"old_string": "a", "new_string": 123}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_unknown_tool_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": "/repo/src/services/x.service.ts"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_the_anti_pattern_inside_documentation(tool_use, run_hook):
    # Arrange
    content = "# Locking\n\nNever do this in application code:\n\n```typescript\nawait db.execute(sql`SELECT 1`);\n```\n"
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
            "content": "await db.execute(sql`SELECT 1`);\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


@pytest.mark.parametrize("receiver", ["tx", "trx", "transaction"])
def test_blocks_raw_sql_on_a_transaction_receiver(tool_use, run_hook, receiver):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/user.service.ts",
            "content": (
                "import { sql } from 'drizzle-orm';\n"
                f"await {receiver}.execute(sql`DELETE FROM users`);\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)
