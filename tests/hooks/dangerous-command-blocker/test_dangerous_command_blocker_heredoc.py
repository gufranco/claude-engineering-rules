from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "dangerous-command-blocker"
ROOT_DELETE = "rm -rf /"
FORCE_PUSH = "git push --" + "force origin main"


@pytest.mark.parametrize(
    "command",
    [
        "cat > notes.md <<'EOF'\n" + ROOT_DELETE + "\nEOF",
        "tee notes.md <<EOF >/dev/null\n" + ROOT_DELETE + "\nEOF",
        "git commit -F - <<'EOF'\ndocs: explain " + FORCE_PUSH + "\nEOF",
    ],
)
def test_a_heredoc_body_fed_to_a_data_sink_is_not_a_command(
    tool_use, run_hook, command
):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "command",
    [
        "bash <<'EOF'\n" + ROOT_DELETE + "\nEOF",
        "sh -s <<EOF\n" + ROOT_DELETE + "\nEOF",
        'echo "<<EOF"\n' + ROOT_DELETE,
        "cat <<'EOF' | bash\n" + ROOT_DELETE + "\nEOF",
        "tee /dev/null <<EOF | sh\n" + ROOT_DELETE + "\nEOF",
    ],
)
def test_a_heredoc_body_the_shell_executes_is_still_scanned(
    tool_use, run_hook, command
):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)
