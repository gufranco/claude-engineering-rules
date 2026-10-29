from __future__ import annotations

import json
import sys
from pathlib import Path

from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.pr_session_ledger import record  # noqa: E402

HOOK = "pr-comment-discipline"
NOW = 1_800_000_000.0

fake = Faker()
Faker.seed(5005)


def _decision(stdout: str) -> dict[str, str]:
    return json.loads(stdout)["hookSpecificOutput"]


def _create(tool_use, session: str, repo: str = "acme/overwatch"):
    command = f"gh pr create --repo {repo} -t 'feat: x' -b body"
    return tool_use("Bash", {"command": command}, session_id=session)


def test_a_second_pr_in_the_same_repository_asks_first(tmp_path, tool_use, run_hook):
    # Arrange
    session = fake.uuid4()
    record(session, "https://github.com/acme/overwatch/pull/671\n", tmp_path, NOW)

    # Act
    result = run_hook(
        HOOK, _create(tool_use, session), env={"CLAUDE_PR_LEDGER_DIR": str(tmp_path)}
    )

    # Assert
    decision = _decision(result.stdout)
    assert (result.code, decision["permissionDecision"]) == (0, "ask")
    assert "already opened acme/overwatch#671" in decision["permissionDecisionReason"]
    assert "cherry-pick" in decision["permissionDecisionReason"]


def test_the_first_pr_or_another_repository_passes_silently(
    tmp_path, tool_use, run_hook
):
    # Arrange
    session = fake.uuid4()
    record(session, "https://github.com/acme/overwatch/pull/671\n", tmp_path, NOW)
    env = {"CLAUDE_PR_LEDGER_DIR": str(tmp_path)}
    payloads = [
        _create(tool_use, fake.uuid4()),
        _create(tool_use, session, repo="acme/onyx_fullstack"),
    ]

    # Act
    results = [run_hook(HOOK, payload, env=env) for payload in payloads]

    # Assert
    assert [(r.code, r.stdout, r.stderr) for r in results] == [(0, "", "")] * 2


def test_an_unreadable_ledger_asks_instead_of_passing(tmp_path, tool_use, run_hook):
    # Arrange
    session = fake.uuid4()
    (tmp_path / f"{session}.json").write_text("{broken", encoding="utf-8")

    # Act
    result = run_hook(
        HOOK, _create(tool_use, session), env={"CLAUDE_PR_LEDGER_DIR": str(tmp_path)}
    )

    # Assert
    decision = _decision(result.stdout)
    assert decision["permissionDecision"] == "ask"
    assert (
        "could not read the pull-request ledger"
        in (decision["permissionDecisionReason"])
    )
