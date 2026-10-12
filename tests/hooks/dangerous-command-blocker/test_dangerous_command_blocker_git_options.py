from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

TESTS_ROOT = Path(__file__).resolve().parents[2]
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
from _helpers.cov_env import apply_coverage_env  # noqa: E402

HOOK = "dangerous-command-blocker"
HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
FORCE = "--" + "force"
SHORT_FORCE = "-" + "f"
UNREADABLE = "BLOCKED: dangerous-command-blocker could not read"


def _run_raw(stdin: str) -> subprocess.CompletedProcess[str]:
    env = apply_coverage_env(dict(os.environ))
    env["CLAUDE_BYPASS_STATE"] = os.devnull
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )


@pytest.mark.parametrize(
    "command",
    [
        f"git -C /tmp/x push {FORCE} origin main",
        f'git -C "/tmp/my repo" push {FORCE} origin feat',
        f"git -c core.x=y push {FORCE} origin feat",
        f"git --git-dir=/x/.git push {FORCE} origin feat",
        f"git --work-tree /x push {FORCE} origin feat",
        f"git --no-pager push {FORCE}",
        f"cd /tmp && git -C /x push {FORCE} origin feat",
    ],
)
def test_long_force_behind_global_options_is_blocked(command, tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Use --force-with-lease instead of --force")


@pytest.mark.parametrize(
    "command",
    [
        f"git push {SHORT_FORCE} origin feat",
        f"git push {SHORT_FORCE}",
        f"git push origin feat {SHORT_FORCE}",
        f"git push {SHORT_FORCE}u origin feat",
        f"git push -u{SHORT_FORCE[1:]} origin feat",
        f"git -c core.x=y push {SHORT_FORCE} origin main",
        f"git -C /tmp/x push {SHORT_FORCE} origin feat",
    ],
)
def test_short_force_after_push_is_blocked(command, tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Use --force-with-lease instead of -f")


@pytest.mark.parametrize(
    "command",
    [
        f"git push {FORCE}-with-lease origin feat",
        f"git -C /tmp/x push {FORCE}-with-lease origin feat",
        f"git push {FORCE}-with-lease {FORCE}-if-includes origin feat",
        "git push origin feat",
        "git push -u origin feat",
        "git -C /tmp/x status",
        "git -c color.ui=never log --oneline -3",
        "git push origin feat && rm -f stale.log",
    ],
)
def test_safe_push_and_read_only_calls_are_allowed(command, tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_protected_branch_push_behind_global_option_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git -C /tmp/x push origin main"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Direct push to protected branch")


def test_reset_hard_behind_global_option_asks_for_confirmation(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git -C /tmp/x reset --hard HEAD~1"})

    # Act
    code, _stdout, stderr = run_hook(HOOK, payload)

    # Assert
    assert code == 0
    assert "CONFIRM REQUIRED: git reset --hard" in stderr


def test_filter_branch_behind_global_option_is_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git -c a=b filter-branch HEAD"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "git filter-branch rewrites history")


def test_block_message_shows_the_command_as_typed(tool_use, run_hook):
    # Arrange
    command = f"git -C /tmp/x push {FORCE} origin feat"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result)
    assert f"Command: {command}" in stderr


@pytest.mark.parametrize("stdin", ["not valid json", "", "[1, 2]", '"text"'])
def test_unparsable_input_is_blocked(stdin):
    # Arrange
    stdin_input = stdin

    # Act
    proc = _run_raw(stdin_input)

    # Assert
    assert proc.returncode == 2
    assert UNREADABLE in proc.stderr


def test_input_that_is_not_utf8_is_blocked():
    # Arrange
    env = apply_coverage_env(dict(os.environ))
    env["CLAUDE_BYPASS_STATE"] = os.devnull

    # Act
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=b"\xff\xfe\x00not utf8",
        capture_output=True,
        env=env,
        timeout=6.0,
        check=False,
    )

    # Assert
    assert proc.returncode == 2
    assert UNREADABLE.encode() in proc.stderr


@pytest.mark.parametrize(
    "payload",
    [
        '{"tool_name": "Bash", "tool_input": []}',
        '{"tool_name": "Bash", "tool_input": {"command": 7}}',
    ],
)
def test_a_malformed_tool_input_is_blocked(payload):
    # Arrange
    payload_input = payload

    # Act
    proc = _run_raw(payload_input)

    # Assert
    assert proc.returncode == 2
    assert UNREADABLE in proc.stderr


def test_a_payload_without_a_command_is_allowed(tool_use, run_hook):
    # Arrange
    payload = tool_use("Read", {"file_path": "/tmp/x"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def _load_module():
    import importlib.util

    if str(HOOK_PATH.parent) not in sys.path:
        sys.path.insert(0, str(HOOK_PATH.parent))
    spec = importlib.util.spec_from_file_location("_dcb_git_options", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git -C /tmp/x push origin main", "/tmp/x"),
        ('git -C "/tmp/my repo" push origin main', "/tmp/my repo"),
        ("cd /a && git -C b push origin main", "/a/b"),
        ("git -c a=b -C /x push", "/x"),
        ("git -C /a -C b push", "/a/b"),
        ("cd /a && git push origin main", "/a"),
        ("git push origin main", ""),
        ("git -C /x status && git push origin main", ""),
    ],
)
def test_push_cwd_follows_cd_and_dash_c(command, expected):
    # Arrange
    module = _load_module()

    # Act
    resolved = module._push_cwd(command)

    # Assert
    assert resolved == expected


@pytest.mark.parametrize(
    "command",
    [
        "git --git-dir=/x/.git push origin main",
        "git --git-dir /x/.git push origin main",
        "git --work-tree=/x push origin main",
        "git -C /x --work-tree /y push origin main",
        "bash -c 'git -C /x push origin main'",
        "cd /a && sh -c 'git push origin main'",
    ],
)
def test_push_cwd_is_unknown_when_git_is_pointed_elsewhere(command):
    # Arrange
    module = _load_module()

    # Act
    resolved = module._push_cwd(command)

    # Assert
    assert resolved is None
