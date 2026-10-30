from __future__ import annotations

import subprocess
import sys

import pytest

from _helpers.cov_env import apply_coverage_env

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


@pytest.mark.parametrize(
    "command",
    [
        'docker run --rm "$r:gates" sh',
        "git show $BRANCH:readme.md",
        'echo "pulling $image:latest"',
        "cd $dir && echo $name:t",
    ],
)
def test_blocks_a_bare_variable_followed_by_a_colon_and_a_letter(
    tool_use, run_hook, command
):
    # Arrange
    payload = bash_payload(tool_use, command)

    # Act
    exit_code, _, stderr = run_hook(HOOK, payload, env=ZSH)

    # Assert
    assert (exit_code, "parameter modifier" in stderr) == (2, True)


@pytest.mark.parametrize(
    "command",
    [
        'docker run --rm "${r}:gates" sh',
        "echo '$r:gates'",
        'curl "$HOST:$PORT/x"',
        'echo "$base://example.test"',
        "echo ${x:-fallback}",
        'echo "\\$r:gates"',
        "git commit -F - <<'ONE' && git commit -F - <<'TWO'\nbody\nONE\nsecond $r:x == y\nTWO",
    ],
)
def test_allows_a_braced_quoted_or_non_letter_colon(tool_use, run_hook, command):
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
        env=apply_coverage_env(
            {
                "SHELL": "/bin/zsh",
                "PATH": "/usr/bin:/bin",
                "CLAUDE_HOOK_AUDIT_DISABLE": "1",
            }
        ),
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


def _guard():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
    spec = importlib.util.spec_from_file_location("zsh_guard", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mask_quoted_keeps_escapes_outside_quotes_and_blanks_them_inside():
    # Arrange
    text = 'a\\b "c\\"d"'

    # Act
    result = _guard().mask_quoted(text)

    # Assert
    assert result == 'a\\b "    "'
