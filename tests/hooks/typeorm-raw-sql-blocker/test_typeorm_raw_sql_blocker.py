from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "typeorm-raw-sql-blocker"


@pytest.mark.parametrize(
    "receiver",
    [
        "dataSource",
        "appDataSource",
        "connection",
        "manager",
        "entityManager",
        "queryRunner",
        "repository",
    ],
)
def test_blocks_query_call_on_known_receivers(tool_use, run_hook, receiver):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, f"{receiver}.query")


def test_blocks_query_on_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/services/order.service.ts",
            "old_string": "return await repo.find();",
            "new_string": "return await repo.query('SELECT * FROM orders');",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "repo.query")


def test_blocks_query_on_multiedit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/billing.service.ts",
            "edits": [
                {"old_string": "x", "new_string": "manager.query(`SELECT 1`)"},
                {"old_string": "y", "new_string": "// nothing here"},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "manager.query")


def test_allows_repository_find(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/user.service.ts",
            "content": (
                "export async function findUser(id: string) {\n"
                "  return await userRepository.findOne({ where: { id } });\n"
                "}\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_query_builder(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/report.service.ts",
            "content": (
                "const qb = repo.createQueryBuilder('u').where('u.id = :id', { id });\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_migration_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/migrations/1700000000000-init.ts",
            "content": (
                "await queryRunner.query(`CREATE TABLE foo (id uuid PRIMARY KEY);`);\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_sql_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/scripts/seed.sql",
            "content": "INSERT INTO foo VALUES (1);\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_test_paths(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/__tests__/seed.ts",
            "content": "await dataSource.query('TRUNCATE TABLE foo CASCADE');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_spec_paths(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/user.spec.ts",
            "old_string": "old",
            "new_string": "manager.query('TRUNCATE TABLE foo CASCADE')",
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
            "file_path": "/repo/src/services/x.service.ts",
            "content": "await dataSource.query('SELECT 1');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"TYPEORM_RAW_SQL_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_other_value_does_not_bypass(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/x.service.ts",
            "content": "await dataSource.query('SELECT 1');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"TYPEORM_RAW_SQL_DISABLE": "0"})

    # Assert
    assert_blocked(result, "dataSource.query")


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "typeorm-raw-sql-blocker.py"
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
    assert proc.returncode == 2


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
        {"file_path": "", "content": "const x = repo.findOne({});\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_with_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/x.ts", "content": 99},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_multiedit_with_non_dict_items_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/x.ts",
            "edits": ["not a dict", None, 42],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_multiedit_with_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/x.ts",
            "edits": [{"old_string": "a", "new_string": 123}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_unknown_tool_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": "/repo/src/services/user.service.ts"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_query_on_unknown_receiver_is_not_flagged(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/user.service.ts",
            "content": "await unrelatedThing.query('something');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_the_anti_pattern_inside_documentation(tool_use, run_hook):
    # Arrange
    content = "# Locking\n\nNever do this in application code:\n\n```typescript\nawait queryRunner.query('SELECT 1');\n```\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/standards/concurrency.md", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_still_blocks_the_same_call_in_application_code(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/account.service.ts",
            "content": "await queryRunner.query('SELECT 1');\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)
