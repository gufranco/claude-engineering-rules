from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "conventional-commits"
LONG_BODY = "x" * 80


@pytest.mark.parametrize(
    "command",
    [
        "git commit -am 'Updated stuff'",
        "git commit --message='Updated stuff'",
        "git commit --message 'Updated stuff'",
        "git commit -m'Updated stuff'",
        "git commit -q -m 'Updated stuff'",
        "git commit -F - <<'EOF'\nUpdated stuff\nEOF",
        "git commit --file=- <<'EOF'\nUpdated stuff\nEOF",
    ],
)
def test_every_message_form_is_checked(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "conventional commit format")


def test_an_apostrophe_does_not_truncate_the_subject(tool_use, run_hook):
    # Arrange
    subject = "fix(api): handle the user's session token refresh path"
    payload = tool_use("Bash", {"command": f'git commit -m "{subject}"'})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "subject line is 54 characters")


def test_a_second_message_is_checked_as_the_body(tool_use, run_hook):
    # Arrange
    command = f"git commit -m 'fix: short subject' -m '{LONG_BODY}'"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "body line 3 is 80 characters")


def test_a_message_file_is_read_from_the_session_directory(
    tool_use, run_hook, tmp_path
):
    # Arrange
    (tmp_path / "msg.txt").write_text("Updated stuff\n", encoding="utf-8")
    payload = tool_use("Bash", {"command": "git commit -F msg.txt"}, cwd=str(tmp_path))

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "conventional commit format")


@pytest.mark.parametrize(
    "command",
    [
        "git commit -am 'fix: tidy the parser'",
        "git commit -q -F - <<'EOF'\nfix: tidy the parser\n\nKeeps the body short.\nEOF",
        "git commit -m 'fix: tidy the parser' -m 'Second paragraph.'",
        "git commit --message='feat(cli): add a flag'",
    ],
)
def test_conforming_messages_in_every_form_pass(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
