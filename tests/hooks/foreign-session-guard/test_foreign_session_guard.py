from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from faker import Faker

HOOK = "foreign-session-guard"

fake = Faker()
Faker.seed(4413)


def _sessions(tmp_path: Path, cwd: Path, session: str) -> dict[str, str]:
    folder = tmp_path / "sessions"
    folder.mkdir()
    record = {
        "pid": os.getpid(),
        "sessionId": session,
        "cwd": str(cwd),
        "name": "dotfiles-3c",
        "status": "busy",
    }
    (folder / "1.json").write_text(json.dumps(record), "utf-8")
    return {"CLAUDE_SESSIONS_DIR": str(folder)}


def _trees(tmp_path: Path) -> tuple[Path, Path]:
    mine, theirs = tmp_path / "claude", tmp_path / "dotfiles"
    mine.mkdir()
    theirs.mkdir()
    return mine, theirs


@pytest.mark.parametrize(
    ("tool", "key"),
    [("Write", "file_path"), ("Edit", "file_path"), ("NotebookEdit", "notebook_path")],
)
def test_a_write_into_another_live_session_tree_is_handed_off(
    tmp_path, tool_use, run_hook, tool, key
):
    # Arrange
    mine, theirs = _trees(tmp_path)
    env = _sessions(tmp_path, theirs, fake.uuid4())
    payload = tool_use(
        tool, {key: str(theirs / ".releaserc.json")}, cwd=str(mine), session_id="me"
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    decision = json.loads(result.stdout)["hookSpecificOutput"]
    reason = decision["permissionDecisionReason"]
    assert (result.code, decision["permissionDecision"]) == (0, "deny")
    assert "Give the user a prompt to paste into session dotfiles-3c" in reason
    assert str(theirs) in reason


def test_a_write_into_the_shared_vault_passes_while_another_session_works_there(
    tmp_path, tool_use, run_hook
):
    # Arrange
    mine, vault = _trees(tmp_path)
    env = {**_sessions(tmp_path, vault, fake.uuid4()), "SECOND_BRAIN_VAULT": str(vault)}
    target = vault / "wiki" / f"{fake.word()}.md"
    payload = tool_use(
        "Write", {"file_path": str(target)}, cwd=str(mine), session_id="me"
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert (result.code, result.stdout) == (0, "")


def test_a_write_in_this_session_tree_passes_silently(tmp_path, tool_use, run_hook):
    # Arrange
    mine, theirs = _trees(tmp_path)
    env = _sessions(tmp_path, theirs, fake.uuid4())
    payload = tool_use(
        "Write", {"file_path": str(mine / "a.md")}, cwd=str(mine), session_id="me"
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert (result.code, result.stdout, result.stderr) == (0, "", "")


def test_a_bash_call_or_a_missing_path_passes_silently(tmp_path, tool_use, run_hook):
    # Arrange
    mine, theirs = _trees(tmp_path)
    env = _sessions(tmp_path, theirs, fake.uuid4())
    payloads = [
        tool_use("Bash", {"command": f"touch {theirs}/x"}, cwd=str(mine)),
        tool_use("Write", {"content": "x"}, cwd=str(mine), session_id="me"),
    ]

    # Act
    results = [run_hook(HOOK, payload, env=env) for payload in payloads]

    # Assert
    assert [(r.code, r.stdout) for r in results] == [(0, "")] * 2


def test_the_disable_variable_lets_the_write_through(tmp_path, tool_use, run_hook):
    # Arrange
    mine, theirs = _trees(tmp_path)
    env = {
        **_sessions(tmp_path, theirs, fake.uuid4()),
        "FOREIGN_SESSION_GUARD_DISABLE": "1",
    }
    payload = tool_use(
        "Write", {"file_path": str(theirs / "a")}, cwd=str(mine), session_id="me"
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert (result.code, result.stdout) == (0, "")


def test_a_hook_profile_that_disables_the_guard_lets_the_write_through(
    tmp_path, tool_use, run_hook
):
    # Arrange
    mine, theirs = _trees(tmp_path)
    env = {
        **_sessions(tmp_path, theirs, fake.uuid4()),
        "CLAUDE_DISABLED_HOOKS": HOOK,
    }
    payload = tool_use(
        "Write", {"file_path": str(theirs / "a")}, cwd=str(mine), session_id="me"
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    assert (result.code, result.stdout) == (0, "")
