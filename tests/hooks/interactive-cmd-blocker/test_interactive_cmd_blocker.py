"""Coverage for the interactive-cmd-blocker hook."""

from __future__ import annotations

import pytest

HOOK = "interactive-cmd-blocker"


# ---------------------------------------------------------------------------
# Block: cp/mv/rm without -f
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "rm file.txt",
        "rm -r mydir",
        "rm -v file.txt",
        "/bin/rm file.txt",
        "cp src.txt dst.txt",
        "cp -r srcdir/ dstdir/",
        "mv old.txt new.txt",
        "mv -v old.txt new.txt",
    ],
)
def test_blocks_command_without_force(tool_use, assert_blocks, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_blocks(HOOK, payload, "without `-f`")


def test_blocks_in_compound_command(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Bash", {"command": "echo hi && rm foo.txt"})

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_after_or(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Bash", {"command": "test -f x.txt || rm x.txt"})

    # Act / Assert
    assert_blocks(HOOK, payload)


def test_blocks_via_command_builtin(tool_use, assert_blocks):
    # Arrange
    payload = tool_use("Bash", {"command": "command rm file.txt"})

    # Act / Assert
    assert_blocks(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: cp/mv/rm with -f or --force
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "rm -f file.txt",
        "rm -rf mydir",
        "rm -fr mydir",
        "rm -rfv mydir",
        "rm --force file.txt",
        "cp -f src dst",
        "cp -rf srcdir dstdir",
        "mv -f old new",
        "mv --force old new",
        "/bin/rm -f file.txt",
    ],
)
def test_allows_command_with_force(tool_use, assert_allows, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_safe_compound(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "ls && rm -f foo && echo done"})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: unrelated commands
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "ls -la",
        "git status",
        "echo rm",  # rm as argument, not invocation
        "python3 script.py",
        "grep -r 'rm' .",
        "remote=$(git remote)",  # rm appears inside word but not as command
        "trim_whitespace",  # word containing 'rm' but not the command
    ],
)
def test_allows_unrelated_commands(tool_use, assert_allows, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Allow: unrelated tools
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool_name", ["Write", "Edit", "Read", "Grep"])
def test_allows_unrelated_tools(tool_use, assert_allows, tool_name):
    # Arrange
    payload = tool_use(tool_name, {"file_path": "/tmp/x"})

    # Act / Assert
    assert_allows(HOOK, payload)


# ---------------------------------------------------------------------------
# Bypass + robustness
# ---------------------------------------------------------------------------


def test_bypass_env_var_disables_check(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "rm file.txt"})

    # Act / Assert
    assert_allows(HOOK, payload, env={"INTERACTIVE_CMD_DISABLE": "1"})


def test_handles_empty_command(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": ""})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_handles_malformed_shell(tool_use, assert_allows):
    # Arrange: unterminated quote
    payload = tool_use("Bash", {"command": "echo 'unterminated"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_handles_env_var_prefix(tool_use, assert_blocks):
    # Arrange: env var prefix before the command should not hide it
    payload = tool_use("Bash", {"command": "FOO=bar rm file.txt"})

    # Act / Assert
    assert_blocks(HOOK, payload)
