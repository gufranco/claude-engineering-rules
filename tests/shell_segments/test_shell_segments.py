"""Coverage for `hooks/_lib/shell_segments.py`."""

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
    segments = shell_segments.quoted_segments(command)

    assert segments == expected


def test_heredoc_body_is_dropped():
    command = "python3 - <<'EOF'\nimport os && rm -rf /\nEOF\necho after"

    segments = shell_segments.quoted_segments(command)

    assert segments == [["python3", "-", "<<EOF"], ["echo", "after"]]


def test_dash_heredoc_with_indented_terminator_is_dropped():
    command = "cat <<-END\n\tgh pr create\n\tEND\nls"

    segments = shell_segments.quoted_segments(command)

    assert segments == [["cat", "<<-END"], ["ls"]]


def test_here_string_is_not_a_heredoc():
    command = "read -r x <<<word\nkcov out run.sh"

    segments = shell_segments.quoted_segments(command)

    assert segments == [["read", "-r", "x", "<<<word"], ["kcov", "out", "run.sh"]]


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
    head = shell_segments.command_head(tokens)

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
    masked = shell_segments.mask_literal_text(command)

    assert masked == expected
