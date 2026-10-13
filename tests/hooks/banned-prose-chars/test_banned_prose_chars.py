from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "banned-prose-chars"

EM_DASH = chr(0x2014)
BOX_DRAWING_LIGHT_HORIZONTAL = chr(0x2500)
BOX_DRAWING_DOUBLE_VERTICAL = chr(0x2551)
ROCKET_EMOJI = chr(0x1F680)
SPARKLES_EMOJI = chr(0x2728)
FLAG_REGIONAL_INDICATOR = chr(0x1F1E7)
ZERO_WIDTH_JOINER = chr(0x200D)


def test_blocks_em_dash_in_write(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/notes.md",
            "content": f"Use this approach{EM_DASH}it scales better.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "em dash")


def test_blocks_em_dash_in_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/notes.md",
            "old_string": "old",
            "new_string": f"keep this clear{EM_DASH}rewrite the sentence",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "em dash")


def test_blocks_em_dash_in_multiedit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/notes.md",
            "edits": [
                {"old_string": "a", "new_string": "clean section a"},
                {"old_string": "b", "new_string": f"split this{EM_DASH}like so"},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "em dash")


def test_blocks_em_dash_in_bash(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"git commit -m 'fix: handle null{EM_DASH}user id'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "em dash")


@pytest.mark.parametrize(
    "box_char",
    [BOX_DRAWING_LIGHT_HORIZONTAL, BOX_DRAWING_DOUBLE_VERTICAL, chr(0x257F)],
)
def test_blocks_box_drawing(tool_use, run_hook, box_char):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/diagram.md",
            "content": f"Diagram:\n{box_char * 5}\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "box-drawing")


@pytest.mark.parametrize(
    "emoji",
    [
        ROCKET_EMOJI,
        SPARKLES_EMOJI,
        FLAG_REGIONAL_INDICATOR,
        ZERO_WIDTH_JOINER,
        chr(0xFE0F),
        chr(0x1FAFF),
    ],
)
def test_blocks_emoji(tool_use, run_hook, emoji):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/README.md",
            "content": f"# Project {emoji}\nLaunch ready.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "emoji")


def test_blocks_multiple_violations_collected(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/x.md",
            "content": (
                f"Title {ROCKET_EMOJI}\n"
                f"Use this{EM_DASH}done.\n"
                f"Diagram: {BOX_DRAWING_LIGHT_HORIZONTAL}\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Blocked")


def test_blocks_em_dash_at_start_of_text(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/x.md",
            "content": f"{EM_DASH} start of file" + ("x" * 200),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "em dash")


def test_blocks_em_dash_at_end_of_text(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/x.md",
            "content": ("x" * 200) + f"end here{EM_DASH}",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "em dash")


def test_blocks_em_dash_with_newline_in_snippet(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/x.md",
            "content": f"first line\n{EM_DASH}\nlast line",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "em dash")


def test_allows_clean_ascii_write(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/clean.md",
            "content": "Plain ASCII with regular punctuation. No tricks.\n",
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
        {"command": "git commit -m 'fix: handle null user id'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_clean_multiedit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/x.md",
            "edits": [
                {"old_string": "a", "new_string": "clean section"},
                {"old_string": "b", "new_string": "another clean section"},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_non_box_drawing_unicode(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/x.md",
            "content": "Accents are fine: cafe naive\n",
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
            "file_path": "/repo/x.md",
            "content": f"Use {EM_DASH} freely with bypass.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"BANNED_PROSE_CHARS_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_disable_env_other_value_does_not_bypass(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/x.md",
            "content": f"Block this {EM_DASH} again.\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"BANNED_PROSE_CHARS_DISABLE": "0"})

    # Assert
    assert_blocked(result, "em dash")


def test_unknown_tool_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/x.md"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_write_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/x.md", "content": 12345},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: banned-prose-chars could not read its input: tool_input.content is not a",
    )


def test_edit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/x.md",
            "old_string": "a",
            "new_string": 999,
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: banned-prose-chars could not read its input: tool_input.new_string is not a",
    )


def test_multiedit_non_dict_items_block(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/x.md",
            "edits": ["not a dict", None, 42],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: banned-prose-chars could not read its input: tool_input.edits is not a list of",
    )


def test_multiedit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/x.md",
            "edits": [{"old_string": "a", "new_string": 12345}],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: banned-prose-chars could not read its input: tool_input.edits is not a list of",
    )


def test_bash_non_string_command_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": 42})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: banned-prose-chars could not read its input: tool_input.command is not a",
    )


def test_invalid_json_stdin_blocks():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "banned-prose-chars.py"
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    env["CLAUDE_BYPASS_STATE"] = os.devnull

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
    assert "could not read its input" in proc.stderr
