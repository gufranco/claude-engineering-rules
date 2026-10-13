from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _pss_support import (
    HOOK,
    _write_schema,
)


def test_drop_column_for_unknown_table_allowed(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'ALTER TABLE "Unknown" DROP COLUMN "foo";\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_drop_table_unknown_allowed(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'DROP TABLE "Unknown";\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_drop_index_not_in_schema_is_allowed(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'DROP INDEX "Game_already_removed_idx";\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_a_second_added_column_missing_from_the_model(
    tmp_path, tool_use, run_hook
):
    # Arrange
    migration_sql = _write_schema(
        tmp_path, "model Game {\n  id String @id\n  homeTeam String\n}\n"
    )
    sql = 'ALTER TABLE "Game" ADD COLUMN "homeTeam" TEXT, ADD COLUMN "venue" TEXT;\n'
    payload = tool_use("Write", {"file_path": str(migration_sql), "content": sql})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, '"venue"')


def test_allows_a_unique_index_declared_on_the_field(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        'model User {\n  id String @id\n  email String @unique(map: "User_email_key")\n}\n',
    )
    sql = 'CREATE UNIQUE INDEX "User_email_key" ON "User" ("email");\n'
    payload = tool_use("Write", {"file_path": str(migration_sql), "content": sql})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
