"""Coverage for the pr-merge-blocker hook.

Source rule: skills/morning/SKILL.md. The hook blocks pull request merges
only while a `morning` session lock is live, so `/deploy land` keeps working
outside a sweep.

The allow-path tests carry the same weight as the block-path tests. A lock
that swallowed `git merge` would break conflict resolution, and a lock that
swallowed `gh pr update-branch` would break the branch-update lane the same
skill depends on.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402
from _lib.session_lock import acquire  # noqa: E402

_TESTS_DIR = ROOT / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _helpers.cov_env import apply_coverage_env  # noqa: E402

HOOK = "pr-merge-blocker"


@pytest.fixture()
def locked(tmp_path: Path) -> dict[str, str]:
    state = tmp_path / ".session-locks.json"
    acquire("morning", ttl_seconds=300, reason="test", state_path=state)
    return {"CLAUDE_SESSION_LOCK_STATE": str(state)}


@pytest.fixture()
def unlocked(tmp_path: Path) -> dict[str, str]:
    state = tmp_path / ".session-locks.json"
    return {"CLAUDE_SESSION_LOCK_STATE": str(state)}


MERGE_COMMANDS = [
    "gh pr merge 123",
    "gh pr merge 123 --squash",
    "gh pr merge --rebase --delete-branch",
    "GH_TOKEN=$(gh auth token --user gufranco) gh pr merge 42 --merge",
    "gh pr merge --auto --squash 7",
    "glab mr merge 45",
    "glab mr merge !45 --yes",
    "gh api --method PUT repos/owner/repo/pulls/1/merge",
    "gh api -X PUT repos/owner/repo/pulls/1/merge",
    "gh api graphql -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }'",
    "gh api graphql -f query='mutation { enablePullRequestAutoMerge(input: {}) { number } }'",
    "glab api --method PUT projects/9/merge_requests/3/merge",
    "curl -X POST https://api.bitbucket.org/2.0/repositories/o/r/pullrequests/5/merge",
]


ALLOWED_COMMANDS = [
    "gh pr view 123",
    "gh pr list --state open",
    "gh pr diff 123",
    "gh pr review 123 --approve",
    "gh pr review 123 --comment --body 'looks good'",
    "gh pr update-branch 123",
    "gh pr checks 123",
    "gh pr comment 123 --body 'ping'",
    "git merge origin/main",
    "git merge --abort",
    "git merge-base origin/main HEAD",
    "git rebase origin/main",
    "glab mr view 45",
    "glab mr list",
    "gh pr merge --help",
]


class TestBlocksWhileLocked:
    @pytest.mark.parametrize("command", MERGE_COMMANDS)
    def test_blocks_every_merge_form(
        self, command: str, tool_use, assert_blocks, locked: dict[str, str]
    ) -> None:
        payload = tool_use("Bash", {"command": command})

        assert_blocks(HOOK, payload, "merge", env=locked)

    def test_block_message_names_the_skill(
        self, tool_use, assert_blocks, locked: dict[str, str]
    ) -> None:
        payload = tool_use("Bash", {"command": "gh pr merge 1"})

        _code, stderr = assert_blocks(HOOK, payload, env=locked)

        assert "morning" in stderr

    def test_blocks_a_merge_chained_behind_a_safe_command(
        self, tool_use, assert_blocks, locked: dict[str, str]
    ) -> None:
        payload = tool_use("Bash", {"command": "gh pr view 1 && gh pr merge 1"})

        assert_blocks(HOOK, payload, env=locked)

    def test_blocks_when_the_lock_file_is_corrupt(
        self, tool_use, assert_blocks, tmp_path: Path
    ) -> None:
        state = tmp_path / ".session-locks.json"
        state.write_text("{not json", encoding="utf-8")
        payload = tool_use("Bash", {"command": "gh pr merge 1"})

        assert_blocks(HOOK, payload, env={"CLAUDE_SESSION_LOCK_STATE": str(state)})


class TestAllowsWhileLocked:
    @pytest.mark.parametrize("command", ALLOWED_COMMANDS)
    def test_allows_non_merge_commands(
        self, command: str, tool_use, assert_allows, locked: dict[str, str]
    ) -> None:
        payload = tool_use("Bash", {"command": command})

        assert_allows(HOOK, payload, env=locked)

    def test_allows_an_empty_command(
        self, tool_use, assert_allows, locked: dict[str, str]
    ) -> None:
        payload = tool_use("Bash", {"command": ""})

        assert_allows(HOOK, payload, env=locked)

    def test_allows_a_non_bash_tool(
        self, tool_use, assert_allows, locked: dict[str, str]
    ) -> None:
        payload = tool_use("Read", {"file_path": "/tmp/x"})

        assert_allows(HOOK, payload, env=locked)


class TestAllowsWhileUnlocked:
    @pytest.mark.parametrize("command", MERGE_COMMANDS)
    def test_deploy_can_merge_with_no_session(
        self, command: str, tool_use, assert_allows, unlocked: dict[str, str]
    ) -> None:
        payload = tool_use("Bash", {"command": command})

        assert_allows(HOOK, payload, env=unlocked)

    def test_expired_lock_stops_blocking(
        self, tool_use, assert_allows, tmp_path: Path
    ) -> None:
        state = tmp_path / ".session-locks.json"
        state.write_text(
            '{"version": 1, "locks": [{"lock": "morning", '
            '"expires_at": "2020-01-01T00:00:00+00:00"}]}',
            encoding="utf-8",
        )
        payload = tool_use("Bash", {"command": "gh pr merge 1"})

        assert_allows(HOOK, payload, env={"CLAUDE_SESSION_LOCK_STATE": str(state)})


class TestBypass:
    def test_env_var_disables_the_hook(
        self, tool_use, assert_allows, locked: dict[str, str]
    ) -> None:
        payload = tool_use("Bash", {"command": "gh pr merge 1"})

        assert_allows(HOOK, payload, env={**locked, "PR_MERGE_BLOCKER_DISABLE": "1"})

    def test_file_registry_bypass_disables_the_hook(
        self, tool_use, assert_allows, locked: dict[str, str], tmp_path: Path
    ) -> None:
        bypass_state = tmp_path / ".bypass-state.json"
        set_bypass(HOOK, ttl_seconds=120, state_path=bypass_state)
        payload = tool_use("Bash", {"command": "gh pr merge 1"})

        assert_allows(
            HOOK, payload, env={**locked, "CLAUDE_BYPASS_STATE": str(bypass_state)}
        )

    def test_profile_disable_makes_the_hook_inert(
        self, tool_use, assert_allows, locked: dict[str, str]
    ) -> None:
        payload = tool_use("Bash", {"command": "gh pr merge 1"})

        assert_allows(HOOK, payload, env={**locked, "CLAUDE_DISABLED_HOOKS": HOOK})


class TestMalformedInput:
    def test_invalid_json_on_stdin_allows(self, locked: dict[str, str]) -> None:
        hook = ROOT / "hooks" / f"{HOOK}.py"
        env = apply_coverage_env({**os.environ, **locked})

        proc = subprocess.run(
            [sys.executable, str(hook)],
            input="{not json",
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            check=False,
        )

        assert proc.returncode == 0
