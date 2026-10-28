from __future__ import annotations

from _helpers.hook_assertions import assert_allowed
from comment_blocker_test_data import (
    HOOK,
)


def test_skips_non_source_extension(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/README.md", "content": "<!-- md comment -->\n# Title\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_unknown_comment_syntax_extension(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts.tmpl", "content": "// note\nconst x = 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_empty_file_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "// note\nconst x = 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_string_with_escaped_backslash(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": 'const s = "a\\tb//c"\n'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_ignores_non_string_content(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": 123},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_ignores_non_string_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {"file_path": "/repo/src/app.ts", "old_string": "a", "new_string": 5},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_ignores_multiedit_non_string_new_string(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/app.ts",
            "edits": [{"old_string": "a", "new_string": 9}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_node_modules(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/node_modules/x/index.js",
            "content": "// vendor\nvar x = 1\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_a_bare_marker_in_go_test_file(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/pkg/x_test.go", "content": "// Arrange\nx := 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_a_bare_marker_in_e2e_segment(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/e2e/flow.ts", "content": "// Act\nconst x = 1\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_ignores_read_tool(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": "/repo/src/app.ts"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_ignores_multiedit_non_dict_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {"file_path": "/repo/src/app.ts", "edits": ["not-a-dict"]},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_waived_assembly_source_is_not_checked(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/work/src/example-project/asm/boot.asm",
            "content": "; reset vector\n",
        },
    )

    # Act
    result = run_hook("comment-blocker", payload)

    # Assert
    assert result.code == 0


def test_unreadable_stdin_is_blocked():
    # Arrange
    import os
    import subprocess
    import sys
    from pathlib import Path

    from _helpers.cov_env import apply_coverage_env

    hook = Path(__file__).resolve().parents[3] / "hooks" / "comment-blocker.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input="not json",
        capture_output=True,
        text=True,
        env=apply_coverage_env(dict(os.environ)),
        timeout=30,
        check=False,
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr
