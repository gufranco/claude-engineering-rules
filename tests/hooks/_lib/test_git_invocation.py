from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.git_invocation import (  # noqa: E402
    FORCE_PUSH_LONG,
    FORCE_PUSH_SHORT,
    FORCE_PUSH_WITH_LEASE,
    strip_git_global_options,
)

FORCE = "--" + "force"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git -C /tmp/x push origin feat", "git push origin feat"),
        ('git -C "/tmp/my repo" push origin feat', "git push origin feat"),
        ("git -C '/tmp/my repo' commit -m x", "git commit -m x"),
        ("git -C /tmp/my\\ repo status", "git status"),
        ("git -C $HOME/repo status", "git status"),
        ("git -C $(pwd) status", "git status"),
        ("git -C `pwd` status", "git status"),
        ("git -c core.editor=true commit", "git commit"),
        ('git -c "user.name=A B" commit', "git commit"),
        ("git --git-dir=/x/.git push", "git push"),
        ("git --git-dir /x/.git push", "git push"),
        ("git --work-tree=/x add a.txt", "git add a.txt"),
        ("git --work-tree /x add a.txt", "git add a.txt"),
        ("git --namespace=ns push", "git push"),
        ("git --namespace ns push", "git push"),
        ("git --config-env=core.editor=EDITOR commit", "git commit"),
        ("git --config-env core.editor=EDITOR commit", "git commit"),
        ("git --exec-path=/opt/git push", "git push"),
        ("git --exec-path push", "git push"),
        ("git --attr-source=HEAD add a", "git add a"),
        ("git --no-pager log", "git log"),
        ("git --paginate log", "git log"),
        ("git -p log", "git log"),
        ("git -P log", "git log"),
        ("git --bare push", "git push"),
        ("git --no-replace-objects push", "git push"),
        ("git --literal-pathspecs add a", "git add a"),
        ("git --glob-pathspecs add a", "git add a"),
        ("git --noglob-pathspecs add a", "git add a"),
        ("git --icase-pathspecs add a", "git add a"),
        ("git --no-optional-locks status", "git status"),
        ("git --no-advice commit", "git commit"),
    ],
)
def test_each_global_option_form_is_removed(command, expected):
    # Arrange
    command_input = command

    # Act
    normalized = strip_git_global_options(command_input)

    # Assert
    assert normalized == expected


def test_several_global_options_in_a_row_are_removed():
    # Arrange
    command = f"git -C /a -c x=y --no-pager --git-dir=/a/.git push {FORCE} origin main"

    # Act
    normalized = strip_git_global_options(command)

    # Assert
    assert normalized == f"git push {FORCE} origin main"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("/usr/bin/git -C /x push", "/usr/bin/git push"),
        ("command git -C /x push", "command git push"),
        ("GIT_TRACE=1 git -C /x push", "GIT_TRACE=1 git push"),
    ],
)
def test_a_prefixed_git_is_normalised(command, expected):
    # Arrange
    command_input = command

    # Act
    normalized = strip_git_global_options(command_input)

    # Assert
    assert normalized == expected


@pytest.mark.parametrize(
    "separator",
    [" && ", " ; ", " | ", " || ", "\n"],
)
def test_every_segment_of_a_compound_command_is_normalised(separator):
    # Arrange
    command = f"git -C /a status{separator}git -c a=b push origin feat"

    # Act
    normalized = strip_git_global_options(command)

    # Assert
    assert normalized == f"git status{separator}git push origin feat"


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "git push origin feat",
        "git status",
        "git push -C origin",
        "legit -C /x push",
        "rm -rf .git -C /x",
        "git-lfs -C /x push",
        "",
    ],
)
def test_a_command_without_git_global_options_is_unchanged(command):
    # Arrange
    command_input = command

    # Act
    normalized = strip_git_global_options(command_input)

    # Assert
    assert normalized == command


def test_options_after_the_subcommand_are_kept():
    # Arrange
    command = "git log -p -c --no-pager"

    # Act
    normalized = strip_git_global_options(command)

    # Assert
    assert normalized == command


def test_an_option_glued_to_text_is_not_an_option():
    # Arrange
    command = "git -pfoo log"

    # Act
    normalized = strip_git_global_options(command)

    # Assert
    assert normalized == command


def test_a_git_call_inside_a_quoted_shell_string_is_normalised():
    # Arrange
    command = f"bash -c 'git -C /x push {FORCE}'"

    # Act
    normalized = strip_git_global_options(command)

    # Assert
    assert normalized == f"bash -c 'git push {FORCE}'"


@pytest.mark.parametrize(
    ("command", "long_force", "short_force", "lease"),
    [
        (f"git push {FORCE} origin feat", True, False, False),
        ("git push -" + "fu origin feat", False, True, False),
        (f"git push {FORCE}-with-lease origin feat", False, False, True),
        (f"git push {FORCE}-if-includes origin feat", False, False, False),
        ("git push origin feat && rm -" + "f x", False, False, False),
        (f"git push origin feat | tee {FORCE}", False, False, False),
    ],
)
def test_force_patterns_match_only_inside_the_push(
    command, long_force, short_force, lease
):
    # Arrange
    patterns = (FORCE_PUSH_LONG, FORCE_PUSH_SHORT, FORCE_PUSH_WITH_LEASE)

    # Act
    matches = tuple(re.search(pattern, command) is not None for pattern in patterns)

    # Assert
    assert matches == (long_force, short_force, lease)
