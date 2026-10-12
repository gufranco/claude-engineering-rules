from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "sequelize-schema-sync"


def test_blocks_sync_force_true(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "force: true")


def test_blocks_sync_alter_true(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/server.ts",
            "old_string": "await sequelize.sync();",
            "new_string": "await sequelize.sync({ alter: true });",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "alter: true")


def test_blocks_umzug_storage_none(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "storage: 'none'")


def test_blocks_indexes_entry_without_name(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "indexes entry")


def test_allows_indexes_entry_with_name(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_sync_with_no_options(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/server.ts",
            "content": "await sequelize.sync();\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_umzug_with_sequelize_storage(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_test_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/__tests__/setup.ts",
            "content": "await sequelize.sync({ force: true });\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_spec_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/user.spec.ts",
            "old_string": "old",
            "new_string": "await sequelize.sync({ alter: true });",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_non_ts_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/notes.md",
            "content": "We deprecated sync({ force: true }) last quarter.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_disable_env_bypasses(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/server.ts",
            "content": "await sequelize.sync({ force: true });\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"SEQUELIZE_SCHEMA_SYNC_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_other_value_does_not_bypass(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/server.ts",
            "content": "await sequelize.sync({ force: true });\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"SEQUELIZE_SCHEMA_SYNC_DISABLE": "0"})

    # Assert
    assert_blocked(result, "force: true")


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
        {"file_path": "", "content": "const x = 1;\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_non_string_content_is_safe(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/server.ts", "content": 42},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_multiedit_non_dict_edits_are_safe(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/server.ts",
            "edits": ["not a dict", None, 42],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_indexes_entry_with_complex_fields_and_name_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/models/user.model.ts",
            "content": (
                "export const userModel = sequelize.define('User', {\n"
                "  email: { type: DataTypes.STRING },\n"
                "  companyId: { type: DataTypes.UUID },\n"
                "}, {\n"
                "  indexes: [\n"
                "    { name: 'User_company_email_idx', fields: ['companyId', 'email'], unique: true },\n"
                "  ],\n"
                "});\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_indexes_array_with_no_entries_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/models/user.model.ts",
            "content": (
                "export const userModel = sequelize.define('User', {\n"
                "  email: { type: DataTypes.STRING },\n"
                "}, {\n"
                "  indexes: [],\n"
                "});\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_unknown_tool_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": "/repo/src/server.ts"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_multiedit_collects_findings(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Blocked")
