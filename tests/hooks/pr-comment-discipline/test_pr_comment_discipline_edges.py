from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _pcd_support import HOOK, REPO

CLI = "g" + "h"


def test_an_unbalanced_comment_command_is_still_blocked(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": CLI + ' pr comment 3 -b "unterminated'})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PRC001")


def test_an_unreadable_review_payload_file_is_blocked(tool_use, run_hook, tmp_path):
    # Arrange
    body = tmp_path / "review.json"
    body.write_text('{"body": ""}', encoding="utf-8")
    body.chmod(0)
    command = f"{CLI} api {REPO}/pulls/7/reviews -X POST --input {body}"

    # Act
    result = run_hook(HOOK, tool_use("Bash", {"command": command}))

    # Assert
    assert_blocked(result, "PRC010")


def test_an_inline_json_payload_is_read(tool_use, run_hook):
    # Arrange
    command = (
        "curl -X POST https://api.bitbucket.org/2.0/repositories/a/b/pullrequests/1/"
        'comments -d \'{"content": {"raw": "x"}}\''
    )

    # Act
    result = run_hook(HOOK, tool_use("Bash", {"command": command}))

    # Assert
    assert_blocked(result, "PRC009")


def test_an_unbalanced_bitbucket_comment_is_still_checked(tool_use, run_hook):
    # Arrange
    command = (
        "curl -X POST https://api.bitbucket.org/2.0/repositories/a/b/pullrequests/1/"
        'comments -d \'{"content": "x"}\' -H "unterminated'
    )

    # Act
    result = run_hook(HOOK, tool_use("Bash", {"command": command}))

    # Assert
    assert_blocked(result, "PRC009")


def test_a_blank_body_in_unparseable_json_is_not_a_summary(tool_use, run_hook):
    # Arrange
    command = (
        f"{CLI} api {REPO}/pulls/7/reviews -X POST --input - <<'EOF'\n"
        '{"body": "  ", "event": "APPROVE",}\nEOF'
    )

    # Act
    result = run_hook(HOOK, tool_use("Bash", {"command": command}))

    # Assert
    assert_allowed(result)
