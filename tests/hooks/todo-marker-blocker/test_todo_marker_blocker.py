from __future__ import annotations
import os
import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
import subprocess
import sys
from pathlib import Path
from _todo_marker_blocker_helpers import HOOK


@pytest.mark.parametrize(
    "marker",
    ["TODO", "FIXME", "HACK", "XXX", "WIP"],
)
def test_blocks_each_marker(tool_use, run_hook, marker):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": f"// {marker}: fix this\nfunction f() {{}}\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, marker)


def test_blocks_lowercase_marker(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// todo: fix this\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


def test_blocks_leave_for_later_phrase(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.go",
            "content": "// We will leave this for later\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "leave for later")


def test_blocks_leave_it_for_later_phrase(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.go",
            "content": "// We will leave it for later\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "leave for later")


def test_blocks_on_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/app.ts",
            "old_string": "old",
            "new_string": "// FIXME: broken",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "FIXME")


def test_blocks_on_multiedit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/app.ts",
            "edits": [
                {"old_string": "a", "new_string": "// TODO: a"},
                {"old_string": "b", "new_string": "// nothing"},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


@pytest.mark.parametrize(
    "issue_form",
    [
        "// TODO(#123): tracked",
        "// FIXME(#456): tracked",
        "// HACK(#issue-789): tracked",
        "// TODO(GH-42): tracked",
        "// FIXME(jira-1234): tracked",
        "// TODO(later) finish this",
        "// TODO(fix this when we have time)",
    ],
)
def test_blocks_a_marker_with_a_parenthesized_note(tool_use, run_hook, issue_form):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": f"{issue_form}\nfunction f() {{}}\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "tactical-debt marker")


def test_bypass_env_var_allows(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// TODO: anything\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"TODO_MARKER_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_blocks_hack_in_python(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/main.py",
            "content": "# HACK: workaround for bug\nprint('hi')\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "HACK")


def test_blocks_in_rust(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/main.rs",
            "content": "// XXX: this is broken\nfn main() {}\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "XXX")


def test_blocks_in_go(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/main.go",
            "content": "// WIP: still working\nfunc main() {}\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "WIP")


def test_blocks_multiple_markers_at_once(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// TODO: a\n// FIXME: b\n// HACK: c\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "TODO")
    assert "FIXME" in stderr
    assert "HACK" in stderr


def test_invalid_json_blocks():
    # Arrange
    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "todo-marker-blocker.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
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
