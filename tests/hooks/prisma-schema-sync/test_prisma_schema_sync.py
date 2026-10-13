from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _pss_support import (
    HOOK,
    MATCHING_MIGRATION,
    MATCHING_SCHEMA,
    _write_schema,
)


def test_blocks_create_index_missing_in_schema(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n  homeTeam String\n}\n"),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'CREATE INDEX "Game_homeTeam_idx" ON "Game" ("homeTeam");\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Game_homeTeam_idx")


def test_blocks_add_column_not_in_schema(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": ('ALTER TABLE "Game" ADD COLUMN "homeTeam" TEXT NOT NULL;\n'),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "ADD COLUMN")


def test_blocks_create_table_no_model(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'CREATE TABLE "Wager" ("id" TEXT NOT NULL);\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "CREATE TABLE")


def test_blocks_drop_index_still_in_schema(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        (
            "model Game {\n"
            "  id String @id\n"
            "  homeTeam String\n"
            '  @@index([homeTeam], map: "Game_homeTeam_idx")\n'
            "}\n"
        ),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'DROP INDEX "Game_homeTeam_idx";\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "DROP INDEX")


def test_blocks_drop_column_field_still_present(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n  homeTeam String\n}\n"),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'ALTER TABLE "Game" DROP COLUMN "homeTeam";\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "DROP COLUMN")


def test_blocks_drop_table_model_still_present(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'DROP TABLE "Game";\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "DROP TABLE")


def test_blocks_create_unique_index_missing_in_schema(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model User {\n  id String @id\n  email String\n}\n"),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'CREATE UNIQUE INDEX "User_email_key" ON "User" ("email");\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "User_email_key")


def test_allows_migration_matching_schema(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        MATCHING_SCHEMA,
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": MATCHING_MIGRATION,
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
