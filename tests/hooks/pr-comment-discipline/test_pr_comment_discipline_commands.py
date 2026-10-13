from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _pcd_support import (
    HOOK,
    REPO,
)


@pytest.mark.parametrize(
    "command",
    [
        "gh pr edit 12 --body-file /tmp/description.md",
        "gh pr create --title fix --body-file /tmp/description.md",
        f"gh api {REPO}/pulls/12/comments",
        f"gh api {REPO}/issues/12/comments --paginate",
        "gh api graphql -f query='mutation { resolveReviewThread(input: {threadId: \"x\"}) { thread { id } } }'",
        "git commit -m 'fix: off by one'",
    ],
)
def test_allows_unrelated_and_read_only_commands(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_non_bash_tools(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/tmp/x.md", "content": "gh pr comment 1"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bypass_env_allows(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": 'gh pr comment 12 --body "hi"'})

    # Act
    result = run_hook(HOOK, payload, env={"PR_COMMENT_DISCIPLINE_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_payload_without_tool_input_is_allowed_silently(run_hook):
    # Arrange
    payload = {"tool_name": "Bash"}

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert (result.code, result.stdout, result.stderr) == (0, "", "")


def test_inline_heredoc_body_is_read(tool_use, run_hook):
    # Arrange
    command = (
        f"gh api {REPO}/pulls/12/reviews -X POST --input - <<'JSON'\n"
        '{"event": "COMMENT", "body": "Nice work overall.", "comments": []}\n'
        "JSON"
    )
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC003")


def test_unparseable_quoting_still_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": 'gh pr comment 12 --body "unbalanced'})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC001")


@pytest.mark.parametrize(
    "method_flag",
    [
        "--method POST",
        "--method=POST",
        "--request PUT",
        "-XPATCH",
    ],
)
def test_recognizes_every_method_spelling(tool_use, run_hook, method_flag):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/issues/12/comments {method_flag}"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC005")


def test_read_only_method_is_not_a_write(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/issues/12/comments --method GET"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "command",
    [
        f"ls -d node_modules && gh api {REPO}/pulls/12/comments",
        f"gh api {REPO}/pulls/12/comments | jq -f filter.jq",
        f"cut -d, -f1 ids.csv; gh api {REPO}/issues/12/comments",
    ],
)
def test_a_flag_from_another_command_is_not_a_payload(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    ("command", "code"),
    [
        (f"ls -d node_modules && gh api {REPO}/pulls/12/comments -f body=hi", "PRC004"),
        (f"cat body.json | gh api {REPO}/issues/12/comments --input -", "PRC005"),
        (f"cd repo; gh api {REPO}/pulls/12/comments -X POST", "PRC004"),
    ],
)
def test_a_write_chained_after_another_command_is_still_caught(
    tool_use, run_hook, command, code
):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, code)


def test_trailing_payload_flag_without_a_value(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/comments -X POST --input"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC004")


def test_stdin_payload_falls_back_to_the_command(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": f"gh api {REPO}/pulls/12/comments -X POST --input -"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC004")
