from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "found-fix-rationalization-blocker"
DEFERRAL = "fix this in a follow-up PR"


def test_a_publishing_command_inside_a_heredoc_body_is_data(tool_use, run_hook):
    # Arrange
    command = "cat > notes.md <<'EOF'\ngit commit -m '" + DEFERRAL + "'\nEOF"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_commit_message_fed_by_heredoc_is_still_scanned(tool_use, run_hook):
    # Arrange
    command = "git commit -F - <<'EOF'\nfix: guard\n\nWill " + DEFERRAL + ".\nEOF"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result, "Blocked: 'found, did not fix' rationalization detected in artifact."
    )
