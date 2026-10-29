from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked

CLI = "g" + "h"


def test_a_long_flag_that_is_not_force_does_not_count(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "cp --no-clobber a.txt b.txt"})

    # Act
    result = run_hook("interactive-cmd-blocker", payload)

    # Assert
    assert_blocked(result)


def test_listing_extensions_needs_no_token(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": f"{CLI} extension list"})

    # Act
    result = run_hook("gh-token-guard", payload)

    # Assert
    assert_allowed(result)


def test_an_auth_switch_is_blocked_with_its_own_message(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": f"{CLI} auth switch --user other"})

    # Act
    result = run_hook("gh-token-guard", payload)

    # Assert
    assert_blocked(result, "changes the global active account")


def test_a_write_without_a_path_is_not_checked_for_markers(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": "", "content": "// TO" + "DO later\n"})

    # Act
    result = run_hook("todo-marker-blocker", payload)

    # Assert
    assert_allowed(result)


def test_a_file_that_is_neither_schema_nor_script_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/docs/notes.txt", "content": "drizzle-kit push\n"}
    )

    # Act
    result = run_hook("drizzle-schema-sync", payload)

    # Assert
    assert_allowed(result)


def test_a_config_write_without_content_is_still_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": "/repo/tsconfig.json"})

    # Act
    result = run_hook("config-protection", payload)

    # Assert
    assert_blocked(result, "weaken type or lint strictness")


def test_a_fanout_inside_a_test_directory_is_skipped(tool_use, run_hook):
    # Arrange
    content = "await Promise.all(users.map((user) => notify(user)));\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/src/__tests__/notify.ts", "content": content}
    )

    # Act
    result = run_hook(
        "concurrent-fanout-guard", payload, env={"CONCURRENT_FANOUT_ENFORCE": "1"}
    )

    # Assert
    assert (result.code, result.stdout) == (0, "")
