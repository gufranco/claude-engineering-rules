from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "drizzle-schema-sync"


def test_blocks_drizzle_kit_push_in_workflow(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/.github/workflows/deploy.yml",
            "content": (
                "name: Deploy\n"
                "jobs:\n"
                "  push:\n"
                "    steps:\n"
                "      - run: pnpm exec drizzle-kit push\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "drizzle-kit push")


def test_blocks_drizzle_kit_push_in_dockerfile(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/Dockerfile",
            "content": ("FROM node:22\nCOPY . /app\nRUN npx drizzle-kit push\n"),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "drizzle-kit push")


def test_blocks_drizzle_kit_push_in_shell_script(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/scripts/deploy.sh",
            "content": ("#!/usr/bin/env bash\nset -euo pipefail\ndrizzle-kit push\n"),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "drizzle-kit push")


def test_blocks_drizzle_kit_push_in_package_json(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/package.json",
            "content": (
                '{\n  "scripts": {\n    "db:push": "drizzle-kit push"\n  }\n}\n'
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "drizzle-kit push")


def test_blocks_drizzle_kit_push_in_bash_payload(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "pnpm exec drizzle-kit push --config drizzle.config.ts"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "drizzle-kit push")


def test_blocks_index_without_name(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/db/schema/users.ts",
            "content": (
                "import { pgTable, text, index } from 'drizzle-orm/pg-core';\n"
                "export const users = pgTable('users', { email: text() }, (t) => ({\n"
                "  emailIdx: index().on(t.email),\n"
                "}));\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "index")


def test_blocks_unique_index_without_name(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/db/schema/users.ts",
            "content": (
                "import { pgTable, text, uniqueIndex } from 'drizzle-orm/pg-core';\n"
                "export const users = pgTable('users', { email: text() }, (t) => ({\n"
                "  emailIdx: uniqueIndex().on(t.email),\n"
                "}));\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "uniqueIndex")


def test_allows_index_with_explicit_name(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/db/schema/users.ts",
            "content": (
                "import { pgTable, text, index } from 'drizzle-orm/pg-core';\n"
                "export const users = pgTable('users', { email: text() }, (t) => ({\n"
                "  emailIdx: index('User_email_idx').on(t.email),\n"
                "}));\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_drizzle_kit_generate(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/.github/workflows/migrate.yml",
            "content": (
                "name: Migrate\n"
                "jobs:\n"
                "  migrate:\n"
                "    steps:\n"
                "      - run: pnpm exec drizzle-kit generate\n"
                "      - run: pnpm exec drizzle-kit migrate\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_clean_bash(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "pnpm exec drizzle-kit migrate"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_index_in_non_drizzle_file_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/utils/helpers.ts",
            "content": "export function index() { return 1; }\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_test_schemas(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/db/__tests__/schema-fixture.ts",
            "content": (
                "import { pgTable, text, index } from 'drizzle-orm/pg-core';\n"
                "export const t = pgTable('t', { c: text() }, (x) => ({\n"
                "  i: index().on(x.c),\n"
                "}));\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_disable_env_bypasses(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "pnpm exec drizzle-kit push"},
    )

    # Act
    result = run_hook(HOOK, payload, env={"DRIZZLE_SCHEMA_SYNC_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_other_value_does_not_bypass(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "pnpm exec drizzle-kit push"},
    )

    # Act
    result = run_hook(HOOK, payload, env={"DRIZZLE_SCHEMA_SYNC_DISABLE": "0"})

    # Assert
    assert_blocked(result, "drizzle-kit push")


def test_schema_edit_path_is_analyzed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/db/schema/users.ts",
            "old_string": "// nothing",
            "new_string": (
                "import { pgTable, text, index } from 'drizzle-orm/pg-core';\n"
                "export const users = pgTable('users', { email: text() }, (t) => ({\n"
                "  emailIdx: index().on(t.email),\n"
                "}));\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "index")


def test_schema_multiedit_path_is_analyzed(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/db/schema/orders.ts",
            "edits": [
                {
                    "old_string": "x",
                    "new_string": (
                        "import { pgTable, text, uniqueIndex } from 'drizzle-orm/pg-core';\n"
                        "export const t = pgTable('t', { c: text() }, (x) => ({\n"
                        "  i: uniqueIndex().on(x.c),\n"
                        "}));\n"
                    ),
                },
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "uniqueIndex")


def test_script_edit_path_blocks_push(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/scripts/deploy.sh",
            "old_string": "echo done",
            "new_string": "drizzle-kit push",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "drizzle-kit push")


def test_script_multiedit_path_blocks_push(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/Dockerfile",
            "edits": [
                {
                    "old_string": "WORKDIR /app",
                    "new_string": "WORKDIR /app\nRUN drizzle-kit push",
                },
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "drizzle-kit push")


def test_index_with_empty_args_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/db/schema/x.ts",
            "content": (
                "import { pgTable, text, index } from 'drizzle-orm/pg-core';\n"
                "export const x = pgTable('x', { c: text() }, (t) => ({\n"
                "  i: index().on(t.c),\n"
                "}));\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "index")


def test_index_method_chain_without_name_in_drizzle_schema(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/db/schema/x.ts",
            "old_string": "old",
            "new_string": (
                "import { pgTable } from 'drizzle-orm/pg-core';\n"
                "// note: uniqueIndex without name\n"
                "uniqueIndex().on(t.email)\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "uniqueIndex")
