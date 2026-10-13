from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _pss_support import (
    HOOK,
    _write_schema,
)


def test_skips_non_migration_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/scripts/seed.sql",
            "content": 'CREATE INDEX "Foo_idx" ON "Foo" ("bar");\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_disable_env_bypasses(tmp_path, tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload, env={"PRISMA_SCHEMA_SYNC_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_other_value_still_blocks(tmp_path, tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload, env={"PRISMA_SCHEMA_SYNC_DISABLE": "0"})

    # Assert
    assert_blocked(result, "Game_missing_idx")


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "prisma-schema-sync.py"
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
    payload = tool_use(
        "Read",
        {"file_path": "/repo/prisma/migrations/20260101000000_init/migration.sql"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_empty_file_path_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": 'CREATE INDEX "x_idx" ON "x" ("y");\n'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_edit_tool_is_analyzed(tmp_path, tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Game_missing_idx")


def test_multiedit_tool_is_analyzed(tmp_path, tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Game_missing_idx")
