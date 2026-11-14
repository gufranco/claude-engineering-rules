from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.sandbox_links import (  # noqa: E402
    Link,
    is_real,
    is_temporary,
    planned_links,
    temp_roots,
)

ENV = {"HOME": "/home/user", "TMPDIR": "/var/folders/ab/xyz/T/"}


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("ln -s /a/b /c/d", [Link("/a/b", "/c/d")]),
        ("ln -sfn ~/x /tmp/y", [Link("/home/user/x", "/tmp/y")]),
        ('S=/tmp/s && ln -s "$S/a" "${S}/b"', [Link("/tmp/s/a", "/tmp/s/b")]),
        ('export S="/tmp/a b" && ln -s /x "$S/l"', [Link("/x", "/tmp/a b/l")]),
        ("cd /tmp/w && ln -s /x l", [Link("/x", "/tmp/w/l")]),
        ("cd /tmp/w && ln -s /x", [Link("/x", "/tmp/w")]),
        ("ln -s -t /tmp/d /x /y", [Link("/x", "/tmp/d"), Link("/y", "/tmp/d")]),
        ("ln --target-directory=/tmp/d -s /x", [Link("/x", "/tmp/d")]),
        ("ln -s ../x /tmp/w/l", [Link("/tmp/x", "/tmp/w/l")]),
        ("ln ../x /tmp/w/l", [Link("/x", "/tmp/w/l")]),
        ("HOME=/elsewhere ln -s /a /b", []),
        ("ln -s $NOPE /tmp/l", []),
        ("ln -s 'open", []),
    ],
)
def test_planned_links_resolve_sources_and_destinations(command, expected) -> None:
    # Arrange
    cwd = "/work"

    # Act
    result = planned_links(command, cwd, ENV)

    # Assert
    assert result == expected


def test_a_mktemp_assignment_counts_as_a_temp_dir() -> None:
    # Arrange
    command = 't=$(mktemp -d) && ln -s /home/user/x "$t/l"'

    # Act
    result = planned_links(command, "/work", ENV)

    # Assert
    assert len(result) == 1
    assert is_temporary(result[0].destination, ENV)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/tmp", True),
        ("/private/tmp/claude-1000/x", True),
        ("/var/folders/ab/xyz/T/tmp.1", True),
        ("/private/var/folders/ab/xyz/T/tmp.1", True),
        ("/tmpfoo", False),
        ("/home/user", False),
    ],
)
def test_temporary_paths_follow_the_temp_roots(path, expected) -> None:
    # Arrange
    env = ENV

    # Act
    result = is_temporary(path, env)

    # Assert
    assert result is expected


def test_no_tmpdir_leaves_only_the_fixed_roots() -> None:
    # Arrange
    env = {"HOME": "/home/user"}

    # Act
    roots = temp_roots(env)

    # Assert
    assert roots == ("/tmp", "/private/tmp")


def test_a_path_in_a_work_tree_outside_home_is_real(tmp_path) -> None:
    # Arrange
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    env = {"HOME": "/home/user"}

    # Act
    result = is_real(str(tmp_path / "repo" / "src"), env)

    # Assert
    assert result is True


@pytest.mark.parametrize("path", ["/usr/bin/true", "/tmp/x"])
def test_system_and_temp_paths_are_not_real(path) -> None:
    # Arrange
    env = {"HOME": ""}

    # Act
    result = is_real(path, env)

    # Assert
    assert result is False
