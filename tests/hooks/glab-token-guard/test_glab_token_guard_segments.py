from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "glab-token-guard"
BINARY = "gl" + "ab"
PREFIX = f"GITLAB_TOKEN=t GITLAB_HOST=gitlab.com {BINARY}"


@pytest.mark.parametrize(
    "command",
    [
        f"{PREFIX} mr list && {BINARY} issue list",
        f"{PREFIX} mr list\n{BINARY} issue list",
        f"ls\n{BINARY} mr list",
    ],
)
def test_every_glab_call_needs_its_own_token(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "GITLAB_TOKEN")


@pytest.mark.parametrize(
    "command",
    [
        f"{PREFIX} mr list && {PREFIX} issue list",
        f"export GITLAB_TOKEN=t GITLAB_HOST=gitlab.com\n{BINARY} mr list",
        f"cat <<'EOF'\n{BINARY} mr list\nEOF",
        f"echo '{BINARY} mr list'",
    ],
)
def test_covered_calls_and_quoted_text_pass(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
