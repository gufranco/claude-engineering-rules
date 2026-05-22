"""Coverage for todo-marker-blocker hook.

Source rule: `~/.claude/rules/design-philosophy.md` Strategic vs Tactical
Programming, and `~/.claude/CLAUDE.md` Completeness.
"""

from __future__ import annotations

import pytest

HOOK = "todo-marker-blocker"


@pytest.mark.parametrize(
    "marker",
    ["TODO", "FIXME", "HACK", "XXX", "WIP"],
)
def test_blocks_each_marker(tool_use, assert_blocks, marker):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": f"// {marker}: fix this\nfunction f() {{}}\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, marker)


def test_blocks_lowercase_marker(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// todo: fix this\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "TODO")


def test_blocks_leave_for_later_phrase(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.go",
            "content": "// We will leave this for later\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "leave for later")


def test_blocks_leave_it_for_later_phrase(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.go",
            "content": "// We will leave it for later\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "leave for later")


def test_blocks_on_edit(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/app.ts",
            "old_string": "old",
            "new_string": "// FIXME: broken",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "FIXME")


def test_blocks_on_multiedit(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "TODO")


@pytest.mark.parametrize(
    "issue_form",
    [
        "// TODO(#123): tracked",
        "// FIXME(#456): tracked",
        "// HACK(#issue-789): tracked",
        "// TODO(GH-42): tracked",
        "// FIXME(jira-1234): tracked",
    ],
)
def test_allows_issue_linked_form(tool_use, assert_allows, issue_form):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": f"{issue_form}\nfunction f() {{}}\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_marker_in_markdown(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/README.md",
            "content": "TODO: write more docs\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_marker_in_specs_path(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/specs/2026-01-01-foo/plan.md",
            "content": "TODO: refine the plan\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_marker_in_test_file(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/foo.test.ts",
            "content": "// TODO: add edge case test\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_marker_in_spec_file(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/foo.spec.ts",
            "content": "// TODO: add edge case\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_marker_in_template(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/templates/component.ts.tmpl",
            "content": "// TODO: implement\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_marker_in_claude_tree(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/Users/x/.claude/hooks/foo.py",
            "content": "# TODO: refine the pattern\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_non_source_file(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/config.yaml",
            "content": "# TODO: tune this value\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_marker_in_tests_dir(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/__tests__/foo.ts",
            "content": "// TODO: test edge\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_marker_with_line_suppression(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/doc-example.ts",
            "content": "// TODO: example -- allow-todo -- documents the pattern\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_marker_with_file_suppression(tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_bypass_env_var_allows(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// TODO: anything\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"TODO_MARKER_DISABLE": "1"})


def test_blocks_hack_in_python(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/main.py",
            "content": "# HACK: workaround for bug\nprint('hi')\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "HACK")


def test_blocks_in_rust(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/main.rs",
            "content": "// XXX: this is broken\nfn main() {}\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "XXX")


def test_blocks_in_go(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/main.go",
            "content": "// WIP: still working\nfunc main() {}\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "WIP")


def test_allows_empty_payload(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Write", {})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_word_containing_todo_substring(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "const todolist = ['a', 'b']\nconst factotum = 'foo'\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_blocks_multiple_markers_at_once(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// TODO: a\n// FIXME: b\n// HACK: c\n",
        },
    )

    # Act / Assert
    code, stderr = assert_blocks(HOOK, payload, "TODO")
    assert "FIXME" in stderr
    assert "HACK" in stderr


def test_allows_unknown_tool(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/src/app.ts"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_bash_tool(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Bash", {"command": "echo TODO"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_marker_in_node_modules(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/node_modules/somepkg/index.js",
            "content": "// TODO: from third-party\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_marker_in_vendor(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/vendor/lib/foo.go",
            "content": "// TODO: from vendor\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_invalid_json_returns_zero(tool_use, run_hook):
    # Arrange
    import subprocess
    import sys
    from pathlib import Path

    hook_path = Path(__file__).resolve().parents[3] / "hooks" / "todo-marker-blocker.py"

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )

    # Assert
    assert proc.returncode == 0


def test_suppression_without_justification_does_not_allow(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// TODO: x // allow-todo\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "TODO")


def test_file_marker_only_in_first_ten_lines(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "TODO")


def test_file_marker_after_blank_lines(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": ("\n\n\n// @allow-todo -- doc example file\n// TODO: example\n"),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_line_marker_on_previous_line(tool_use, assert_allows):
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

    # Act / Assert
    assert_allows(HOOK, payload)


def test_eslint_disable_suppresses(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/app.ts",
            "content": "// eslint-disable-next-line\n// TODO: covered by eslint-disable\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)
