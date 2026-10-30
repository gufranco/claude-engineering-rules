from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "background-exit-status"


def _background(tool_use, command):
    return tool_use("Bash", {"command": command, "run_in_background": True})


@pytest.mark.parametrize(
    ("command", "reporter"),
    [
        ("brew install --build-from-source marsdev 2>&1 | tail -n 40", "tail"),
        ("make coverage > log 2>&1; echo done", "echo"),
        ('make test; echo "exit=$?" >> log', "echo"),
        ("pytest -q | grep -E 'passed|failed' | tail -3", "tail"),
        ("cd build && make 2>&1 | tee build.log", "tee"),
        ("make; code=$?; printf 'code=%s\\n' \"$code\" > rc.txt", "printf"),
        ("(make check; du -sh coverage)", "du"),
        ("make check\ntail -n 20 log", "tail"),
    ],
)
def test_blocks_a_background_command_ending_in_a_reporter(
    tool_use, run_hook, command, reporter
):
    # Arrange
    payload = _background(tool_use, command)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result, f"A background command ends in `{reporter}`, after the step it runs."
    )


@pytest.mark.parametrize(
    "command",
    [
        "make test > log 2>&1",
        "make test > log 2>&1; code=$?; tail -n 20 log; exit $code",
        "set -o pipefail; make test 2>&1 | tail -n 20",
        "cd build && make",
        "cd /tmp && tail -f server.log",
        "tail -f server.log",
        "echo 'make; tail log'",
        "make 2>&1 >log",
        "{ make check; }",
        "python3 - <<'EOF'\nprint(1); echo\nEOF",
    ],
)
def test_allows_a_background_command_that_keeps_its_status(tool_use, run_hook, command):
    # Arrange
    payload = _background(tool_use, command)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_ignores_a_foreground_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "make test | tail -n 20"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_refuses_a_command_that_is_not_text(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash", {"command": ["make", "|", "tail"], "run_in_background": True}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "tool_input.command is not a string")


def test_an_unbalanced_quote_still_reads_the_command_name(tool_use, run_hook):
    # Arrange
    payload = _background(tool_use, 'make test; echo "unterminated')

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "ends in `echo`")


def test_the_disable_variable_lets_the_command_through(tool_use, run_hook):
    # Arrange
    payload = _background(tool_use, "make test | tail -n 20")

    # Act
    result = run_hook(HOOK, payload, env={"BACKGROUND_EXIT_STATUS_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_the_minimal_profile_does_not_run_it(tool_use, run_hook):
    # Arrange
    payload = _background(tool_use, "make test | tail -n 20")

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_HOOK_PROFILE": "minimal"})

    # Assert
    assert_allowed(result)
