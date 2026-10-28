from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.publish_commands import (  # noqa: E402
    Attachment,
    Channel,
    publications,
    tracker_publication,
)

fake = Faker()
Faker.seed(7307)
GH = "g" + "h"
TOKEN = f"GH_TOKEN=$({GH} auth token --user acct)"


def test_pr_create_records_attachments_body_and_base(tmp_path):
    # Arrange
    alt = fake.sentence(nb_words=3)
    command = (
        f"{TOKEN} {GH} pr create --base develop -R acme/web --body 'see shots' "
        f"--attach 'before.png#Before: {alt}' --attach=after.png"
    )

    # Act
    result = publications(command, str(tmp_path))

    # Assert
    assert len(result) == 1
    assert result[0].channel is Channel.PR_CREATE
    assert result[0].attachments == (
        Attachment("before.png", f"Before: {alt}"),
        Attachment("after.png", ""),
    )
    assert (result[0].text, result[0].base, result[0].repo) == (
        "see shots",
        "develop",
        "acme/web",
    )


def test_body_file_is_read_relative_to_the_working_directory(tmp_path):
    # Arrange
    body = fake.paragraph()
    (tmp_path / "body.md").write_text(body, encoding="utf-8")

    # Act
    result = publications(f"{GH} issue comment 4 --body-file body.md", str(tmp_path))

    # Assert
    assert [(p.channel, p.text, p.unreadable) for p in result] == [
        (Channel.ISSUE_COMMENT, body, ())
    ]


def test_an_unreadable_body_file_is_reported(tmp_path):
    # Arrange
    missing = f"{fake.word()}.md"

    # Act
    result = publications(f"{GH} issue create -F {missing}", str(tmp_path))

    # Assert
    assert result[0].unreadable == (missing,)


def test_a_stdin_body_file_reads_the_heredoc(tmp_path):
    # Arrange
    body = fake.sentence()
    command = f"{GH} pr create --body-file - <<'EOF'\n{body}\nEOF"

    # Act
    result = publications(command, str(tmp_path))

    # Assert
    assert body in result[0].text


@pytest.mark.parametrize(
    "command",
    [
        f"{GH} pr create --help",
        f"{GH} pr edit 3 --add-label bug",
        f"{GH} issue edit 3 --title x",
        f"{GH} pr list",
        f"{GH} api repos/a/b/pulls/3/comments",
        "glab mr update 3 --label x",
        "glab mr list",
        "echo hello",
        "",
    ],
)
def test_commands_that_publish_no_text_are_ignored(tmp_path, command):
    # Arrange
    cwd = str(tmp_path)

    # Act
    result = publications(command, cwd)

    # Assert
    assert result == []


def test_pr_edit_with_only_an_attachment_counts(tmp_path):
    # Arrange
    command = f"{GH} pr edit 9 --attach 'a.png#After: grid'"

    # Act
    result = publications(command, str(tmp_path))

    # Assert
    assert [p.channel for p in result] == [Channel.PR_EDIT]


def test_thread_reply_reads_field_and_input_bodies(tmp_path):
    # Arrange
    field_body = fake.sentence()
    input_body = fake.sentence()
    (tmp_path / "reply.json").write_text(json.dumps({"body": input_body}))
    (tmp_path / "plain.txt").write_text("not json")
    command = (
        f"{GH} api repos/a/b/pulls/7/comments/99/replies -X POST "
        f"-f body='{field_body}' -f other=1 --input reply.json --input plain.txt"
    )

    # Act
    result = publications(command, str(tmp_path))

    # Assert
    assert result[0].channel is Channel.THREAD_REPLY
    assert result[0].text.split("\n") == [field_body, input_body, "not json"]


def test_thread_reply_reads_a_body_field_file_and_reports_a_missing_one(tmp_path):
    # Arrange
    body = fake.sentence()
    (tmp_path / "b.md").write_text(body)
    command = (
        f"{GH} api repos/a/b/pulls/7/comments -F in_reply_to=5 "
        "-F body=@b.md -F body=@gone.md --input gone.json"
    )

    # Act
    result = publications(command, str(tmp_path))

    # Assert
    assert result[0].channel is Channel.THREAD_REPLY
    assert (result[0].text, result[0].unreadable) == (body, ("gone.md", "gone.json"))


def test_stdin_payloads_read_the_heredoc(tmp_path):
    # Arrange
    body = fake.sentence()
    command = (
        f"{GH} api repos/a/b/pulls/7/comments/9/replies -F body=@- --input - "
        f"<<'EOF'\n{body}\nEOF"
    )

    # Act
    result = publications(command, str(tmp_path))

    # Assert
    assert body in result[0].text


@pytest.mark.parametrize(
    "command",
    [
        f"{GH} api repos/a/b/issues/12/comments -f body=hi",
        f"{GH} api repos/a/b/issues/12/comments --method POST",
    ],
)
def test_issue_comment_through_the_api_counts(tmp_path, command):
    # Arrange
    cwd = str(tmp_path)

    # Act
    result = publications(command, cwd)

    # Assert
    assert [p.channel for p in result] == [Channel.API_ISSUE_COMMENT]


@pytest.mark.parametrize(
    ("command", "channel"),
    [
        ("glab mr create --description 'x'", Channel.MR_CREATE),
        ("glab mr update 3 -d 'x'", Channel.MR_UPDATE),
        ("glab issue create --description 'x'", Channel.GLAB_ISSUE_CREATE),
        ("glab issue note 4 -m 'x'", Channel.GLAB_ISSUE_NOTE),
    ],
)
def test_glab_channels_are_recognised(tmp_path, command, channel):
    # Arrange
    cwd = str(tmp_path)

    # Act
    result = publications(command, cwd)

    # Assert
    assert [(p.channel, p.text) for p in result] == [(channel, "x")]


def test_every_publication_in_a_chain_is_returned(tmp_path):
    # Arrange
    command = f"cd web && {GH} pr create -b one; {GH} issue comment 2 -b two"

    # Act
    result = publications(command, str(tmp_path))

    # Assert
    assert [p.text for p in result] == ["one", "two"]


def test_an_unbalanced_quote_falls_back_to_plain_words(tmp_path):
    # Arrange
    command = f'{GH} issue create -b "open'

    # Act
    result = publications(command, str(tmp_path))

    # Assert
    assert [p.text for p in result] == ['"open']


def test_tracker_issue_collects_description_and_patch_text():
    # Arrange
    description = fake.paragraph()
    tool_input = {
        "description": description,
        "patch": [
            {"op": "append", "text": "tail"},
            {"op": "replace", "old_string": "a", "new_string": "b"},
            "skip",
        ],
    }

    # Act
    result = tracker_publication("mcp__linear-acme__save_issue", tool_input)

    # Assert
    assert result is not None
    assert (result.channel, result.text) == (
        Channel.TRACKER_ISSUE,
        f"{description}\ntail\nb",
    )


def test_tracker_comment_reads_the_body():
    # Arrange
    body = fake.sentence()

    # Act
    result = tracker_publication("mcp__linear-acme__save_comment", {"body": body})

    # Assert
    assert result is not None
    assert (result.channel, result.text) == (Channel.TRACKER_COMMENT, body)


@pytest.mark.parametrize(
    ("tool_name", "tool_input"),
    [
        ("mcp__linear-acme__get_issue", {"description": "x"}),
        ("Bash", {"command": "x"}),
        ("mcp__linear-acme__save_issue", "not a mapping"),
    ],
)
def test_other_tools_are_not_tracker_publications(tool_name, tool_input):
    # Arrange
    name = tool_name

    # Act
    result = tracker_publication(name, tool_input)

    # Assert
    assert result is None


def test_tracker_issue_without_text_fields_has_empty_text():
    # Arrange
    tool_input = {"title": "x", "patch": "not a list"}

    # Act
    result = tracker_publication("mcp__linear-acme__save_issue", tool_input)

    # Assert
    assert result is not None
    assert result.text == ""


def test_an_absolute_body_file_is_read_as_is(tmp_path):
    # Arrange
    body = fake.sentence()
    path = tmp_path / "abs.md"
    path.write_text(body, encoding="utf-8")

    # Act
    result = publications(f"{GH} pr create --body-file {path}", "/")

    # Assert
    assert result[0].text == body
