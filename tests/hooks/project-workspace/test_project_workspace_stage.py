from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.cov_env import apply_coverage_env  # noqa: E402
from _ppw_support import (
    GIT_ENV,
    HOOK,
    bash,
    make_repo,
    start,
)


@pytest.mark.parametrize(
    "command",
    [
        "git add -f docs/PROMPT.md",
        "git add --force docs",
        "git add -fA",
        "git add -f .",
        "git -C . add -f -- docs/research.md",
        "npm test && git add -f 'docs/*.md'",
        "git stage --force docs/plans",
        "GIT_TRACE=0 git add -f docs",
        "git add -f :/",
    ],
)
def test_stage_blocks_a_forced_add_of_the_workspace(
    run_hook, tool_use, tmp_path, command
):
    # Arrange
    repo = make_repo(tmp_path / "project")
    start(run_hook, repo)

    # Act
    code, _, stderr = bash(run_hook, tool_use, repo, command)

    # Assert
    assert code == 2
    assert "docs/" in stderr


@pytest.mark.parametrize(
    "command",
    [
        "git add -f src/main.py",
        "git add -A",
        "git status",
        "echo git add -f docs",
        "FOO=1",
        "git -C",
        "echo 'unterminated",
        "",
    ],
)
def test_stage_allows_other_commands(run_hook, tool_use, tmp_path, command):
    # Arrange
    repo = make_repo(tmp_path / "project")
    start(run_hook, repo)

    # Act
    code, _, _ = bash(run_hook, tool_use, repo, command)

    # Assert
    assert code == 0


def test_stage_blocks_a_forced_add_from_inside_the_workspace(
    run_hook, tool_use, tmp_path
):
    # Arrange
    repo = make_repo(tmp_path / "project")
    start(run_hook, repo)
    (repo / "docs").mkdir()

    # Act
    code, _, _ = bash(run_hook, tool_use, repo / "docs", "git add -f PROMPT.md")

    # Assert
    assert code == 2


def test_stage_blocks_a_forced_add_when_git_fails(run_hook, tool_use, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")

    # Act
    code, _, stderr = bash(
        run_hook, tool_use, repo, "git add -f docs", env={"PATH": str(tmp_path)}
    )

    # Assert
    assert code == 2
    assert "could not" in stderr


def test_stage_blocks_an_unparseable_forced_add(run_hook, tool_use, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    start(run_hook, repo)

    # Act
    code, _, _ = bash(run_hook, tool_use, repo, "git add -f 'docs/PROMPT.md")

    # Assert
    assert code == 2


def test_stage_allows_outside_a_repository(run_hook, tool_use, tmp_path):
    # Arrange
    command = "git add -f docs"

    # Act
    code, _, _ = bash(run_hook, tool_use, tmp_path, command)

    # Assert
    assert code == 0


def test_env_bypass_skips_every_event(run_hook, tool_use, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    start(run_hook, repo)

    # Act
    code, _, _ = bash(
        run_hook,
        tool_use,
        repo,
        "git add -f docs",
        env={"PROJECT_WORKSPACE_DISABLE": "1"},
    )

    # Assert
    assert code == 0


@pytest.mark.parametrize("raw", ["not json", "[]"])
def test_malformed_payload_blocks(raw):
    # Arrange
    hook = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=raw,
        capture_output=True,
        text=True,
        env=apply_coverage_env(
            {**os.environ, "CLAUDE_BYPASS_STATE": os.devnull, **GIT_ENV}
        ),
        check=False,
        timeout=30,
    )

    # Assert
    assert proc.returncode == 2


def test_non_dict_tool_input_blocks(run_hook, tmp_path):
    # Arrange
    repo = make_repo(tmp_path / "project")
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": "git add -f docs",
        "cwd": str(repo),
    }

    # Act
    code, _, _ = run_hook(HOOK, payload, env=GIT_ENV)

    # Assert
    assert code == 2
