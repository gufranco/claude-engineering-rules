from __future__ import annotations

import os

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _pss_support import (
    HOOK,
    _write_schema,
)


def test_no_schema_found_is_reported(tmp_path, tool_use, run_hook):
    # Arrange
    migrations_dir = tmp_path / "noschema" / "prisma" / "migrations" / "init"
    migrations_dir.mkdir(parents=True)
    migration_sql = migrations_dir / "migration.sql"
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'CREATE INDEX "x_idx" ON "x" ("y");\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "no schema.prisma found")


def test_add_column_table_with_no_model(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'ALTER TABLE "Unknown" ADD COLUMN "foo" TEXT;\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "no model")


def test_strip_comments_block_and_line(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": (
                '-- CREATE INDEX "Game_missing_idx" ON "Game" ("homeTeam");\n'
                '/* CREATE TABLE "Stale" ("id" TEXT NOT NULL); */\n'
                'CREATE TABLE "Game" ("id" TEXT NOT NULL);\n'
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_schema_with_at_map_table_override(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        (
            "model Game {\n"
            "  id String @id\n"
            '  homeTeam String @map("home_team")\n'
            '  @@map("games")\n'
            '  @@index([homeTeam], map: "games_home_team_idx")\n'
            "}\n"
        ),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": (
                'CREATE TABLE "games" ("id" TEXT NOT NULL, "home_team" TEXT NOT NULL);\n'
                'CREATE INDEX "games_home_team_idx" ON "games" ("home_team");\n'
                'ALTER TABLE "games" ADD COLUMN "home_team" TEXT;\n'
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_schema_via_sibling_prisma_directory(tmp_path, tool_use, run_hook):
    # Arrange
    pkg = tmp_path / "packages" / "database"
    (pkg / "prisma" / "migrations" / "init").mkdir(parents=True)
    (pkg / "prisma" / "schema.prisma").write_text(
        "model Game {\n  id String @id\n}\n",
        encoding="utf-8",
    )
    migration_sql = pkg / "prisma" / "migrations" / "init" / "migration.sql"
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'CREATE INDEX "Game_x_idx" ON "Game" ("id");\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Game_x_idx")


def test_schema_nested_braces_in_model_body(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        (
            "model Game {\n"
            "  id String @id\n"
            '  meta Json @default("{}")\n'
            "  /// nested { brace } in doc comment\n"
            '  @@index([id], map: "Game_id_idx")\n'
            "}\n"
        ),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'CREATE INDEX "Game_id_idx" ON "Game" ("id");\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_schema_with_unmatched_field_lines(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        (
            "model Game {\n"
            "  // standalone comment line\n"
            "  id String @id\n"
            "  homeTeam\n"
            "}\n"
        ),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'CREATE TABLE "Game" ("id" TEXT NOT NULL);\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_schema_via_parent_with_sibling_prisma(tmp_path, tool_use, run_hook):
    # Arrange
    monorepo = tmp_path / "monorepo"
    (monorepo / "prisma").mkdir(parents=True)
    (monorepo / "prisma" / "schema.prisma").write_text(
        "model Game {\n  id String @id\n}\n",
        encoding="utf-8",
    )
    nested_migration = (
        monorepo / "db" / "prisma" / "migrations" / "init" / "migration.sql"
    )
    nested_migration.parent.mkdir(parents=True)
    payload = tool_use(
        "Write",
        {
            "file_path": str(nested_migration),
            "content": 'CREATE INDEX "Game_x_idx" ON "Game" ("id");\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Game_x_idx")


@pytest.mark.skipif(
    os.geteuid() == 0, reason="root reads files without permission bits"
)
def test_schema_read_failure_is_reported(unreadable_schema, tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": str(unreadable_schema),
            "content": 'CREATE INDEX "Game_x_idx" ON "Game" ("id");\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "failed to read")
