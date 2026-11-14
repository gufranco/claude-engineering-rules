from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.machine_leak_sources import (  # noqa: E402
    COMMAND_LABEL,
    MESSAGE_LABEL,
    PUBLISHED_LABEL,
    added_in_command,
    command_text_lines,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t.test",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "kept.txt").write_text("one\n", encoding="utf-8")
    _git(root, "add", "kept.txt")
    _git(root, "commit", "-q", "--no-verify", "-m", "chore: start")
    return root


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git commit -m 'a b'", [(MESSAGE_LABEL, 1, "a b")]),
        ("git commit -mshort", [(MESSAGE_LABEL, 1, "short")]),
        ("git commit --message=long", [(MESSAGE_LABEL, 1, "long")]),
        (
            "git -C x commit -m one -m two",
            [(MESSAGE_LABEL, 1, "one"), (MESSAGE_LABEL, 1, "two")],
        ),
        (
            "gh pr create -t T -b B",
            [(PUBLISHED_LABEL, 1, "T"), (PUBLISHED_LABEL, 1, "B")],
        ),
        ("gh api repos/x -f body=hello", [(PUBLISHED_LABEL, 1, "hello")]),
        ("gh release create v1 --notes N", [(PUBLISHED_LABEL, 1, "N")]),
        ("echo hi && ls", []),
        ("git commit", []),
    ],
)
def test_text_flags_become_scanned_lines(command, expected, tmp_path) -> None:
    # Arrange
    cwd = str(tmp_path)

    # Act
    result = command_text_lines(command, cwd)

    # Assert
    assert result == expected


def test_message_and_body_files_are_read(tmp_path) -> None:
    # Arrange
    message = tmp_path / "m.txt"
    message.write_text("subject\n\nbody\n", encoding="utf-8")
    command = (
        f"git commit -F {message.name} && gh pr comment 1 --body-file {message.name}"
    )

    # Act
    result = command_text_lines(command, str(tmp_path))

    # Assert
    assert result == [
        (MESSAGE_LABEL, 1, "subject"),
        (MESSAGE_LABEL, 3, "body"),
        (PUBLISHED_LABEL, 1, "subject"),
        (PUBLISHED_LABEL, 3, "body"),
    ]


def test_a_stdin_or_missing_file_reads_nothing(tmp_path) -> None:
    # Arrange
    command = "git commit -F - && gh pr create --body-file absent.md"

    # Act
    result = command_text_lines(command, str(tmp_path))

    # Assert
    assert result == []


def test_an_unparseable_command_is_scanned_whole(tmp_path) -> None:
    # Arrange
    command = "gh pr create --body 'open"

    # Act
    result = command_text_lines(command, str(tmp_path))

    # Assert
    assert result == [(COMMAND_LABEL, 1, command)]


def test_a_named_add_reads_new_and_changed_files(repo: Path) -> None:
    # Arrange
    (repo / "kept.txt").write_text("one\ntwo\n", encoding="utf-8")
    (repo / "new.txt").write_text("fresh\n", encoding="utf-8")
    command = "git add kept.txt new.txt && git commit -m x"

    # Act
    result = added_in_command(command, str(repo))

    # Assert
    assert sorted(result) == [("kept.txt", 2, "two"), ("new.txt", 1, "fresh")]


def test_a_whole_tree_add_reads_every_pending_file(repo: Path) -> None:
    # Arrange
    (repo / "dir").mkdir()
    (repo / "dir" / "n.txt").write_text("n\n", encoding="utf-8")

    # Act
    result = added_in_command("git add -A && git commit -m x", str(repo))

    # Assert
    assert result == [("dir/n.txt", 1, "n")]


def test_no_add_reads_nothing(repo: Path) -> None:
    # Arrange
    (repo / "new.txt").write_text("fresh\n", encoding="utf-8")

    # Act
    result = added_in_command("git commit -m x", str(repo))

    # Assert
    assert result == []


def test_an_add_outside_a_repository_reads_nothing(tmp_path) -> None:
    # Arrange
    (tmp_path / "f.txt").write_text("x\n", encoding="utf-8")

    # Act
    result = added_in_command("git add f.txt", str(tmp_path))

    # Assert
    assert result == []


def test_an_oversized_added_file_is_skipped(repo: Path) -> None:
    # Arrange
    (repo / "big.txt").write_text("x" * (600 * 1024), encoding="utf-8")

    # Act
    result = added_in_command("git add big.txt && git commit -m x", str(repo))

    # Assert
    assert result == []


def test_a_heredoc_message_with_an_apostrophe_is_read_as_the_message(tmp_path):
    # Arrange
    command = (
        "cd \"/home/u/some where\" && git commit -F - <<'MSG'\n"
        "fix: y\n\nthe maintainer's machine\nMSG"
    )

    # Act
    result = command_text_lines(command, str(tmp_path))

    # Assert
    assert result == [
        (MESSAGE_LABEL, 1, "fix: y"),
        (MESSAGE_LABEL, 3, "the maintainer's machine"),
    ]


def test_a_heredoc_body_file_feeds_the_published_text(tmp_path) -> None:
    # Arrange
    command = "gh pr comment 1 --body-file - <<'B'\nhello\nB"

    # Act
    result = command_text_lines(command, str(tmp_path))

    # Assert
    assert result == [(PUBLISHED_LABEL, 1, "hello")]


def test_the_fallback_skips_segments_that_publish_nothing(tmp_path) -> None:
    # Arrange
    command = "cd /home/u/x && gh pr create --body 'open"

    # Act
    result = command_text_lines(command, str(tmp_path))

    # Assert
    assert result == [(COMMAND_LABEL, 1, "gh pr create --body 'open")]


def test_a_heredoc_opened_by_another_command_is_not_the_message(tmp_path) -> None:
    # Arrange
    command = (
        "python3 - <<'PY'\nold = 'private words'\nPY\n"
        "git commit -F - <<'MSG'\ndocs: neutral\nMSG"
    )

    # Act
    result = command_text_lines(command, str(tmp_path))

    # Assert
    assert result == [(MESSAGE_LABEL, 1, "docs: neutral")]


def test_an_unparseable_command_keeps_its_publishing_heredoc(tmp_path) -> None:
    # Arrange
    command = "gh pr create --body 'open <<'B'\nignored\nB\ngh pr comment 1 --body-file - <<'C'\nkept\nC"

    # Act
    result = command_text_lines(command, str(tmp_path))

    # Assert
    assert "kept" in [text for _label, _number, text in result]
