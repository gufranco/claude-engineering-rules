from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

from _helpers.cov_env import apply_coverage_env  # noqa: E402

HOOK = "ai-process-leak-blocker"


GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


PLANNING_TEXT = "# Phase 1: scaffolding\n\nMaps to canvas region 2.\n"


def make_repo(root: Path) -> Path:
    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=root,
        check=True,
        capture_output=True,
        env={**os.environ, **GIT_ENV},
        timeout=30,
    )
    return root


def write_payload(tool_use, path: Path) -> dict:
    return tool_use("Write", {"file_path": str(path), "content": PLANNING_TEXT})


def test_allows_write_into_the_local_workspace(tool_use, run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path)
    target = repo / "docs" / "plans" / "x" / "plan.md"

    # Act
    result = run_hook(HOOK, write_payload(tool_use, target), env=GIT_ENV)

    # Assert
    assert_allowed(result)


def test_allows_write_into_the_fallback_workspace(tool_use, run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "index.md").write_text("# Project docs\n")
    target = repo / ".work" / "PROMPT.md"

    # Act
    result = run_hook(HOOK, write_payload(tool_use, target), env=GIT_ENV)

    # Assert
    assert_allowed(result)


def test_blocks_write_into_a_project_owned_docs(tool_use, run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "index.md").write_text("# Project docs\n")
    target = repo / "docs" / "guide.md"

    # Act
    result = run_hook(HOOK, write_payload(tool_use, target), env=GIT_ENV)

    # Assert
    assert_blocked(result, "Phase")


def test_blocks_write_outside_a_repository(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "docs" / "notes.md"

    # Act
    result = run_hook(HOOK, write_payload(tool_use, target), env=GIT_ENV)

    # Assert
    assert_blocked(result, "Phase")


def test_blocks_workspace_write_when_git_is_missing(tool_use, run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path)
    target = repo / "docs" / "PROMPT.md"
    env = {**GIT_ENV, "PATH": str(tmp_path / "empty")}

    # Act
    result = run_hook(HOOK, write_payload(tool_use, target), env=env)

    # Assert
    assert_blocked(result, "Phase")


@pytest.mark.parametrize(
    "message",
    [
        "Context lives in docs/PROMPT.md",
        "see .work/plans/2026-09-30-x for details",
        "details in ./docs/plans/",
    ],
)
def test_blocks_a_commit_naming_the_workspace(tool_use, run_hook, message):
    # Arrange
    payload = tool_use("Bash", {"command": f'git commit -m "{message}"'})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "workspace")


def test_allows_a_commit_naming_project_docs(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": 'git commit -m "docs: update docs/api.md"'})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_a_quoted_body_file_with_a_leak(tmp_path, tool_use, run_hook):
    # Arrange
    body = tmp_path / "body.md"
    body.write_text("Phase 3 landed.\n", encoding="utf-8")
    command = f"gh pr create --title fix --body-file '{body}'"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "Phase")


def test_allows_an_empty_body_file_value(tool_use, run_hook):
    # Arrange
    command = "gh pr create --title fix --body-file ''"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.skipif(
    os.geteuid() == 0, reason="root reads files without permission bits"
)
def test_allows_an_unreadable_body_file(tmp_path, tool_use, run_hook):
    # Arrange
    body = tmp_path / "locked.md"
    body.write_text("Phase 3 landed.\n", encoding="utf-8")
    body.chmod(0)
    command = f"gh pr create --title fix --body-file {body}"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_edit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Edit", {"file_path": "/repo/src/app.ts", "new_string": 7})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: ai-process-leak-blocker could not read its input: tool_input.new_string is not",
    )


def test_multiedit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    edits = [{"old_string": "a", "new_string": 7}, "not an edit"]
    payload = tool_use("MultiEdit", {"file_path": "/repo/src/app.ts", "edits": edits})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: ai-process-leak-blocker could not read its input: tool_input.edits is not a",
    )


def test_malformed_payload_blocks():
    # Arrange
    hook = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input="not json",
        capture_output=True,
        text=True,
        env=apply_coverage_env({**os.environ, "CLAUDE_BYPASS_STATE": os.devnull}),
        check=False,
        timeout=30,
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr
