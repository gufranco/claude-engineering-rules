from __future__ import annotations

import json

import pytest

HOOK = "dangerous-command-blocker"
TEST_DELETION = "CONFIRM REQUIRED: Deleting a test file removes coverage"
WIDE_SEARCH = "CONFIRM REQUIRED: Searching the whole filesystem or home directory"


def _context(stdout: str) -> str:
    return json.loads(stdout)["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize(
    "command",
    [
        "rm src/orders.test.ts",
        "git rm tests/test_orders.py",
        "rm -f internal/orders_test.go",
        "rm -rf src/__tests__/",
        "unlink spec/orders.spec.js",
    ],
)
def test_deleting_a_test_file_asks_for_confirmation(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    code, stdout, _stderr = run_hook(HOOK, payload)

    # Assert
    assert code == 0
    assert TEST_DELETION in _context(stdout)


@pytest.mark.parametrize(
    "command",
    [
        "rm src/orders.ts",
        "rm latest_tests.txt",
        "git mv tests/test_a.py tests/test_b.py",
        'docker run --rm -v "$PWD:/work" img python3 patch.retail.test.py',
        "podman run --rm=true img sh -c 'python3 tests/test_api.py'",
    ],
)
def test_other_deletions_and_moves_raise_no_test_prompt(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    code, stdout, _stderr = run_hook(HOOK, payload)

    # Assert
    assert code == 0
    assert TEST_DELETION not in stdout


@pytest.mark.parametrize(
    ("command", "absent"),
    [
        (
            'docker run --rm img sh -c "ls" ; python3 "$HOME/.claude/scripts/x.py" list',
            "Deleting .claude/",
        ),
        ("docker run --rm img sh -c 'ls *.py'", "rm with wildcard"),
    ],
)
def test_a_container_rm_flag_is_not_an_rm_command(tool_use, run_hook, command, absent):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    code, stdout, stderr = run_hook(HOOK, payload)

    # Assert
    assert (code, absent in stdout + stderr) == (0, False)


def test_a_real_rm_after_a_container_rm_flag_still_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash", {"command": "docker run --rm img ls && rm -rf ~/.claude"}
    )

    # Act
    code, _stdout, stderr = run_hook(HOOK, payload)

    # Assert
    assert (code, "Deleting .claude/" in stderr) == (2, True)


@pytest.mark.parametrize(
    "command",
    [
        "find / -name settings.json",
        "find ~ -name '*.pem'",
        'grep -rn token "$HOME"',
        "rg password /",
        "fd config ~/",
    ],
)
def test_searching_root_or_home_asks_for_confirmation(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    code, stdout, _stderr = run_hook(HOOK, payload)

    # Assert
    assert code == 0
    assert WIDE_SEARCH in _context(stdout)


@pytest.mark.parametrize(
    "command",
    [
        "find . -name '*.py'",
        "rg token ~/project/src",
        "grep -rn '/' src",
        "grep token /etc/hosts",
        "fd config $HOME/.config",
    ],
)
def test_scoped_searches_raise_no_prompt(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    code, stdout, _stderr = run_hook(HOOK, payload)

    # Assert
    assert code == 0
    assert WIDE_SEARCH not in stdout
