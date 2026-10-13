from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "internal-config-leakage"
GH = "g" + "h"
GLAB = "gl" + "ab"
LEAK_PATH = "stand" + "ards/multi-account-cli.md"


@pytest.mark.parametrize(
    "command",
    [
        f"sed -n 1,5p {LEAK_PATH}; {GLAB} api --help",
        f"cat {LEAK_PATH}; {GH} pr view 12 --json title",
        f"cat {LEAK_PATH}; {GH} api repos/o/r/pulls/1/comments",
        f"cat {LEAK_PATH}; {GLAB} mr list -F json",
        f"cat {LEAK_PATH}; {GH} issue list --limit 5",
        f"grep -rn 'auth token\\|{GLAB} mr view --json' {LEAK_PATH}",
    ],
)
def test_a_read_only_call_is_not_publishing(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "command",
    [
        f"{GH} pr comment 1 --body 'see {LEAK_PATH}'",
        f"{GH} api repos/o/r/issues/1/comments -f body='see {LEAK_PATH}'",
        f"{GH} api -X PATCH repos/o/r/pulls/1 -f body='see {LEAK_PATH}'",
        f"{GLAB} mr note 1 -m 'see {LEAK_PATH}'",
    ],
)
def test_a_write_call_is_still_scanned(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


@pytest.mark.parametrize("prefix", ["cd /repo && ", "echo start; "])
def test_a_publishing_call_after_a_harmless_prefix_is_scanned(
    tool_use, run_hook, prefix
):
    # Arrange
    command = f"{prefix}{GH} pr create --title t --body 'see {LEAK_PATH}'"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


@pytest.mark.parametrize(
    "command",
    [
        f"python3 - <<'EOF'\nprint('{LEAK_PATH}')\nEOF\ngit commit -m 'fix: tidy'",
        f"python3 -m pytest {LEAK_PATH} && git commit -m 'fix: tidy'",
    ],
    ids=["heredoc-for-another-command", "dash-m-of-another-command"],
)
def test_text_for_another_command_is_not_the_commit_message(
    tool_use, run_hook, command
):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_commit_message_fed_by_heredoc_is_still_scanned(tool_use, run_hook):
    # Arrange
    command = f"git commit -F - <<'EOF'\nfix: see {LEAK_PATH}\nEOF"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_a_publish_after_a_heredoc_is_still_scanned(tool_use, run_hook):
    # Arrange
    command = (
        "cat > notes.md <<'EOF'\nit's fine\nEOF\n"
        f"{GH} pr create --title t --body 'see {LEAK_PATH}'"
    )
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)
