"""Coverage for drizzle-raw-sql-blocker hook.

Source rule: `~/.claude/rules/code-style.md` No raw SQL +
             `~/.claude/rules/lang/drizzle-migrations.md`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = "drizzle-raw-sql-blocker"


@pytest.mark.parametrize("method", ["execute", "run", "all", "get"])
@pytest.mark.parametrize("receiver", ["db", "database", "drizzle", "conn", "client"])
def test_blocks_db_method_with_sql_tag(tool_use, assert_blocks, receiver, method):
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

    # Act / Assert
    assert_blocks(HOOK, payload, f"{receiver}.{method}")


def test_blocks_sql_raw_call(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "sql.raw")


def test_blocks_on_edit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/services/z.service.ts",
            "old_string": "// nothing",
            "new_string": "const r = await db.execute(sql`SELECT 1`);",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "db.execute")


def test_blocks_on_multiedit(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "db.run")


def test_allows_db_select(tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_sql_fragment_in_where(tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_migration_files(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/drizzle/0001_init.sql",
            "content": "CREATE TABLE foo (id uuid PRIMARY KEY);\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_drizzle_meta_files(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/drizzle/0002_add_users.sql",
            "content": "ALTER TABLE foo ADD COLUMN name text;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_drizzle_dir_non_sql_file(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/drizzle/0003_custom.ts",
            "content": "await db.execute(sql`SELECT 1`);\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_schema_files(tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_test_paths(tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_env_bypasses(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "content": "await db.execute(sql`SELECT 1`);\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"DRIZZLE_RAW_SQL_DISABLE": "1"})


def test_disable_env_other_value_does_not_bypass(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "content": "await db.execute(sql`SELECT 1`);\n",
        },
    )

    # Act / Assert
    assert_blocks(
        HOOK,
        payload,
        "db.execute",
        env={"DRIZZLE_RAW_SQL_DISABLE": "0"},
    )


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "drizzle-raw-sql-blocker.py"
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


def test_invalid_json_via_run_hook(run_hook):
    # Arrange / Act
    code, _stdout, _stderr = run_hook("drizzle-raw-sql-blocker", {"_invalid": True})

    # Assert
    assert code == 0


def test_empty_file_path_with_clean_content_is_allowed(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "const rows = await db.select().from(t);\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_non_string_content_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/x.ts", "content": 42},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_non_dict_items_are_safe(tool_use, assert_allows):
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


def test_multiedit_with_non_string_new_string_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/x.ts",
            "edits": [{"old_string": "a", "new_string": 123}],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_unknown_tool_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": "/repo/src/services/x.service.ts"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)
