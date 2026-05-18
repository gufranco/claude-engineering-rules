"""Coverage for migration-idempotency hook.

Source rule: rules/git-workflow.md Migration Idempotency.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = "migration-idempotency"
BYPASS_ENV = {"MIGRATION_ALLOW_BLOCKING_INDEX": "1"}


@pytest.mark.parametrize(
    "stmt",
    [
        "CREATE TABLE users (id uuid);",
        "CREATE EXTENSION pg_trgm;",
        "CREATE MATERIALIZED VIEW v AS SELECT 1;",
        "CREATE TYPE status AS ENUM ('a', 'b');",
        "CREATE FUNCTION f() RETURNS int AS $$ SELECT 1; $$ LANGUAGE sql;",
        "CREATE SCHEMA app;",
        "CREATE SEQUENCE seq_x;",
        "CREATE TRIGGER tr BEFORE INSERT ON t FOR EACH ROW EXECUTE PROCEDURE f();",
        "CREATE VIEW v AS SELECT 1;",
        "CREATE ROLE app_user;",
        "CREATE USER app_user WITH PASSWORD 'x';",
        "CREATE POLICY p ON t FOR SELECT USING (true);",
    ],
)
def test_blocks_create_without_if_not_exists(tool_use, assert_blocks, stmt):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "content": stmt + "\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "not idempotent", env=BYPASS_ENV)


def test_blocks_create_index_without_concurrently(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_idx.sql",
            "content": "CREATE INDEX IF NOT EXISTS users_email_idx ON users(email);\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "CONCURRENTLY")


def test_allows_create_index_concurrently_if_not_exists(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_idx.sql",
            "content": (
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS users_email_idx "
                "ON users(email);\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_blocking_index_bypass_env_allows(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_idx.sql",
            "content": "CREATE INDEX IF NOT EXISTS users_email_idx ON users(email);\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"MIGRATION_ALLOW_BLOCKING_INDEX": "1"})


@pytest.mark.parametrize(
    "stmt",
    [
        "DROP TABLE users;",
        "DROP INDEX idx_x;",
        "DROP EXTENSION pg_trgm;",
        "DROP VIEW v;",
        "DROP MATERIALIZED VIEW v;",
        "DROP TYPE status;",
        "DROP FUNCTION f();",
        "DROP SCHEMA app;",
        "DROP SEQUENCE seq_x;",
        "DROP TRIGGER tr ON t;",
        "DROP ROLE app_user;",
        "DROP USER app_user;",
        "DROP POLICY p ON t;",
        "ALTER TABLE t DROP COLUMN c;",
        "ALTER TABLE t DROP CONSTRAINT chk_x;",
    ],
)
def test_blocks_drop_without_if_exists(tool_use, assert_blocks, stmt):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_drop.sql",
            "content": stmt + "\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "not idempotent", env=BYPASS_ENV)


def test_allows_idempotent_create_table(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "content": "CREATE TABLE IF NOT EXISTS users (id uuid);\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_idempotent_drop_table(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_drop.sql",
            "content": "DROP TABLE IF EXISTS users;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_create_or_replace_function(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_fn.sql",
            "content": (
                "CREATE OR REPLACE FUNCTION f() RETURNS int "
                "AS $$ SELECT 1; $$ LANGUAGE sql;\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_block_comments_are_stripped(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_comment.sql",
            "content": "/* CREATE TABLE users; DROP TABLE users; */\nSELECT 1;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_line_comments_are_stripped(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_comment.sql",
            "content": "-- CREATE TABLE users\nSELECT 1;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_blocks_in_prisma_migrations_path(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/prisma/migrations/20260101_init/migration.sql",
            "content": "CREATE TABLE users (id uuid);\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "not idempotent", env=BYPASS_ENV)


def test_blocks_in_database_migrations_path(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/database/migrations/20260101_init.sql",
            "content": "CREATE TABLE users (id uuid);\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "not idempotent", env=BYPASS_ENV)


def test_blocks_in_flyway_filename(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/sql/V1_2__init.sql",
            "content": "CREATE TABLE users (id uuid);\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "not idempotent", env=BYPASS_ENV)


def test_blocks_on_edit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "old_string": "old",
            "new_string": "CREATE TABLE users (id uuid);\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "not idempotent", env=BYPASS_ENV)


def test_blocks_on_multiedit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "edits": [
                {"old_string": "a", "new_string": "CREATE TABLE u (id uuid);"},
                {"old_string": "b", "new_string": "DROP TABLE u;"},
            ],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "not idempotent", env=BYPASS_ENV)


def test_skips_non_migration_path(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/sql/seed.sql",
            "content": "CREATE TABLE users (id uuid); DROP TABLE users;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_unknown_tool(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": "/repo/db/migrations/20260101000000_init.sql"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_non_string_content_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "content": 42,
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_edit_non_string_new_string_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
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
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
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
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "edits": [{"old_string": "a", "new_string": 12345}],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_empty_file_path_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "CREATE TABLE users (id uuid);\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_env_bypasses(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "content": "CREATE TABLE users (id uuid); DROP TABLE users;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"MIGRATION_IDEMPOTENCY_DISABLE": "1"})


def test_disable_env_other_value_does_not_bypass(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/db/migrations/20260101000000_init.sql",
            "content": "CREATE TABLE users (id uuid);\n",
        },
    )

    # Act / Assert
    assert_blocks(
        HOOK,
        payload,
        "not idempotent",
        env={
            "MIGRATION_IDEMPOTENCY_DISABLE": "0",
            "MIGRATION_ALLOW_BLOCKING_INDEX": "1",
        },
    )


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "migration-idempotency.py"
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
