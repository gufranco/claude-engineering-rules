from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "pr-comment-discipline"
GH = "g" + "h"


def test_a_comment_command_inside_a_heredoc_body_is_data(tool_use, run_hook):
    # Arrange
    command = "cat > notes.md <<'EOF'\n" + GH + " pr comment 1 --body hi\nEOF"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_comment_command_after_a_heredoc_is_still_blocked(tool_use, run_hook):
    # Arrange
    command = "cat > notes.md <<'EOF'\nhello\nEOF\n" + GH + " pr comment 1 --body hi"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)
