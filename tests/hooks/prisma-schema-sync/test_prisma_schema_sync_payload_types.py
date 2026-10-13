from __future__ import annotations

from _helpers.hook_assertions import assert_blocked
from _pss_support import (
    HOOK,
    _write_schema,
)


def test_write_non_string_content_blocks(tmp_path, tool_use, run_hook):
    # Arrange
    migration_sql = _write_schema(
        tmp_path,
        ("model Game {\n  id String @id\n}\n"),
    )
    payload = tool_use(
        "Write",
        {"file_path": str(migration_sql), "content": 12345},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: prisma-schema-sync could not read its input: tool_input.content is not a",
    )


def test_edit_non_string_new_string_blocks(tmp_path, tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: prisma-schema-sync could not read its input: tool_input.new_string is not a",
    )


def test_multiedit_non_dict_edits_blocks(tmp_path, tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: prisma-schema-sync could not read its input: tool_input.edits is not a list of",
    )


def test_multiedit_with_dict_non_string_new_string_blocks(tmp_path, tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: prisma-schema-sync could not read its input: tool_input.edits is not a list of",
    )
