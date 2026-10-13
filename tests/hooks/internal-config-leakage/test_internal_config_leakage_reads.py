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
