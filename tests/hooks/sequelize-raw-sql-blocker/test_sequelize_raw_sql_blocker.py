"""Coverage for sequelize-raw-sql-blocker hook.

Source rule: `~/.claude/rules/code-style.md` No raw SQL +
             `~/.claude/rules/lang/sequelize-migrations.md`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = "sequelize-raw-sql-blocker"


@pytest.mark.parametrize(
    "receiver",
    ["sequelize", "db", "database", "connection", "conn"],
)
def test_blocks_query_call_on_known_receivers(tool_use, assert_blocks, receiver):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/user.service.ts",
            "content": (
                f"export async function loadAll() {{\n"
                f"  return await {receiver}.query('SELECT 1');\n"
                f"}}\n"
            ),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, f"{receiver}.query")


def test_blocks_query_on_edit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/services/order.service.ts",
            "old_string": "return await Order.findAll();",
            "new_string": "return await sequelize.query('SELECT * FROM orders');",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "sequelize.query")


def test_blocks_query_on_multiedit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/billing.service.ts",
            "edits": [
                {"old_string": "x", "new_string": "db.query('SELECT 1')"},
                {"old_string": "y", "new_string": "// nothing here"},
            ],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "db.query")


def test_allows_model_findAll(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/user.service.ts",
            "content": (
                "import { User } from '../models/user.model';\n"
                "export async function findUsers() {\n"
                "  return await User.findAll();\n"
                "}\n"
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
            "file_path": "/repo/migrations/20260514120000-init.ts",
            "content": (
                "export async function up(queryInterface) {\n"
                "  await queryInterface.sequelize.query('CREATE EXTENSION pgcrypto');\n"
                "}\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_seeders_files(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/seeders/20260514120000-seed.ts",
            "content": (
                "export async function up(queryInterface) {\n"
                "  await queryInterface.sequelize.query('INSERT INTO ...');\n"
                "}\n"
            ),
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
            "content": "await sequelize.query('TRUNCATE TABLE foo CASCADE');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_spec_paths(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/user.spec.ts",
            "old_string": "old",
            "new_string": "sequelize.query('TRUNCATE TABLE foo CASCADE')",
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
            "content": "await sequelize.query('SELECT 1');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"SEQUELIZE_RAW_SQL_DISABLE": "1"})


def test_disable_env_other_value_does_not_bypass(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "content": "await sequelize.query('SELECT 1');\n",
        },
    )

    # Act / Assert
    assert_blocks(
        HOOK,
        payload,
        "sequelize.query",
        env={"SEQUELIZE_RAW_SQL_DISABLE": "0"},
    )


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "sequelize-raw-sql-blocker.py"
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
    assert proc.returncode == 0


def test_unknown_tool_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": "/repo/src/services/user.service.ts"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_query_on_unknown_receiver_is_not_flagged(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/user.service.ts",
            "content": "await unrelatedThing.query('something');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)
