from __future__ import annotations

from pathlib import Path

import pytest
from _dcb_support import load_module as _load_module


def _with_allowlist(monkeypatch, tmp_path, body: str):
    module = _load_module()
    listing = tmp_path / "solo-repos.txt"
    listing.write_text(body, encoding="utf-8")
    monkeypatch.setattr(module, "SOLO_REPO_ALLOWLIST", str(listing))
    return module


PUSH = "git " + "push " + "orig" + "in " + "ma" + "in"


@pytest.mark.parametrize(
    "target",
    ["main", "HEAD:main", "refs/heads/develop", "+master", "main --tags", "develop;"],
)
def test_a_protected_ref_is_named(target):
    # Arrange
    module = _load_module()

    # Act
    result = module._names_protected_ref(f" {target}")

    # Assert
    assert result is True


@pytest.mark.parametrize(
    "target",
    [
        "gfranco/eng-2330-cut-memory-main",
        "feature/main",
        "develop-2",
        "HEAD",
        "mainline",
    ],
)
def test_a_branch_that_only_ends_in_a_protected_name_is_not_protected(target):
    # Arrange
    module = _load_module()

    # Act
    result = module._names_protected_ref(f" {target}")

    # Assert
    assert result is False


def test_command_cwd_reads_a_leading_cd():
    # Arrange
    module = _load_module()

    # Act
    result = module._command_cwd(f"cd /repos/solo && {PUSH}")

    # Assert
    assert result == "/repos/solo"


def test_command_cwd_reads_a_quoted_leading_cd():
    # Arrange
    module = _load_module()

    # Act
    result = module._command_cwd(f'cd "/repos/my repo" && {PUSH}')

    # Assert
    assert result == "/repos/my repo"


def test_command_cwd_expands_a_tilde():
    # Arrange
    module = _load_module()
    expected = str(Path.home() / ".claude")

    # Act
    result = module._command_cwd(f"cd ~/.claude && {PUSH}")

    # Assert
    assert result == expected


def test_command_cwd_expands_home_inside_double_quotes(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setenv("HOME", str(tmp_path))
    module = _load_module()

    # Act
    result = module._command_cwd(f'cd "$HOME/.claude" && {PUSH}')

    # Assert
    assert result == f"{tmp_path}/.claude"


def test_command_cwd_expands_braced_home_unquoted(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setenv("HOME", str(tmp_path))
    module = _load_module()

    # Act
    result = module._command_cwd(f"cd ${{HOME}}/.claude && {PUSH}")

    # Assert
    assert result == f"{tmp_path}/.claude"


def test_command_cwd_keeps_home_literal_inside_single_quotes(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setenv("HOME", str(tmp_path))
    module = _load_module()

    # Act
    result = module._command_cwd(f"cd '$HOME/.claude' && {PUSH}")

    # Assert
    assert result == "$HOME/.claude"


def test_command_cwd_is_empty_without_a_leading_cd():
    # Arrange
    module = _load_module()

    # Act
    result = module._command_cwd(PUSH)

    # Assert
    assert result == ""


def test_command_cwd_ignores_a_cd_that_is_not_first():
    # Arrange
    module = _load_module()

    # Act
    result = module._command_cwd("git status && cd /repos/solo")

    # Assert
    assert result == ""


def test_solo_repo_matches_exact_path(monkeypatch, tmp_path):
    # Arrange
    module = _with_allowlist(monkeypatch, tmp_path, "/repos/solo\n")

    # Act
    result = module._is_solo_repo("/repos/solo")

    # Assert
    assert result is True


def test_solo_repo_matches_glob(monkeypatch, tmp_path):
    # Arrange
    module = _with_allowlist(monkeypatch, tmp_path, "/repos/personal/*\n")

    # Act
    result = module._is_solo_repo("/repos/personal/toy")

    # Assert
    assert result is True


def test_solo_repo_rejects_unlisted_path(monkeypatch, tmp_path):
    # Arrange
    module = _with_allowlist(monkeypatch, tmp_path, "/repos/solo\n")

    # Act
    result = module._is_solo_repo("/repos/team-service")

    # Assert
    assert result is False


@pytest.mark.parametrize(
    ("root", "expected"), [("/repos/team", False), ("/repos/solo", True)]
)
def test_solo_repo_ignores_blank_and_comment_lines(
    monkeypatch, tmp_path, root, expected
):
    # Arrange
    module = _with_allowlist(monkeypatch, tmp_path, "\n# /repos/team\n\n/repos/solo\n")

    # Act
    result = module._is_solo_repo(root)

    # Assert
    assert result is expected


def test_solo_repo_tolerates_trailing_slash(monkeypatch, tmp_path):
    # Arrange
    module = _with_allowlist(monkeypatch, tmp_path, "/repos/solo/\n")

    # Act
    result = module._is_solo_repo("/repos/solo")

    # Assert
    assert result is True


def test_solo_repo_false_for_empty_root(monkeypatch, tmp_path):
    # Arrange
    module = _with_allowlist(monkeypatch, tmp_path, "/repos/solo\n")

    # Act
    result = module._is_solo_repo("")

    # Assert
    assert result is False


def test_solo_repo_false_when_allowlist_missing(monkeypatch, tmp_path):
    # Arrange
    module = _load_module()
    monkeypatch.setattr(module, "SOLO_REPO_ALLOWLIST", str(tmp_path / "absent.txt"))

    # Act
    result = module._is_solo_repo("/repos/solo")

    # Assert
    assert result is False
