"""Coverage for normative-keyword-discipline.

Source rules:
  - ~/.claude/rules/normative-keywords.md (BCP 14 glossary, lowercase-primary).
  - ~/.claude/rules/writing-precision.md "Eliminate weasel words".

The hook is advisory in this phase: it prints a warning to stderr and exits 0.
Promotion to blocking (exit 2) happens later by flipping ADVISORY_MODE in the
hook source.
"""

from __future__ import annotations

import pytest

HOOK = "normative-keyword-discipline"

IN_SCOPE_PATH = "/Users/anyone/.claude/rules/example.md"
SELF_REF_PATH = "/Users/anyone/.claude/rules/normative-keywords.md"
WRITING_PRECISION_PATH = "/Users/anyone/.claude/rules/writing-precision.md"
OUT_OF_SCOPE_PATH = "/tmp/sandbox.md"
NON_MARKDOWN_PATH = "/Users/anyone/.claude/rules/something.txt"
CLAUDE_MD_PATH = "/Users/anyone/.claude/CLAUDE.md"


# ---------- detection: bullet items starting with Should/should ----------


@pytest.mark.parametrize(
    "content",
    [
        "- Should validate input.",
        "* Should always run tests.",
        "1. Should pick a clear approach.",
        "  - Should  doublecheck this.",
        "- should validate input.",
        "* should run the migration.",
    ],
)
def test_blocks_should_bullet(tool_use, assert_blocks, content):
    # Arrange
    payload = tool_use(
        "Edit",
        {"file_path": IN_SCOPE_PATH, "new_string": content},
    )

    # Act / Assert
    code, stderr = assert_blocks(HOOK, payload, "Should ")
    assert "normative-keywords.md" in stderr


# ---------- compliant content: silent allow ----------


@pytest.mark.parametrize(
    "content",
    [
        "- Must validate input.",
        "- Validate input at the boundary.",
        "- May skip when the value is null.",
        "- Never log secrets.",
        "Inline prose: the handler should call the validator.",
        "A paragraph mentioning should as part of a sentence.",
        "- The reader should understand the trade-off before proceeding.",
    ],
)
def test_silent_on_compliant_content(tool_use, assert_allows, content):
    # Arrange
    payload = tool_use(
        "Edit",
        {"file_path": IN_SCOPE_PATH, "new_string": content},
    )

    # Act / Assert
    code, stderr = assert_allows(HOOK, payload)
    assert stderr.strip() == ""


# ---------- scope filtering ----------


def test_out_of_scope_path_is_silent(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {"file_path": OUT_OF_SCOPE_PATH, "new_string": "- Should validate input."},
    )

    # Act / Assert
    code, stderr = assert_allows(HOOK, payload)
    assert stderr.strip() == ""


def test_non_markdown_file_is_silent(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {"file_path": NON_MARKDOWN_PATH, "new_string": "- Should validate input."},
    )

    # Act / Assert
    code, stderr = assert_allows(HOOK, payload)
    assert stderr.strip() == ""


def test_normative_keywords_rule_file_is_silent(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {"file_path": SELF_REF_PATH, "new_string": "- Should validate input."},
    )

    # Act / Assert
    code, stderr = assert_allows(HOOK, payload)
    assert stderr.strip() == ""


def test_writing_precision_rule_file_is_silent(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {"file_path": WRITING_PRECISION_PATH, "new_string": "- Should validate input."},
    )

    # Act / Assert
    code, stderr = assert_allows(HOOK, payload)
    assert stderr.strip() == ""


def test_claude_md_is_in_scope(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {"file_path": CLAUDE_MD_PATH, "new_string": "- Should validate input."},
    )

    # Act / Assert
    code, stderr = assert_blocks(HOOK, payload, "Should")


# ---------- tool support ----------


def test_write_tool_handled(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": IN_SCOPE_PATH, "content": "- Should validate input."},
    )

    # Act / Assert
    code, stderr = assert_blocks(HOOK, payload, "Should")


def test_multiedit_tool_handled(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": IN_SCOPE_PATH,
            "edits": [
                {"old_string": "x", "new_string": "- Should validate input."},
                {"old_string": "y", "new_string": "- Must run tests."},
            ],
        },
    )

    # Act / Assert
    code, stderr = assert_blocks(HOOK, payload, "Should")


def test_bash_tool_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "git commit -m '- Should validate input.'"},
    )

    # Act / Assert
    code, stderr = assert_allows(HOOK, payload)
    assert stderr.strip() == ""


# ---------- bypass ----------


def test_bypass_env_var_silences_hook(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {"file_path": IN_SCOPE_PATH, "new_string": "- Should validate input."},
    )

    # Act / Assert
    code, stderr = assert_allows(
        HOOK,
        payload,
        env={"NORMATIVE_KEYWORD_DISABLE": "1"},
    )
    assert stderr.strip() == ""


# ---------- robustness ----------


def test_malformed_json_does_not_crash(hooks_dir):
    # Arrange
    import subprocess
    import sys as _sys

    hook_path = hooks_dir / "normative-keyword-discipline.py"

    # Act
    proc = subprocess.run(
        [_sys.executable, str(hook_path)],
        input="this is not json",
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "CLAUDE_HOOK_AUDIT_DISABLE": "1"},
        timeout=6.0,
        check=False,
    )

    # Assert
    assert proc.returncode == 0
    assert proc.stderr.strip() == ""


def test_missing_tool_input_is_handled(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Edit", {})

    # Act / Assert
    code, stderr = assert_allows(HOOK, payload)
    assert stderr.strip() == ""


def test_read_tool_is_ignored(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": IN_SCOPE_PATH},
    )

    # Act / Assert
    code, stderr = assert_allows(HOOK, payload)
    assert stderr.strip() == ""


def test_non_string_content_is_silent(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": IN_SCOPE_PATH, "content": 12345},
    )

    # Act / Assert
    code, stderr = assert_allows(HOOK, payload)
    assert stderr.strip() == ""


def test_non_string_new_string_is_silent(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {"file_path": IN_SCOPE_PATH, "new_string": None},
    )

    # Act / Assert
    code, stderr = assert_allows(HOOK, payload)
    assert stderr.strip() == ""


def test_multiedit_skips_non_dict_edits(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": IN_SCOPE_PATH,
            "edits": ["not-a-dict", {"old_string": "x", "new_string": None}],
        },
    )

    # Act / Assert
    code, stderr = assert_allows(HOOK, payload)
    assert stderr.strip() == ""


def test_content_without_trailing_newline(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {"file_path": IN_SCOPE_PATH, "new_string": "- Should validate input."},
    )

    # Act / Assert
    code, stderr = assert_blocks(HOOK, payload, "Should validate input.")


def test_should_run_disabled_via_env(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Edit",
        {"file_path": IN_SCOPE_PATH, "new_string": "- Should validate input."},
    )

    # Act / Assert
    code, stderr = assert_allows(
        HOOK,
        payload,
        env={"CLAUDE_DISABLED_HOOKS": "normative-keyword-discipline"},
    )
    assert stderr.strip() == ""
