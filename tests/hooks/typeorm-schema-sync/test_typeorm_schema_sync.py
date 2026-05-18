"""Coverage for typeorm-schema-sync hook.

Source rule: `~/.claude/rules/lang/typeorm-migrations.md`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "typeorm-schema-sync"


def test_blocks_synchronize_true_in_data_source(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/data-source.ts",
            "content": (
                "import { DataSource } from 'typeorm';\n"
                "export const dataSource = new DataSource({\n"
                "  type: 'postgres',\n"
                "  synchronize: true,\n"
                "});\n"
            ),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "synchronize: true")


def test_blocks_drop_schema_true(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/data-source.ts",
            "old_string": "type: 'postgres',",
            "new_string": "type: 'postgres', dropSchema: true,",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "dropSchema: true")


def test_blocks_dataSource_synchronize_call(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/bootstrap.ts",
            "content": (
                "import { dataSource } from './data-source';\n"
                "await dataSource.synchronize();\n"
            ),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "dataSource.synchronize")


def test_blocks_dataSource_dropDatabase_call(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/bootstrap.ts",
            "edits": [
                {
                    "old_string": "await dataSource.initialize();",
                    "new_string": "await dataSource.initialize();\nawait dataSource.dropDatabase();",
                },
            ],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "dropDatabase")


def test_blocks_index_decorator_without_name(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/game.entity.ts",
            "content": (
                "@Entity('game')\n"
                "@Index(['homeTeam', 'awayTeam'])\n"
                "export class Game {}\n"
            ),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "@Index")


def test_blocks_unique_decorator_without_name(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/user.entity.ts",
            "content": (
                "@Entity('user')\n"
                "@Unique(['email'])\n"
                "export class User {}\n"
            ),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "@Unique")


def test_blocks_check_decorator_without_name(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/order.entity.ts",
            "content": (
                "@Entity('order')\n"
                "@Check('amount > 0')\n"
                "export class Order {}\n"
            ),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "@Check")


def test_allows_index_decorator_with_name(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/game.entity.ts",
            "content": (
                "@Entity('game')\n"
                "@Index('Game_homeTeam_idx', ['homeTeam'])\n"
                "export class Game {}\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_synchronize_false(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/data-source.ts",
            "content": (
                "import { DataSource } from 'typeorm';\n"
                "export const dataSource = new DataSource({\n"
                "  type: 'postgres',\n"
                "  synchronize: false,\n"
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
            "content": "await dataSource.synchronize();\n",
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
            "new_string": "synchronize: true",
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
            "content": "We had @Index(['col']) issues last quarter.\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_env_bypasses_block(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/data-source.ts",
            "content": "synchronize: true",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"TYPEORM_SCHEMA_SYNC_DISABLE": "1"})


def test_disable_env_other_value_does_not_bypass(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/data-source.ts",
            "content": "synchronize: true",
        },
    )

    # Act / Assert
    assert_blocks(
        HOOK,
        payload,
        "synchronize: true",
        env={"TYPEORM_SCHEMA_SYNC_DISABLE": "0"},
    )


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "typeorm-schema-sync.py"
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


def test_invalid_json_stdin_with_run_hook(run_hook):
    # Arrange
    # run_hook is the conftest fixture that propagates COVERAGE_PROCESS_START.

    # Act
    code, _stdout, _stderr = run_hook("typeorm-schema-sync", {"_not": "a-valid-tool-payload"})

    # Assert
    assert code == 0


def test_empty_file_path_with_clean_content_is_allowed(tool_use, assert_allows):
    # Arrange
    # Empty file_path is acceptable when the content has no offending pattern.
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "const x = 1;\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_index_decorator_with_empty_args_is_blocked(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/x.entity.ts",
            "content": "@Index()\nexport class X {}\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "@Index")


def test_check_decorator_with_empty_args_is_blocked(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/x.entity.ts",
            "content": "@Check()\nexport class X {}\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "@Check")


def test_check_decorator_with_brackets_in_single_arg_is_blocked(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/x.entity.ts",
            "content": "@Check('amount + (tax * 2) > 0')\nexport class X {}\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "@Check")


def test_check_decorator_with_two_args_is_allowed(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entities/x.entity.ts",
            "content": (
                "@Entity('order')\n"
                "@Check('Order_amount_chk', 'amount > 0')\n"
                "export class Order {}\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_with_non_string_content_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/data-source.ts", "content": 12345},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_with_non_dict_items_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/data-source.ts",
            "edits": ["not a dict", None, 42],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_edit_with_non_string_new_string_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/data-source.ts",
            "old_string": "old",
            "new_string": 12345,
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_with_non_string_new_string_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/data-source.ts",
            "edits": [{"old_string": "a", "new_string": 999}],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_audit_env_bypasses_branch(tool_use, assert_allows):
    # Arrange
    # Confirms the bypass-env audit call line runs.
    payload = tool_use("Write", {"file_path": "/repo/src/x.ts", "content": "synchronize: true"})

    # Act / Assert
    assert_allows(HOOK, payload, env={"TYPEORM_SCHEMA_SYNC_DISABLE": "1"})


def test_unknown_tool_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": "/repo/src/data-source.ts"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_collects_findings(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/entities/order.entity.ts",
            "edits": [
                {"old_string": "x", "new_string": "@Index(['col'])"},
                {"old_string": "y", "new_string": "synchronize: true"},
            ],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "Blocked")


def test_index_with_object_first_arg_is_blocked(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/entity.ts",
            "content": "@Index({ name: 'x' }, ['col'])\nexport class E {}\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "@Index")
