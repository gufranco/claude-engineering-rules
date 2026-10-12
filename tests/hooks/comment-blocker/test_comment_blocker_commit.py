from __future__ import annotations

import subprocess
import os
import json
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))

from git_repo_fixture import GitRepo, new_git_repo  # noqa: E402

HOOK = "comment-blocker"
BLOCK_MSG = "comment added to source"


@pytest.fixture
def repo(tmp_path: Path) -> GitRepo:
    return new_git_repo(tmp_path)


def commit_payload(tool_use, repo: GitRepo, command: str = "git commit -m x"):
    return tool_use("Bash", {"command": command}, cwd=str(repo.root))


def test_blocks_a_comment_staged_through_bash(tool_use, run_hook, repo):
    # Arrange
    repo.stage("src/app.py", "x = 1  # explain\n")

    # Act
    result = run_hook(HOOK, commit_payload(tool_use, repo))

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert "src/app.py (staged for commit" in stderr


def test_blocks_a_docstring_staged_through_bash(tool_use, run_hook, repo):
    # Arrange
    repo.stage("src/app.py", "x = 1\n")
    repo.commit()
    repo.stage("src/app.py", 'def f():\n    """Explain."""\n    return 1\n')

    # Act
    result = run_hook(HOOK, commit_payload(tool_use, repo))

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert 'L2: """Explain."""' in stderr


def test_allows_a_comment_that_head_already_holds(tool_use, run_hook, repo):
    # Arrange
    repo.stage("app.sh", "# legacy\necho 1\n")
    repo.commit()
    repo.stage("app.sh", "# legacy\necho 2\n")

    # Act
    result = run_hook(HOOK, commit_payload(tool_use, repo))

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


def test_allows_bare_markers_in_a_staged_test(tool_use, run_hook, repo):
    # Arrange
    repo.stage(
        "tests/test_a.py",
        "def test_a():\n    # Arrange\n    x = 1\n\n    # Act\n    y = x\n\n"
        "    # Assert\n    assert y == 1\n",
    )

    # Act
    result = run_hook(HOOK, commit_payload(tool_use, repo))

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


def test_blocks_a_worktree_comment_committed_with_all(tool_use, run_hook, repo):
    # Arrange
    repo.stage("main.tf", 'resource "a" "b" {}\n')
    repo.commit()
    repo.write("main.tf", '# explain\nresource "a" "b" {}\n')

    # Act
    result = run_hook(HOOK, commit_payload(tool_use, repo, "git commit -am x"))

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert "L1: # explain" in stderr


def test_blocks_a_commit_run_against_another_directory(
    tool_use, run_hook, repo, tmp_path
):
    # Arrange
    repo.stage("q.sql", "SELECT 1; -- explain\n")
    payload = tool_use(
        "Bash", {"command": f"git -C {repo.root} commit -m x"}, cwd=str(tmp_path)
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert "q.sql" in stderr


def test_allows_a_bash_command_that_does_not_commit(tool_use, run_hook, repo):
    # Arrange
    repo.stage("src/app.py", "x = 1  # explain\n")

    # Act
    result = run_hook(HOOK, commit_payload(tool_use, repo, "git status"))

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


def test_fails_closed_when_the_index_cannot_be_read(tool_use, run_hook, repo):
    # Arrange
    broken = repo.root / "broken-index"
    broken.write_bytes(b"not an index")

    # Act
    result = run_hook(
        HOOK, commit_payload(tool_use, repo), env={"GIT_INDEX_FILE": str(broken)}
    )

    # Assert
    _, stderr = assert_blocked(result, "could not read the staged files")
    assert "COMMENT_BLOCKER_DISABLE=1" in stderr


@pytest.mark.parametrize(
    "payload",
    [
        {"tool_name": "Bash", "tool_input": "git commit"},
        {"tool_name": "Bash", "tool_input": {"command": 5}},
    ],
)
def test_allows_a_payload_with_nothing_to_check(run_hook, payload):
    # Arrange
    candidate = payload

    # Act
    result = run_hook(HOOK, candidate)

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


def test_blocks_a_comment_in_a_notebook_code_cell(tool_use, run_hook):
    # Arrange
    notebook = json.dumps(
        {
            "metadata": {"language_info": {"name": "python"}},
            "cells": [
                {"cell_type": "markdown", "source": ["# Heading\n"]},
                {"cell_type": "code", "source": ["x = 1  # explain\n"]},
            ],
        }
    )
    payload = tool_use("Write", {"file_path": "/repo/nb/a.ipynb", "content": notebook})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert "x = 1  # explain" in stderr


@pytest.mark.parametrize(
    ("file_path", "content"),
    [
        ("/repo/conf/ci.yml", "key: value  # explain\n"),
        ("/repo/db/q.sql", "-- explain\nSELECT 1;\n"),
        ("/repo/Dockerfile", "# explain\nFROM alpine\n"),
        ("/repo/web/a.html", "<!-- explain -->\n<p/>\n"),
        ("/repo/lua/a.lua", "--[[ explain ]]\n"),
    ],
)
def test_blocks_a_comment_in_a_newly_covered_language(
    tool_use, run_hook, file_path, content
):
    # Arrange
    payload = tool_use("Write", {"file_path": file_path, "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, BLOCK_MSG)
    assert "explain" in stderr


def test_allows_a_documented_env_example(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/.env.example", "content": "# The API port\nPORT=3000\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


def test_allows_a_rewrite_that_keeps_existing_comments(tool_use, run_hook, tmp_path):
    # Arrange
    path = tmp_path / "a.sh"
    path.write_text("# legacy\necho 1\n", encoding="utf-8")
    payload = tool_use(
        "Write", {"file_path": str(path), "content": "# legacy\necho 2\n"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


@pytest.mark.parametrize(
    "env",
    [{"CLAUDE_HOOK_PROFILE": "minimal"}, {"CLAUDE_DISABLED_HOOKS": "comment-blocker"}],
)
def test_allows_when_the_profile_skips_the_hook(tool_use, run_hook, env):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/tests/test_a.py",
            "content": "# explain\ndef test_a():\n    pass\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=env)

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


def test_allows_a_bash_command_without_a_commit(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "ls"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    code, _ = assert_allowed(result)
    assert code == 0


@pytest.mark.parametrize("raw", ["not json", '["not", "an", "object"]', ""])
def test_blocks_input_it_cannot_read(raw, hooks_dir):
    # Arrange
    hook = hooks_dir / "comment-blocker.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=raw,
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_BYPASS_STATE": os.devnull},
        check=False,
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr
