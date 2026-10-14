from __future__ import annotations
from _helpers.hook_assertions import assert_allowed
from _todo_marker_blocker_helpers import HOOK


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
