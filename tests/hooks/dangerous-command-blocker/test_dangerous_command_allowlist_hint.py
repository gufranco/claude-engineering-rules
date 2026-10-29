from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from faker import Faker

HOOKS_DIR = Path(__file__).resolve().parents[3] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.dangerous_command_verdicts import allowlist_hint  # noqa: E402

HOOK = "dangerous-command-blocker"
PUSH = "pu" + "sh"

fake = Faker()
Faker.seed(6117)


def test_the_hint_names_the_resolved_path_to_append():
    # Arrange
    top = f"/private/var/folders/{fake.word()}/repo"

    # Act
    result = allowlist_hint(top)

    # Assert
    assert f"  echo '{top}' >> ~/.claude/solo-repos.txt\n" in result


def test_without_a_repository_the_hint_stays_generic():
    # Arrange
    top = ""

    # Act
    result = allowlist_hint(top)

    # Assert
    assert result == (
        "Solo repo with no PR workflow? Add it to ~/.claude/solo-repos.txt "
        "once instead of bypassing on every push.\n"
    )


def test_a_blocked_protected_push_prints_the_line_to_append(
    tmp_path, tool_use, run_hook
):
    # Arrange
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)], check=True, timeout=30
    )
    top = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()
    payload = tool_use("Bash", {"command": f"git -C {repo} {PUSH} origin HEAD:main"})

    # Act
    result = run_hook(HOOK, payload, env={"HOME": str(tmp_path), **_no_bypass()})

    # Assert
    assert result.code == 2
    assert f"echo '{top}' >> ~/.claude/solo-repos.txt" in result.stderr


def _no_bypass() -> dict[str, str]:
    return {key: "" for key in ("ALLOW_PROTECTED_BRANCH_PUSH",) if key in os.environ}
