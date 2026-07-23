"""Coverage for comment-blocker hook.

Source rule: `~/.claude/rules/code-style.md` Comments Policy. Code must be
self-explanatory; the only comments permitted anywhere are the exact
Arrange-Act-Assert markers inside test files (`~/.claude/rules/testing.md`).
"""

from __future__ import annotations

import pytest

HOOK = "comment-blocker"
BLOCK_MSG = "comment added to source"


def test_blocks_line_comment_ts(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "// explain\nconst x = 1\n"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_block_comment_ts(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "/* explain */\nconst x = 1\n"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_multiline_block_comment(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "/*\n multi\n line\n*/\nconst x = 1\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_jsx_comment(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.tsx",
            "content": "const a = <div>{/* c */}</div>\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_hash_comment_python(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.py", "content": "# explain\nx = 1\n"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_trailing_comment(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "const x = 1 // trailing\n"},
    )

    # Act / Assert
    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_on_edit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/app.ts",
            "old_string": "old",
            "new_string": "// note\nconst y = 2",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_on_multiedit(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_allows_url_in_string(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": 'const u = "https://x.com/a"\n'},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_double_slash_in_template_literal(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "const u = `a//b`\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_private_field_js(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "class A { #x = 1 }\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_hash_in_python_string(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.py", "content": 'x = "a # b"\n'},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_hash_in_python_docstring(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.py",
            "content": 'def f():\n    """a # b"""\n    return 1\n',
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_shebang_first_line(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/scripts/run.sh",
            "content": "#!/usr/bin/env bash\necho hi\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_no_comment(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "const x = 1\nconst y = 2\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_claude_tree(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/home/u/.claude/hooks/x.py", "content": "# doc\nx = 1\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_planning_specs(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/specs/plan/x.ts", "content": "// note\nconst x = 1\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


@pytest.mark.parametrize(
    "aaa",
    ["// Arrange", "// Act", "// Assert", "// Act / Assert", "// Arrange / Act"],
)
def test_allows_aaa_in_test_file(tool_use, assert_allows, aaa):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.test.ts", "content": f"{aaa}\nconst x = 1\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_aaa_hash_in_python_test(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/tests/test_x.py",
            "content": "# Arrange\nx = 1\n# Act / Assert\nassert x\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_blocks_non_aaa_comment_in_test_file(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.test.ts",
            "content": "// setup the thing\nconst x = 1\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_aaa_with_description_in_test_file(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.test.ts",
            "content": "// Act: do the thing\nconst x = 1\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_no_per_line_suppression_marker(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// allow-comment -- vendor banner\nconst x = 1\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_no_file_level_suppression_marker(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// @allow-comment -- legal header\n// legal line\nconst x = 1\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_no_eslint_disable_suppression(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// eslint-disable-next-line\nconst x = 1\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_skips_non_source_extension(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/README.md", "content": "<!-- md comment -->\n# Title\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_unknown_comment_syntax_extension(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts.tmpl", "content": "// note\nconst x = 1\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_empty_file_path(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "// note\nconst x = 1\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_string_with_escaped_backslash(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": 'const s = "a\\tb//c"\n'},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_ignores_non_string_content(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": 123},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_ignores_non_string_edit(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {"file_path": "/repo/src/app.ts", "old_string": "a", "new_string": 5},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_ignores_multiedit_non_string_new_string(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/app.ts",
            "edits": [{"old_string": "a", "new_string": 9}],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_node_modules(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/node_modules/x/index.js",
            "content": "// vendor\nvar x = 1\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_aaa_in_go_test_file(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/pkg/x_test.go", "content": "// Arrange\nx := 1\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_aaa_in_e2e_segment(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/e2e/flow.ts", "content": "// Act\nconst x = 1\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_ignores_read_tool(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": "/repo/src/app.ts"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_ignores_multiedit_non_dict_edit(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {"file_path": "/repo/src/app.ts", "edits": ["not-a-dict"]},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_bypass_env(tool_use, assert_allows, monkeypatch):
    # Arrange
    monkeypatch.setenv("COMMENT_BLOCKER_DISABLE", "1")
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "// explain\nconst x = 1\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)
