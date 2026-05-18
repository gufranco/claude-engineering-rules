"""Coverage for prisma-schema-sync hook.

Source rule: `~/.claude/rules/lang/prisma-migrations.md`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "prisma-schema-sync"


def _write_schema(tmp_path: Path, body: str) -> Path:
    prisma_dir = tmp_path / "prisma"
    prisma_dir.mkdir(parents=True, exist_ok=True)
    schema = prisma_dir / "schema.prisma"
    schema.write_text(body, encoding="utf-8")
    migrations_dir = prisma_dir / "migrations" / "20260101000000_init"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    return migrations_dir / "migration.sql"


def test_blocks_create_index_missing_in_schema(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "Game_homeTeam_idx")


def test_blocks_add_column_not_in_schema(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "ADD COLUMN")


def test_blocks_create_table_no_model(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "CREATE TABLE")


def test_blocks_drop_index_still_in_schema(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "DROP INDEX")


def test_blocks_drop_column_field_still_present(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "DROP COLUMN")


def test_blocks_drop_table_model_still_present(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "DROP TABLE")


def test_blocks_create_unique_index_missing_in_schema(
    tmp_path, tool_use, assert_blocks
):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "User_email_key")


def test_allows_migration_matching_schema(tmp_path, tool_use, assert_allows):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        (
            "model Game {\n"
            "  id String @id\n"
            "  homeTeam String\n"
            "  awayTeam String\n"
            '  @@index([homeTeam], map: "Game_homeTeam_idx")\n'
            '  @@unique([awayTeam], map: "Game_awayTeam_key")\n'
            "}\n"
        ),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": (
                'CREATE TABLE "Game" ("id" TEXT NOT NULL, "homeTeam" TEXT NOT NULL, "awayTeam" TEXT NOT NULL);\n'
                'CREATE INDEX "Game_homeTeam_idx" ON "Game" ("homeTeam");\n'
                'CREATE UNIQUE INDEX "Game_awayTeam_key" ON "Game" ("awayTeam");\n'
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_non_migration_path(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/scripts/seed.sql",
            "content": 'CREATE INDEX "Foo_idx" ON "Foo" ("bar");\n',
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_env_bypasses(tmp_path, tool_use, assert_allows):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'CREATE INDEX "Game_missing_idx" ON "Game" ("homeTeam");\n',
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"PRISMA_SCHEMA_SYNC_DISABLE": "1"})


def test_disable_env_other_value_still_blocks(tmp_path, tool_use, assert_blocks):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Write",
        {
            "file_path": str(migration_sql),
            "content": 'CREATE INDEX "Game_missing_idx" ON "Game" ("homeTeam");\n',
        },
    )

    # Act / Assert
    assert_blocks(
        HOOK,
        payload,
        "Game_missing_idx",
        env={"PRISMA_SCHEMA_SYNC_DISABLE": "0"},
    )


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "prisma-schema-sync.py"
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
    payload = tool_use(
        "Read",
        {"file_path": "/repo/prisma/migrations/20260101000000_init/migration.sql"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_empty_file_path_is_allowed(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": 'CREATE INDEX "x_idx" ON "x" ("y");\n'},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_edit_tool_is_analyzed(tmp_path, tool_use, assert_blocks):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Edit",
        {
            "file_path": str(migration_sql),
            "old_string": "old",
            "new_string": 'CREATE INDEX "Game_missing_idx" ON "Game" ("homeTeam");\n',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "Game_missing_idx")


def test_multiedit_tool_is_analyzed(tmp_path, tool_use, assert_blocks):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": str(migration_sql),
            "edits": [
                {
                    "old_string": "a",
                    "new_string": 'CREATE INDEX "Game_missing_idx" ON "Game" ("homeTeam");\n',
                },
                {"old_string": "b", "new_string": "-- comment\n"},
            ],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "Game_missing_idx")


def test_no_schema_found_is_reported(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "no schema.prisma found")


def test_add_column_table_with_no_model(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "no model")


def test_strip_comments_block_and_line(tmp_path, tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_schema_with_at_map_table_override(tmp_path, tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_non_string_content_is_safe(tmp_path, tool_use, assert_allows):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Write",
        {"file_path": str(migration_sql), "content": 12345},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_edit_non_string_new_string_is_safe(tmp_path, tool_use, assert_allows):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Edit",
        {
            "file_path": str(migration_sql),
            "old_string": "old",
            "new_string": 9999,
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_non_dict_edits_safe(tmp_path, tool_use, assert_allows):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": str(migration_sql),
            "edits": ["not a dict", None, 42],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_drop_column_for_unknown_table_allowed(tmp_path, tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_drop_table_unknown_allowed(tmp_path, tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_drop_index_not_in_schema_is_allowed(tmp_path, tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_schema_via_sibling_prisma_directory(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "Game_x_idx")


def test_schema_nested_braces_in_model_body(tmp_path, tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_schema_with_unmatched_field_lines(tmp_path, tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_schema_via_parent_with_sibling_prisma(tmp_path, tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "Game_x_idx")


def test_multiedit_with_dict_non_string_new_string(tmp_path, tool_use, assert_allows):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": str(migration_sql),
            "edits": [{"old_string": "a", "new_string": 42}],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_schema_read_failure_is_reported(tmp_path, tool_use, assert_blocks):
    # Arrange
    prisma_dir = tmp_path / "prisma"
    prisma_dir.mkdir()
    schema = prisma_dir / "schema.prisma"
    schema.write_text("model Game {\n  id String @id\n}\n", encoding="utf-8")
    schema.chmod(0o000)
    try:
        migrations_dir = prisma_dir / "migrations" / "20260101000000_init"
        migrations_dir.mkdir(parents=True)
        migration_sql = migrations_dir / "migration.sql"
        payload = tool_use(
            "Write",
            {
                "file_path": str(migration_sql),
                "content": 'CREATE INDEX "Game_x_idx" ON "Game" ("id");\n',
            },
        )

        # Act / Assert
        assert_blocks(HOOK, payload, "failed to read")
    finally:
        schema.chmod(0o644)
