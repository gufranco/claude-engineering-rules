"""Coverage for sequelize-schema-sync hook.

Source rule: `~/.claude/rules/lang/sequelize-migrations.md`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = "sequelize-schema-sync"


def test_blocks_sync_force_true(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/server.ts",
            "content": (
                "import { sequelize } from './db';\n"
                "await sequelize.sync({ force: true });\n"
            ),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "force: true")


def test_blocks_sync_alter_true(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/server.ts",
            "old_string": "await sequelize.sync();",
            "new_string": "await sequelize.sync({ alter: true });",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "alter: true")


def test_blocks_umzug_storage_none(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/db/umzug.ts",
            "content": (
                "import { Umzug } from 'umzug';\n"
                "export const umzug = new Umzug({\n"
                "  storage: 'none',\n"
                "});\n"
            ),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "storage: 'none'")


def test_blocks_indexes_entry_without_name(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/models/user.model.ts",
            "content": (
                "export const userModel = sequelize.define('User', {\n"
                "  email: { type: DataTypes.STRING },\n"
                "}, {\n"
                "  indexes: [\n"
                "    { fields: ['email'] },\n"
                "  ],\n"
                "});\n"
            ),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "indexes entry")


def test_allows_indexes_entry_with_name(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/models/user.model.ts",
            "content": (
                "export const userModel = sequelize.define('User', {\n"
                "  email: { type: DataTypes.STRING },\n"
                "}, {\n"
                "  indexes: [\n"
                "    { name: 'User_email_idx', fields: ['email'] },\n"
                "  ],\n"
                "});\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_sync_with_no_options(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/server.ts",
            "content": "await sequelize.sync();\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_umzug_with_sequelize_storage(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/db/umzug.ts",
            "content": (
                "import { Umzug, SequelizeStorage } from 'umzug';\n"
                "export const umzug = new Umzug({\n"
                "  storage: new SequelizeStorage({ sequelize }),\n"
                "});\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_test_files(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/__tests__/setup.ts",
            "content": "await sequelize.sync({ force: true });\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_spec_files(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/user.spec.ts",
            "old_string": "old",
            "new_string": "await sequelize.sync({ alter: true });",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_non_ts_files(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/notes.md",
            "content": "We deprecated sync({ force: true }) last quarter.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_env_bypasses(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/server.ts",
            "content": "await sequelize.sync({ force: true });\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"SEQUELIZE_SCHEMA_SYNC_DISABLE": "1"})


def test_disable_env_other_value_does_not_bypass(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/server.ts",
            "content": "await sequelize.sync({ force: true });\n",
        },
    )

    # Act / Assert
    assert_blocks(
        HOOK,
        payload,
        "force: true",
        env={"SEQUELIZE_SCHEMA_SYNC_DISABLE": "0"},
    )


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "sequelize-schema-sync.py"
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
        {"file_path": "/repo/src/server.ts"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_collects_findings(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/server.ts",
            "edits": [
                {"old_string": "x", "new_string": "sync({ force: true })"},
                {"old_string": "y", "new_string": "storage: 'none'"},
            ],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "Blocked")
