from __future__ import annotations

import os

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "ai-slop-blocker"
DOC = "/repo/docs/notes.md"

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))


def test_repository_corpus_is_not_empty():
    # Arrange
    rules_dir = REPO_ROOT / "rules"

    # Act
    corpus = sorted(rules_dir.glob("*.md"))

    # Assert
    assert len(corpus) > 1


@pytest.mark.parametrize(
    "path",
    [
        path
        for path in sorted((REPO_ROOT / "rules").glob("*.md"))
        if path.name != "anti-slop.md"
    ],
    ids=lambda path: path.name,
)
def test_repository_corpus_stays_clean(tool_use, run_hook, path):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": str(path), "content": path.read_text(encoding="utf-8")},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_missing_file_path_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"content": "This stands as a testament.\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_unwatched_tool_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Read", {"file_path": DOC})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_vocabulary_cluster_ignores_a_repeated_single_word(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": DOC,
            "content": (
                "# Notes\n\nThe meticulous rollout was planned.\n"
                "The meticulous rehearsal followed.\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_repeated_code_reports_its_fix_once(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": DOC,
            "edits": [
                {"old_string": "a", "new_string": "Experts argue the design is wrong."},
                {"old_string": "b", "new_string": "Studies show the cache is cold."},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _exit, stderr = assert_blocked(
        result, "BLOCKED by ai-slop-blocker (~/.claude/rules/anti-slop.md)"
    )
    assert stderr.count("SLOP004: Name the source") == 1


def test_profile_disable_short_circuits(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": DOC, "content": "This stands as a testament to the design.\n"},
    )

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": HOOK})

    # Assert
    assert_allowed(result)


def test_registry_bypass_short_circuits(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": DOC, "content": "This stands as a testament to the design.\n"},
    )
    registry = tmp_path / "bypass.json"
    registry.write_text(
        json.dumps(
            {
                "version": 1,
                "bypasses": [
                    {
                        "hook": HOOK,
                        "expires_at": (
                            datetime.now(timezone.utc) + timedelta(minutes=10)
                        ).isoformat(),
                        "reason": "test",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(registry)})

    # Assert
    assert_allowed(result)


def test_malformed_stdin_blocks():
    # Arrange
    hook_path = REPO_ROOT / "hooks" / "ai-slop-blocker.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not json at all",
        capture_output=True,
        text=True,
        timeout=30,
        env={
            **os.environ,
            "CLAUDE_HOOK_AUDIT_DISABLE": "1",
            "CLAUDE_BYPASS_STATE": os.devnull,
        },
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr
