from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "internal-config-leakage"
CONFIG = "~/.cl" + "aude/rules/x" + ".m" + "d"
GH = "g" + "h"


@pytest.mark.parametrize(
    "command",
    [
        f"cd /tmp && {GH} pr create --title t --body 'see {CONFIG}'",
        f'echo \'{{"body": "see {CONFIG}"}}\' | {GH} api repos/o/r/issues/1/comments --input -',
        f"ls\n{GH} issue create --title t --body 'see {CONFIG}'",
    ],
)
def test_a_publishing_call_behind_an_inert_command_is_scanned(
    tool_use, run_hook, command
):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: internal Claude config or templated scaffolding leaking into external output.",
    )


@pytest.mark.parametrize(
    "command",
    [
        f"cat <<'EOF' > notes.txt\n{GH} pr create --body 'see {CONFIG}'\nEOF",
        f"python3 - <<'PY'\nprint('{GH} pr create {CONFIG}')\nPY",
        f"cd /tmp && grep -r '{CONFIG}' .",
    ],
)
def test_config_text_in_inert_commands_passes(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
