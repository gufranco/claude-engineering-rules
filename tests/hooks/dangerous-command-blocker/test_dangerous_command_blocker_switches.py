from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

ROOT = Path(__file__).resolve().parents[3]
HOOK = "dangerous-command-blocker"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

ROOT_DELETE = "rm -rf /"


@pytest.mark.parametrize(
    "env",
    [
        {"DANGEROUS_COMMAND_BLOCKER_DISABLE": "1"},
        {"CLAUDE_DISABLED_HOOKS": HOOK},
    ],
)
def test_an_explicit_switch_turns_the_blocker_off(env, tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": ROOT_DELETE})

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert_allowed(result)


def test_a_live_bypass_entry_turns_the_blocker_off(tmp_path, tool_use, run_hook):
    # Arrange
    state = tmp_path / "bypass.json"
    set_bypass(HOOK, ttl_seconds=120, state_path=state)
    payload = tool_use("Bash", {"command": ROOT_DELETE})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    assert_allowed(result)


@pytest.fixture()
def solo_home(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "solo-repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "solo-repos.txt").write_text(f"{repo}\n", encoding="utf-8")
    return home, repo


def test_a_push_to_main_in_a_listed_solo_repo_is_allowed(solo_home, tool_use, run_hook):
    # Arrange
    home, repo = solo_home
    payload = tool_use("Bash", {"command": f"git -C {repo} push origin main"})

    # Act
    result = run_hook(HOOK, payload, env={"HOME": str(home)})

    # Assert
    assert_allowed(result)


def test_a_push_to_main_in_an_unlisted_repo_is_blocked(
    solo_home, tmp_path, tool_use, run_hook
):
    # Arrange
    home, _repo = solo_home
    other = tmp_path / "team-repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(other)], check=True)
    payload = tool_use("Bash", {"command": f"git -C {other} push origin main"})

    # Act
    result = run_hook(HOOK, payload, env={"HOME": str(home)})

    # Assert
    assert_blocked(result, "Direct push to protected branch")


def test_a_nested_push_to_main_skips_the_solo_allowance(solo_home, tool_use, run_hook):
    # Arrange
    home, repo = solo_home
    payload = tool_use(
        "Bash", {"command": f"cd {repo} && bash -c 'git push origin main'"}
    )

    # Act
    result = run_hook(HOOK, payload, env={"HOME": str(home)})

    # Assert
    assert_blocked(result, "Direct push to protected branch")


def test_an_env_bypass_lets_a_protected_push_through(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "git -C /tmp/x push origin main"})

    # Act
    result = run_hook(HOOK, payload, env={"ALLOW_PROTECTED_BRANCH_PUSH": "1"})

    # Assert
    assert_allowed(result)
