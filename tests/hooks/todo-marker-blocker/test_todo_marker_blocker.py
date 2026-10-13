from __future__ import annotations

import os

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
import subprocess
import sys
from pathlib import Path

HOOK = "todo-marker-blocker"


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


def test_allows_marker_in_markdown(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/README.md",
            "content": "TODO: write more docs\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_marker_in_specs_path(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/specs/2026-01-01-foo/plan.md",
            "content": "TODO: refine the plan\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_marker_in_test_file(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/foo.test.ts",
            "content": "// TODO: add edge case test\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_marker_in_spec_file(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/foo.spec.ts",
            "content": "// TODO: add edge case\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_marker_in_template(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/templates/component.ts.tmpl",
            "content": "// TODO: implement\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_marker_in_claude_tree(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/x/.claude/hooks/foo.py",
            "content": "# TODO: refine the pattern\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_non_source_file(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/config.yaml",
            "content": "# TODO: tune this value\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_marker_in_tests_dir(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/__tests__/foo.ts",
            "content": "// TODO: test edge\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_line_allow_marker_does_not_suppress(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/doc-example.ts",
            "content": "// TODO: example -- allow-todo -- documents the pattern\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


def test_file_allow_marker_does_not_suppress(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/doc-example.ts",
            "content": (
                "// @allow-todo -- this file documents the patterns\n"
                "// TODO: example 1\n"
                "// TODO: example 2\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


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


def test_allows_empty_payload(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_word_containing_todo_substring(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "const todolist = ['a', 'b']\nconst factotum = 'foo'\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


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


def test_allows_unknown_tool(tool_use, run_hook):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/app.ts"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_bash_tool(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "echo TODO"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_marker_in_node_modules(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/node_modules/somepkg/index.js",
            "content": "// TODO: from third-party\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_marker_in_vendor(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/vendor/lib/foo.go",
            "content": "// TODO: from vendor\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


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


def test_suppression_without_justification_does_not_allow(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// TODO: x // allow-todo\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


def test_file_marker_only_in_first_ten_lines(tool_use, run_hook):
    # Arrange
    leading = "\n".join([f"// line {i}" for i in range(15)])
    trailing = "\n".join([f"// post {i}" for i in range(5)])
    content = (
        leading
        + "\n// @allow-todo -- after ten lines is too late\n"
        + trailing
        + "\n// TODO: hit\n"
    )
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": content,
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


def test_file_allow_marker_after_blank_lines_does_not_suppress(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": ("\n\n\n// @allow-todo -- doc example file\n// TODO: example\n"),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


def test_allow_marker_on_previous_line_does_not_suppress(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": (
                "// allow-todo -- this is a documented example\n"
                "// TODO: documented example\n"
            ),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "TODO")


def test_eslint_directive_still_suppresses(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// eslint-disable-next-line\n// TODO: documented example\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_eslint_disable_suppresses(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// eslint-disable-next-line\n// TODO: covered by eslint-disable\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
