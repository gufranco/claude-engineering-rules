from __future__ import annotations

from _helpers.hook_assertions import assert_blocked
from _icl_support import HOOK

CLI = "g" + "h"
LEAK = "see ~/.claude/rules/testing.md"


def test_an_unbalanced_forge_command_is_treated_as_publishing(tool_use, run_hook):
    # Arrange
    command = f'{CLI} issue create --title x --body "{LEAK}'

    # Act
    result = run_hook(HOOK, tool_use("Bash", {"command": command}))

    # Assert
    assert_blocked(result)


def test_an_attached_post_method_marks_an_api_write(tool_use, run_hook):
    # Arrange
    command = f"{CLI} api repos/a/b/issues -XPOST -f 'body={LEAK}'"

    # Act
    result = run_hook(HOOK, tool_use("Bash", {"command": command}))

    # Assert
    assert_blocked(result)
