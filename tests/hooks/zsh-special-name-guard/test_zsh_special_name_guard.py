from __future__ import annotations

import subprocess
import sys

import pytest

HOOK = "zsh-special-name-guard"
ZSH = {"SHELL": "/bin/zsh"}


def bash_payload(tool_use, command: str) -> dict:
    return tool_use("Bash", {"command": command})


@pytest.mark.parametrize(
    "command",
    [
        "for path in a b; do echo $path; done",
        "path=$(git log -1 --format=%H)",
        "local status=0",
        "typeset -a argv",
        "f() { local fpath; fpath=x; }",
        "x=1; manpath=/opt/man",
        "read -r status",
        "export watch=1",
    ],
)
def test_blocks_a_zsh_special_name_used_as_a_variable(tool_use, run_hook, command):
    # Arrange
    payload = bash_payload(tool_use, command)

    # Act
    exit_code, _, stderr = run_hook(HOOK, payload, env=ZSH)

    # Assert
    assert exit_code == 2
    assert "zsh special name" in stderr


@pytest.mark.parametrize(
    "command",
    [
        "echo ==up",
        "printf x; echo =====",
        "[ a == b ]",
    ],
)
def test_blocks_an_unquoted_word_starting_with_equals(tool_use, run_hook, command):
    # Arrange
    payload = bash_payload(tool_use, command)

    # Act
    exit_code, _, stderr = run_hook(HOOK, payload, env=ZSH)

    # Assert
    assert exit_code == 2
    assert "leading equals sign" in stderr


@pytest.mark.parametrize(
    "command",
    [
        "echo 'path=x'",
        'echo "for status in nothing"',
        "echo '== up'",
        "[[ $a == b ]]",
        "(( n == 2 ))",
        "filepath=/tmp/x; mypath=y",
        "git log --format=%H",
        "cat <<'PAYLOAD'\npath=x\n==\nPAYLOAD",
        "a=b c=d make",
        "status_code=200",
        '[ "$t" = tag ] && echo y',
        "test a = b",
    ],
)
def test_allows_commands_without_the_trap(tool_use, run_hook, command):
    # Arrange
    payload = bash_payload(tool_use, command)

    # Act
    exit_code, stdout, _ = run_hook(HOOK, payload, env=ZSH)

    # Assert
    assert (exit_code, stdout) == (0, "")


def test_stays_inert_when_the_shell_is_not_zsh(tool_use, run_hook):
    # Arrange
    payload = bash_payload(tool_use, "for path in a; do :; done")

    # Act
    exit_code, _, _ = run_hook(HOOK, payload, env={"SHELL": "/bin/bash"})

    # Assert
    assert exit_code == 0


def test_ignores_tools_other_than_bash(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": "/tmp/x.sh", "content": "path=x"})

    # Act
    exit_code, _, _ = run_hook(HOOK, payload, env=ZSH)

    # Assert
    assert exit_code == 0


def test_respects_the_disable_variable(tool_use, run_hook):
    # Arrange
    payload = bash_payload(tool_use, "for path in a; do :; done")

    # Act
    exit_code, _, _ = run_hook(
        HOOK, payload, env={**ZSH, "ZSH_SPECIAL_NAME_GUARD_DISABLE": "1"}
    )

    # Assert
    assert exit_code == 0


def test_blocks_unreadable_input_with_a_message(hooks_dir):
    # Arrange
    hook = hooks_dir / f"{HOOK}.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input="not json",
        capture_output=True,
        text=True,
        env={"SHELL": "/bin/zsh", "PATH": "/usr/bin:/bin"},
        check=False,
        timeout=30,
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr


@pytest.mark.parametrize(
    "command",
    [
        "gh api repos/o/r/pulls/1/comments -f path=src/a.ts -f body=x",
        "curl -d status=ok https://example.test",
    ],
)
def test_a_name_equals_value_argument_is_not_an_assignment(tool_use, run_hook, command):
    # Arrange
    payload = bash_payload(tool_use, command)

    # Act
    exit_code, _, _ = run_hook(HOOK, payload, env=ZSH)

    # Assert
    assert exit_code == 0


@pytest.mark.parametrize(
    "command",
    [
        "path=/tmp/x; ls",
        "x=1 path=/tmp/x ls",
        "if true; then status=1; fi",
        "ls && path=/tmp",
    ],
)
def test_an_assignment_at_a_command_start_blocks(tool_use, run_hook, command):
    # Arrange
    payload = bash_payload(tool_use, command)

    # Act
    exit_code, _, stderr = run_hook(HOOK, payload, env=ZSH)

    # Assert
    assert (exit_code, "zsh special name" in stderr) == (2, True)
