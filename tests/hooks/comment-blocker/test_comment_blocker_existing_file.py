from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from comment_blocker_test_data import (
    BLOCK_MSG,
    HOOK,
)

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
    tool_use, run_hook, python_module
):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": str(python_module),
            "old_string": '    Extra detail.\n    """\n    return 1\n',
            "new_string": '    Extra detail.\n    """\n    # explain\n    return 1\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_allows_a_hash_line_inside_a_docstring_opened_by_the_fragment(
    tool_use, run_hook, python_module
):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": str(python_module),
            "old_string": 'def f():\n    """Return one.\n',
            "new_string": 'def f():\n    """Return one.\n\n    # 1 is the identity.\n',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_an_edit_that_carries_a_pre_existing_comment(
    tool_use, run_hook, tmp_path
):
    # Arrange
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_a_second_copy_of_an_existing_comment(tool_use, run_hook, tmp_path):
    # Arrange
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_blocks_a_comment_added_by_one_edit_of_a_multiedit(
    tool_use, run_hook, python_module
):
    # Arrange
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_allows_a_multiedit_that_adds_no_comment(tool_use, run_hook, python_module):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": str(python_module),
            "edits": [{"old_string": "    return 1\n", "new_string": "    return 2\n"}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_when_old_string_does_not_match_the_file(
    tool_use, run_hook, python_module
):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": str(python_module),
            "old_string": "absent from the file",
            "new_string": "# explain\nx = 1\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_leaves_the_file_untouched(tool_use, run_hook, python_module):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": str(python_module),
            "old_string": "import os\n",
            "new_string": "import os  # explain\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)
    assert python_module.read_text(encoding="utf-8") == MODULE_WITH_DOCSTRINGS


def test_falls_back_to_the_fragment_on_a_file_past_the_size_ceiling(
    tool_use, run_hook, tmp_path
):
    # Arrange
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_blocks_after_an_unterminated_python_quote(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.py", "content": "s = 'abc\n# explain\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_allows_a_multiline_shell_string_containing_a_hash(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/scripts/run.sh",
            "content": "msg='line one\nline two # inside'\necho \"$msg\"\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize("suffix", [".pyi", ".pyw"])
def test_blocks_comment_in_python_sibling_extension(tool_use, run_hook, suffix):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": f"/repo/src/app{suffix}", "content": "# explain\nx = 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, BLOCK_MSG)


def test_blocks_docstring_in_a_stub_file(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.pyi", "content": '"""Stub."""\n\nx: int\n'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert 'L1: """Stub."""' in stderr


def test_bypass_env(tool_use, run_hook, monkeypatch):
    # Arrange
    monkeypatch.setenv("COMMENT_BLOCKER_DISABLE", "1")
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": "// explain\nconst x = 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
