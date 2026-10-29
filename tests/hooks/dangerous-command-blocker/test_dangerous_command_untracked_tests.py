from __future__ import annotations

import subprocess
from pathlib import Path

from faker import Faker

HOOK = "dangerous-command-blocker"
TEST_DELETION = "CONFIRM REQUIRED: Deleting a test file removes coverage"

fake = Faker()
Faker.seed(7219)


def _repo_with(tmp_path: Path, committed: str, untracked: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (
        ["init", "-q"],
        ["config", "user.email", f"{fake.user_name()}@repo.test"],
        ["config", "user.name", fake.name()],
        ["config", "commit.gpgsign", "false"],
    ):
        subprocess.run(["git", "-C", str(repo), *args], check=True, timeout=30)
    (repo / committed).write_text("test()\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", committed], check=True, timeout=30)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "add"], check=True, timeout=30
    )
    (repo / untracked).write_text("test()\n", encoding="utf-8")
    return repo


def test_removing_a_spec_no_commit_holds_raises_no_prompt(tmp_path, tool_use, run_hook):
    # Arrange
    repo = _repo_with(tmp_path, "orders.test.ts", "capture.spec.ts")
    payload = tool_use("Bash", {"command": "rm -f capture.spec.ts"}, cwd=str(repo))

    # Act
    code, stdout, _stderr = run_hook(HOOK, payload)

    # Assert
    assert (code, TEST_DELETION in stdout) == (0, False)


def test_removing_a_committed_test_alongside_an_untracked_one_still_asks(
    tmp_path, tool_use, run_hook
):
    # Arrange
    repo = _repo_with(tmp_path, "orders.test.ts", "capture.spec.ts")
    payload = tool_use(
        "Bash", {"command": "rm capture.spec.ts orders.test.ts"}, cwd=str(repo)
    )

    # Act
    code, stdout, _stderr = run_hook(HOOK, payload)

    # Assert
    assert code == 0
    assert TEST_DELETION in stdout
