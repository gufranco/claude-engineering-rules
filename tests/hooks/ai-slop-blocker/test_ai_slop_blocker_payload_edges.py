from __future__ import annotations

HOOK = "ai-slop-blocker"
CLI = "g" + "h"


def test_non_body_fields_and_loose_comment_entries_are_ignored(
    tool_use, run_hook, tmp_path
):
    # Arrange
    payload_file = tmp_path / "review.json"
    payload_file.write_text(
        '{"comments": ["loose", {"body": "Renamed the helper."}]}', encoding="utf-8"
    )
    command = f"{CLI} api repos/a/b/pulls/1/reviews -f title=x --input {payload_file}"

    # Act
    result = run_hook(HOOK, tool_use("Bash", {"command": command}))

    # Assert
    assert result.code == 0


def test_an_unreadable_payload_file_is_reported(tool_use, run_hook, tmp_path):
    # Arrange
    payload_file = tmp_path / "reply.json"
    payload_file.write_text('{"body": "Fixed."}', encoding="utf-8")
    payload_file.chmod(0)
    endpoint = "repos/a/b/pulls/1/comments/2/" + "replies"
    command = f"{CLI} api {endpoint} --input {payload_file}"

    # Act
    result = run_hook(HOOK, tool_use("Bash", {"command": command}))

    # Assert
    assert result.code == 0
    assert "cannot read" in result.stderr
