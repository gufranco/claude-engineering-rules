"""Coverage for console-log-blocker hook.

Source rule: `~/.claude/rules/code-style.md` Use the project logger, never console.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = "console-log-blocker"


@pytest.mark.parametrize(
    "method",
    ["log", "warn", "error", "info", "debug", "trace"],
)
def test_blocks_each_console_method(tool_use, assert_blocks, method):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": f"console.{method}('hello');\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, f"console.{method}")


def test_blocks_on_edit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/app.ts",
            "old_string": "old",
            "new_string": "console.log('here');",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "console.log")


def test_blocks_on_multiedit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/app.ts",
            "edits": [
                {"old_string": "a", "new_string": "console.warn('hi');"},
                {"old_string": "b", "new_string": "// nothing"},
            ],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "console.warn")


def test_allows_logger_call(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "logger.info('hello');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_comment_with_console(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// console.log usage is banned in production\nconst x = 1;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_test_file_suffix(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/foo.test.ts",
            "content": "console.log('debug');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_spec_file_suffix(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/foo.spec.tsx",
            "content": "console.log('debug');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_tests_directory(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/__tests__/foo.ts",
            "content": "console.log('debug');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_scripts_directory(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/scripts/seed.ts",
            "content": "console.log('seeded');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_next_error_boundary(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/app/error.tsx",
            "content": "console.error(err);\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_config_file(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/next.config.ts",
            "content": "console.log('config');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_non_js_extension(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/README.md",
            "content": "console.log('docs');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_line_marker_with_justification_suppresses(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "console.log('boot'); // claude-allow-console -- startup banner only\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_file_marker_with_justification_suppresses_all(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/cli.ts",
            "content": (
                "// @claude-allow-console -- CLI entry point intentionally uses console\n"
                "console.log('starting');\n"
                "console.error('done');\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_disable_env_bypasses(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "console.log('hi');\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"CONSOLE_LOG_DISABLE": "1"})


def test_disable_env_other_value_does_not_bypass(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "console.log('hi');\n",
        },
    )

    # Act / Assert
    assert_blocks(
        HOOK,
        payload,
        "console.log",
        env={"CONSOLE_LOG_DISABLE": "0"},
    )


def test_unknown_tool_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/app.ts"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_empty_file_path_is_skipped(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "", "content": "console.log('here');\n"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_write_non_string_content_is_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/app.ts", "content": 42},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multiedit_non_dict_edits_are_safe(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/app.ts",
            "edits": ["not a dict", None, 42],
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_line_marker_above_call_suppresses(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": (
                "// claude-allow-console -- emergency banner before logger boots\n"
                "console.log('boot');\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_block_comment_with_console_pattern_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "  * console.log examples below would block:\nconst x = 1;\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_eslint_disable_next_line_suppresses(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": (
                "// eslint-disable-next-line no-console\nconsole.log('legacy');\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_blank_lines_at_top_skipped_in_file_marker_scan(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/cli.ts",
            "content": (
                "\n\n\n"
                "// @claude-allow-console -- CLI entry point\n"
                "console.log('ready');\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_invalid_json_stdin_does_not_crash():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "console-log-blocker.py"
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
