from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib import shell_segments  # noqa: E402


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("ls -la", [["ls", "-la"]]),
        ("a && b || c; d | e & f", [["a"], ["b"], ["c"], ["d"], ["e"], ["f"]]),
        ("echo 'x && y'", [["echo", "x && y"]]),
        ('grep -e "|gh pr" file', [["grep", "-e", "|gh pr", "file"]]),
        ("echo one\necho two", [["echo", "one"], ["echo", "two"]]),
        ("echo 'unterminated && rm x", []),
        ("", []),
    ],
)
def test_quoted_segments_split_only_at_real_operators(command, expected):
    # Arrange
    command_input = command

    # Act
    segments = shell_segments.quoted_segments(command_input)

    # Assert
    assert segments == expected


def test_heredoc_body_is_dropped():
    # Arrange
    command = "python3 - <<'EOF'\nimport os && rm -rf /\nEOF\necho after"

    # Act
    segments = shell_segments.quoted_segments(command)

    # Assert
    assert segments == [["python3", "-", "<<EOF"], ["echo", "after"]]


def test_dash_heredoc_with_indented_terminator_is_dropped():
    # Arrange
    command = "cat <<-END\n\tgh pr create\n\tEND\nls"

    # Act
    segments = shell_segments.quoted_segments(command)

    # Assert
    assert segments == [["cat", "<<-END"], ["ls"]]


def test_every_heredoc_started_on_one_line_has_its_body_dropped():
    # Arrange
    command = (
        "git commit -F - <<'ONE' && git commit -F - <<'TWO' && git log\n"
        "first body\n"
        "ONE\n"
        'second body == "x"\n'
        "TWO\n"
        "echo after"
    )

    # Act
    stripped = shell_segments.strip_heredoc_bodies(command)

    # Assert
    assert stripped == (
        "git commit -F - <<'ONE' && git commit -F - <<'TWO' && git log\necho after"
    )


def test_here_string_is_not_a_heredoc():
    # Arrange
    command = "read -r x <<<word\nkcov out run.sh"

    # Act
    segments = shell_segments.quoted_segments(command)

    # Assert
    assert segments == [["read", "-r", "x", "<<<word"], ["kcov", "out", "run.sh"]]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("make", [("make", "")]),
        (
            "cd a && make 2>&1 | tail -3; echo x",
            [("cd a ", ""), (" make 2>&1 ", "&&"), (" tail -3", "|"), (" echo x", ";")],
        ),
        ("make &>log & wait", [("make &>log ", ""), (" wait", "&")]),
        (
            "make |& tee log || true",
            [("make ", ""), (" tee log ", "|&"), (" true", "||")],
        ),
        ("echo 'a; b' \"c | d\"", [("echo 'a; b' \"c | d\"", "")]),
        ("a\nb;", [("a", ""), ("b", "\n")]),
        ("", []),
    ],
)
def test_operator_segments_name_the_operator_before_each_segment(command, expected):
    # Arrange
    command_input = command

    # Act
    segments = shell_segments.operator_segments(command_input)

    # Assert
    assert segments == expected


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        (["ls", "-la"], ("ls", ["ls", "-la"])),
        (["/bin/rm", "x"], ("rm", ["/bin/rm", "x"])),
        (["FOO=1", "BAR=2", "make", "test"], ("make", ["make", "test"])),
        (["command", "rm", "x"], ("rm", ["rm", "x"])),
        (["command"], ("command", ["command"])),
        (["FOO=1"], ("", [])),
        ([], ("", [])),
    ],
)
def test_command_head_skips_env_and_command_builtin(tokens, expected):
    # Arrange
    tokens_input = tokens

    # Act
    head = shell_segments.command_head(tokens_input)

    # Assert
    assert head == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("echo 'a|gh b'", "echo '      '"),
        ('echo "it\'s $(gh x)"', 'echo "it\'s $(gh x)"'),
        ("echo \\'gh x", "echo \\'gh x"),
        ('echo "a \\" gh b"', 'echo "a \\" gh b"'),
        ("echo 'open", "echo '    "),
        ("cat <<'EOF'\ngh pr\nEOF\nls", "cat <<'   '\n\nEOF\nls"),
        ("cat <<EOF\n$(gh pr)\nEOF", "cat <<EOF\n$(gh pr)\nEOF"),
    ],
)
def test_mask_literal_text_blanks_only_unexecuted_text(command, expected):
    # Arrange
    command_input = command

    # Act
    masked = shell_segments.mask_literal_text(command_input)

    # Assert
    assert masked == expected
