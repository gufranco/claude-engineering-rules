"""Coverage for comment-blocker hook.

Source rule: `~/.claude/rules/code-style.md` Comments Policy. Code must be
self-explanatory; no prose comment is permitted in any scanned file, test
files included (`~/.claude/rules/testing.md`). Tool directives are the one
exempt class.
"""

from __future__ import annotations

import pytest

HOOK = "comment-blocker"
BLOCK_MSG = "comment added to source"


def test_blocks_line_comment_ts(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "// explain\nconst x = 1\n"},
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_block_comment_ts(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "/* explain */\nconst x = 1\n"},
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_multiline_block_comment(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "/*\n multi\n line\n*/\nconst x = 1\n",
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_jsx_comment(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.tsx",
            "content": "const a = <div>{/* c */}</div>\n",
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_hash_comment_python(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.py", "content": "# explain\nx = 1\n"},
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_trailing_comment(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "const x = 1 // trailing\n"},
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_on_edit(tool_use, assert_blocks):
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/app.ts",
            "old_string": "old",
            "new_string": "// note\nconst y = 2",
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_on_multiedit(tool_use, assert_blocks):
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

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_allows_url_in_string(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": 'const u = "https://x.com/a"\n'},
    )

    assert_allows(HOOK, payload)


def test_allows_double_slash_in_template_literal(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "const u = `a//b`\n"},
    )

    assert_allows(HOOK, payload)


def test_allows_private_field_js(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "class A { #x = 1 }\n"},
    )

    assert_allows(HOOK, payload)


def test_allows_hash_in_python_string(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.py", "content": 'x = "a # b"\n'},
    )

    assert_allows(HOOK, payload)


def test_allows_hash_in_python_docstring(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.py",
            "content": 'def f():\n    """a # b"""\n    return 1\n',
        },
    )

    assert_allows(HOOK, payload)


def test_allows_shebang_first_line(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/scripts/run.sh",
            "content": "#!/usr/bin/env bash\necho hi\n",
        },
    )

    assert_allows(HOOK, payload)


def test_allows_no_comment(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "const x = 1\nconst y = 2\n"},
    )

    assert_allows(HOOK, payload)


def test_scans_the_claude_tree_like_any_other_source(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {"file_path": "/home/u/.claude/hooks/x.py", "content": "# doc\nx = 1\n"},
    )

    assert_blocks(HOOK, payload, "comment")


def test_allows_a_docstring_in_the_claude_tree(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/home/u/.claude/hooks/x.py",
            "content": '"""What this module does."""\n\nx = 1\n',
        },
    )

    assert_allows(HOOK, payload)


def test_allows_a_tool_directive_in_the_claude_tree(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/home/u/.claude/hooks/x.py",
            "content": "from _lib.output import block  # noqa: E402\n",
        },
    )

    assert_allows(HOOK, payload)


def test_skips_planning_specs(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/specs/plan/x.ts", "content": "// note\nconst x = 1\n"},
    )

    assert_allows(HOOK, payload)


@pytest.mark.parametrize(
    "marker",
    ["// Arrange", "// Act", "// Assert", "// Act / Assert", "// Arrange / Act"],
)
def test_blocks_former_aaa_marker_in_test_file(tool_use, assert_blocks, marker):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.test.ts", "content": f"{marker}\nconst x = 1\n"},
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_former_aaa_hash_marker_in_python_test(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/tests/test_x.py",
            "content": "# Arrange\nx = 1\n# Act / Assert\nassert x\n",
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_prose_comment_in_test_file(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.test.ts",
            "content": "// setup the thing\nconst x = 1\n",
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_marker_with_description_in_test_file(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.test.ts",
            "content": "// Act: do the thing\nconst x = 1\n",
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_no_per_line_suppression_marker(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// allow-comment -- vendor banner\nconst x = 1\n",
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_no_file_level_suppression_marker(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// @allow-comment -- legal header\n// legal line\nconst x = 1\n",
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


@pytest.mark.parametrize(
    ("file_path", "content"),
    [
        ("/repo/src/app.ts", "// eslint-disable-next-line\nconst x = 1\n"),
        (
            "/repo/src/app.ts",
            "// eslint-disable-next-line no-console -- CLI entry point\nconst x = 1\n",
        ),
        ("/repo/src/app.ts", "/* eslint-disable no-console */\nconst x = 1\n"),
        ("/repo/src/app.ts", "// prettier-ignore\nconst x = 1\n"),
        ("/repo/src/app.ts", "// @ts-expect-error\nconst x = 1\n"),
        ("/repo/src/app.ts", "/** @ts-check */\nconst x = 1\n"),
        ("/repo/src/app.ts", '/// <reference types="node" />\nconst x = 1\n'),
        ("/repo/src/app.ts", "const x = 1 // eslint-disable-line no-magic-numbers\n"),
        ("/repo/src/app.ts", "// biome-ignore lint: intentional\nconst x = 1\n"),
        ("/repo/src/app.ts", "// istanbul ignore next\nconst x = 1\n"),
        ("/repo/pkg/main.go", "//go:build linux\n\npackage main\n"),
        ("/repo/pkg/main.go", "//nolint:errcheck\nx := 1\n"),
        ("/repo/src/app.py", "import os  # noqa: F401\n"),
        ("/repo/src/app.py", "x = load()  # type: ignore[no-any-return]\n"),
        ("/repo/src/app.py", "def f():\n    return 1  # pragma: no cover\n"),
        ("/repo/src/app.py", "# ruff: noqa: E501\nx = 1\n"),
        ("/repo/src/app.py", "# fmt: off\nx = 1\n# fmt: on\n"),
        ("/repo/src/app.py", "# pylint: disable=too-many-locals\nx = 1\n"),
        ("/repo/scripts/run.sh", "# shellcheck disable=SC2086\necho $x\n"),
        ("/repo/src/lib.rs", "// SAFETY: ptr is non-null and aligned\nunsafe { *p }\n"),
        ("/repo/src/app.ts", "// SPDX-License-Identifier: Apache-2.0\nconst x = 1\n"),
        ("/repo/src/app.py", "# SPDX-FileCopyrightText: 2026 Example\nx = 1\n"),
    ],
)
def test_allows_tool_directive(tool_use, assert_allows, file_path, content):
    payload = tool_use("Write", {"file_path": file_path, "content": content})

    assert_allows(HOOK, payload)


@pytest.mark.parametrize(
    "content",
    [
        "// eslint is configured to allow this\nconst x = 1\n",
        "// we disable eslint here because the rule is wrong\nconst x = 1\n",
        "// noqa was removed from the python side\nconst x = 1\n",
    ],
)
def test_blocks_prose_that_mentions_a_tool(tool_use, assert_blocks, content):
    payload = tool_use("Write", {"file_path": "/repo/src/app.ts", "content": content})

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_prose_continuation_of_directive_block(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "/* eslint-disable\n   because the rule is wrong here\n*/\nconst x = 1\n",
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_skips_non_source_extension(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/README.md", "content": "<!-- md comment -->\n# Title\n"},
    )

    assert_allows(HOOK, payload)


def test_skips_unknown_comment_syntax_extension(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts.tmpl", "content": "// note\nconst x = 1\n"},
    )

    assert_allows(HOOK, payload)


def test_allows_empty_file_path(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "// note\nconst x = 1\n"},
    )

    assert_allows(HOOK, payload)


def test_allows_string_with_escaped_backslash(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": 'const s = "a\\tb//c"\n'},
    )

    assert_allows(HOOK, payload)


def test_ignores_non_string_content(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": 123},
    )

    assert_allows(HOOK, payload)


def test_ignores_non_string_edit(tool_use, assert_allows):
    payload = tool_use(
        "Edit",
        {"file_path": "/repo/src/app.ts", "old_string": "a", "new_string": 5},
    )

    assert_allows(HOOK, payload)


def test_ignores_multiedit_non_string_new_string(tool_use, assert_allows):
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/app.ts",
            "edits": [{"old_string": "a", "new_string": 9}],
        },
    )

    assert_allows(HOOK, payload)


def test_skips_node_modules(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/node_modules/x/index.js",
            "content": "// vendor\nvar x = 1\n",
        },
    )

    assert_allows(HOOK, payload)


def test_blocks_former_aaa_marker_in_go_test_file(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/pkg/x_test.go", "content": "// Arrange\nx := 1\n"},
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_former_aaa_marker_in_e2e_segment(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/e2e/flow.ts", "content": "// Act\nconst x = 1\n"},
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_ignores_read_tool(tool_use, assert_allows):
    payload = tool_use(
        "Read",
        {"file_path": "/repo/src/app.ts"},
    )

    assert_allows(HOOK, payload)


def test_ignores_multiedit_non_dict_edit(tool_use, assert_allows):
    payload = tool_use(
        "MultiEdit",
        {"file_path": "/repo/src/app.ts", "edits": ["not-a-dict"]},
    )

    assert_allows(HOOK, payload)


MODULE_WITH_DOCSTRINGS = '''"""Module doc.

Second paragraph.
"""

import os


def f():
    """Return one.

    Extra detail.
    """
    return 1
'''


@pytest.fixture
def python_module(tmp_path):
    path = tmp_path / "app.py"
    path.write_text(MODULE_WITH_DOCSTRINGS, encoding="utf-8")
    return path


def test_blocks_comment_below_a_docstring_closed_by_the_fragment(
    tool_use, assert_blocks, python_module
):
    payload = tool_use(
        "Edit",
        {
            "file_path": str(python_module),
            "old_string": '    Extra detail.\n    """\n    return 1\n',
            "new_string": '    Extra detail.\n    """\n    # explain\n    return 1\n',
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_allows_a_hash_line_inside_a_docstring_opened_by_the_fragment(
    tool_use, assert_allows, python_module
):
    payload = tool_use(
        "Edit",
        {
            "file_path": str(python_module),
            "old_string": 'def f():\n    """Return one.\n',
            "new_string": 'def f():\n    """Return one.\n\n    # 1 is the identity.\n',
        },
    )

    assert_allows(HOOK, payload)


def test_allows_an_edit_that_carries_a_pre_existing_comment(
    tool_use, assert_allows, tmp_path
):
    path = tmp_path / "legacy.py"
    path.write_text("# inherited note\nx = 1\n", encoding="utf-8")
    payload = tool_use(
        "Edit",
        {
            "file_path": str(path),
            "old_string": "# inherited note\nx = 1\n",
            "new_string": "# inherited note\nx = 2\n",
        },
    )

    assert_allows(HOOK, payload)


def test_blocks_a_second_copy_of_an_existing_comment(tool_use, assert_blocks, tmp_path):
    path = tmp_path / "legacy.py"
    path.write_text("# inherited note\nx = 1\n", encoding="utf-8")
    payload = tool_use(
        "Edit",
        {
            "file_path": str(path),
            "old_string": "x = 1\n",
            "new_string": "# inherited note\nx = 1\n",
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_a_comment_added_by_one_edit_of_a_multiedit(
    tool_use, assert_blocks, python_module
):
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": str(python_module),
            "edits": [
                {"old_string": "import os\n", "new_string": "import os\nimport sys\n"},
                {
                    "old_string": "    return 1\n",
                    "new_string": "    # explain\n    return 1\n",
                },
            ],
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_allows_a_multiedit_that_adds_no_comment(
    tool_use, assert_allows, python_module
):
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": str(python_module),
            "edits": [{"old_string": "    return 1\n", "new_string": "    return 2\n"}],
        },
    )

    assert_allows(HOOK, payload)


def test_blocks_when_old_string_does_not_match_the_file(
    tool_use, assert_blocks, python_module
):
    payload = tool_use(
        "Edit",
        {
            "file_path": str(python_module),
            "old_string": "absent from the file",
            "new_string": "# explain\nx = 1\n",
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_leaves_the_file_untouched(tool_use, assert_blocks, python_module):
    payload = tool_use(
        "Edit",
        {
            "file_path": str(python_module),
            "old_string": "import os\n",
            "new_string": "import os  # explain\n",
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)
    assert python_module.read_text(encoding="utf-8") == MODULE_WITH_DOCSTRINGS


def test_falls_back_to_the_fragment_on_a_file_past_the_size_ceiling(
    tool_use, assert_blocks, tmp_path
):
    path = tmp_path / "huge.py"
    path.write_text("x = 1\n" * 120_000, encoding="utf-8")
    payload = tool_use(
        "Edit",
        {
            "file_path": str(path),
            "old_string": "x = 1\n",
            "new_string": "# explain\nx = 2\n",
        },
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_blocks_after_an_unterminated_python_quote(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.py", "content": "s = 'abc\n# explain\n"},
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_allows_a_multiline_shell_string_containing_a_hash(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/scripts/run.sh",
            "content": "msg='line one\nline two # inside'\necho \"$msg\"\n",
        },
    )

    assert_allows(HOOK, payload)


@pytest.mark.parametrize("suffix", [".pyi", ".pyw"])
def test_blocks_comment_in_python_sibling_extension(tool_use, assert_blocks, suffix):
    payload = tool_use(
        "Write",
        {"file_path": f"/repo/src/app{suffix}", "content": "# explain\nx = 1\n"},
    )

    assert_blocks(HOOK, payload, BLOCK_MSG)


def test_allows_docstring_in_a_stub_file(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.pyi", "content": '"""Stub."""\n\nx: int\n'},
    )

    assert_allows(HOOK, payload)


def test_bypass_env(tool_use, assert_allows, monkeypatch):
    monkeypatch.setenv("COMMENT_BLOCKER_DISABLE", "1")
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "// explain\nconst x = 1\n"},
    )

    assert_allows(HOOK, payload)
