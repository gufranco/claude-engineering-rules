from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked
from comment_blocker_test_data import (
    BLOCK_MSG,
    HOOK,
)


def test_blocks_line_comment_ts(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "// explain\nconst x = 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_blocks_block_comment_ts(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "/* explain */\nconst x = 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_blocks_multiline_block_comment(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "/*\n multi\n line\n*/\nconst x = 1\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_blocks_jsx_comment(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.tsx",
            "content": "const a = <div>{/* c */}</div>\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_blocks_hash_comment_python(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.py", "content": "# explain\nx = 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_blocks_trailing_comment(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "const x = 1 // trailing\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_blocks_on_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/app.ts",
            "old_string": "old",
            "new_string": "// note\nconst y = 2",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_blocks_on_multiedit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/app.ts",
            "edits": [
                {"old_string": "a", "new_string": "// c\nconst a = 1"},
                {"old_string": "b", "new_string": "const b = 2"},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_allows_url_in_string(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": 'const u = "https://x.com/a"\n'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_double_slash_in_template_literal(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "const u = `a//b`\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_private_field_js(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "class A { #x = 1 }\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_hash_in_python_string(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.py", "content": 'x = "a # b"\n'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_a_docstring_holding_a_hash(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.py",
            "content": 'def f():\n    """a # b"""\n    return 1\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert 'L2: """a # b"""' in stderr


def test_allows_shebang_first_line(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/scripts/run.sh",
            "content": "#!/usr/bin/env bash\necho hi\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_no_comment(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "const x = 1\nconst y = 2\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_scans_the_claude_tree_like_any_other_source(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/home/u/.claude/hooks/x.py", "content": "# doc\nx = 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "comment")


def test_blocks_a_docstring_in_the_claude_tree(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/home/u/.claude/hooks/x.py",
            "content": '"""What this module does."""\n\nx = 1\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert "Docstrings and doc comments are comments" in stderr


def test_allows_a_tool_directive_in_the_claude_tree(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/home/u/.claude/hooks/x.py",
            "content": "from _lib.output import block  # noqa: E402\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_planning_specs(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/specs/plan/x.ts", "content": "// note\nconst x = 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
