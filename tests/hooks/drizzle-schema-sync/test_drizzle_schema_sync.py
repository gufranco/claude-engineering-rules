"""Coverage for drizzle-schema-sync hook.

Source rule: `~/.claude/rules/lang/drizzle-migrations.md`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOOK = "drizzle-schema-sync"


def test_blocks_drizzle_kit_push_in_workflow(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "drizzle-kit push")


def test_blocks_drizzle_kit_push_in_dockerfile(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/Dockerfile",
            "content": (
                "FROM node:22\n"
                "COPY . /app\n"
                "RUN npx drizzle-kit push\n"
            ),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "drizzle-kit push")


def test_blocks_drizzle_kit_push_in_shell_script(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/scripts/deploy.sh",
            "content": (
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "drizzle-kit push\n"
            ),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "drizzle-kit push")


def test_blocks_drizzle_kit_push_in_package_json(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/package.json",
            "content": (
                '{\n'
                '  "scripts": {\n'
                '    "db:push": "drizzle-kit push"\n'
                '  }\n'
                '}\n'
            ),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "drizzle-kit push")


def test_blocks_drizzle_kit_push_in_bash_payload(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "pnpm exec drizzle-kit push --config drizzle.config.ts"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "drizzle-kit push")


def test_blocks_index_without_name(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "index")


def test_blocks_unique_index_without_name(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "uniqueIndex")


def test_allows_index_with_explicit_name(tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_drizzle_kit_generate(tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_clean_bash(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "pnpm exec drizzle-kit migrate"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_index_in_non_drizzle_file_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/utils/helpers.ts",
            "content": "export function index() { return 1; }\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_test_schemas(tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_env_bypasses(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "pnpm exec drizzle-kit push"},
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"DRIZZLE_SCHEMA_SYNC_DISABLE": "1"})


def test_disable_env_other_value_does_not_bypass(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "pnpm exec drizzle-kit push"},
    )

    # Act / Assert
    assert_blocks(
        HOOK,
        payload,
        "drizzle-kit push",
        env={"DRIZZLE_SCHEMA_SYNC_DISABLE": "0"},
    )


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "drizzle-schema-sync.py"
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


def test_edit_with_non_string_new_string_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/db/schema/x.ts",
            "old_string": "old",
            "new_string": 9999,
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_with_non_string_new_string_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/db/schema/x.ts",
            "edits": [{"old_string": "a", "new_string": 123}],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_invalid_json_via_run_hook(run_hook):
    # Arrange / Act
    code, _stdout, _stderr = run_hook("drizzle-schema-sync", {"_invalid": True})

    # Assert
    assert code == 0


def test_empty_file_path_is_allowed(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "drizzle-orm import"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_non_schema_non_script_file_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/utils/regular.ts",
            "content": "console.log('hello');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_schema_edit_path_is_analyzed(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "index")


def test_schema_multiedit_path_is_analyzed(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "uniqueIndex")


def test_script_edit_path_blocks_push(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/scripts/deploy.sh",
            "old_string": "echo done",
            "new_string": "drizzle-kit push",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "drizzle-kit push")


def test_script_multiedit_path_blocks_push(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/Dockerfile",
            "edits": [
                {"old_string": "WORKDIR /app", "new_string": "WORKDIR /app\nRUN drizzle-kit push"},
            ],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "drizzle-kit push")


def test_index_with_empty_args_is_blocked(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "index")


def test_bash_with_non_string_command_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": 12345})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_non_string_content_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/db/schema/x.ts", "content": 9999},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_non_dict_edits_are_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/db/schema/x.ts",
            "edits": ["not a dict", None, 42],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_index_method_chain_without_name_in_drizzle_schema(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "uniqueIndex")


def test_unknown_tool_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": "/repo/src/db/schema/users.ts"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_unrelated_yaml_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/.github/workflows/lint.yml",
            "content": (
                "name: Lint\n"
                "jobs:\n"
                "  lint:\n"
                "    steps:\n"
                "      - run: pnpm lint\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)
