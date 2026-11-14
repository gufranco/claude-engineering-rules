from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "sandbox-link-guard"


@dataclass(frozen=True, slots=True)
class Layout:
    home: Path
    scratch: Path
    outside_repo: Path
    env: dict[str, str]


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    home = tmp_path / "home"
    (home / ".dotfiles" / "gnupg").mkdir(parents=True)
    temp_root = tmp_path / "tmpdir"
    scratch = temp_root / "claude-1000" / "session" / "scratchpad"
    scratch.mkdir(parents=True)
    outside_repo = tmp_path / "work" / "repo"
    (outside_repo / ".git").mkdir(parents=True)
    env = {"HOME": str(home), "TMPDIR": f"{temp_root}/"}
    return Layout(home, scratch, outside_repo, env)


def _run(tool_use, run_hook, layout: Layout, command: str, cwd: Path | None = None):
    payload = tool_use("Bash", {"command": command}, cwd=str(cwd or layout.home))
    return run_hook(HOOK, payload, env=layout.env)


def test_the_install_sandbox_link_into_the_real_repo_is_blocked(
    tool_use, run_hook, layout
):
    # Arrange
    command = (
        f'S={layout.scratch}/install-sandbox && mkdir -p "$S/home" && '
        f'ln -s {layout.home}/.dotfiles "$S/home/.dotfiles" && '
        f'env -i HOME="$S/home" bash {layout.home}/.dotfiles/install.sh'
    )

    # Act
    result = _run(tool_use, run_hook, layout, command)

    # Assert
    _code, stderr = assert_blocked(result, f"{layout.home}/.dotfiles")
    assert "git worktree add" in stderr


def test_a_relative_link_name_inside_the_sandbox_is_blocked(tool_use, run_hook, layout):
    # Arrange
    command = f'cd "{layout.scratch}" && ln -sfn ~/.dotfiles/gnupg .gnupg'

    # Act
    result = _run(tool_use, run_hook, layout, command)

    # Assert
    assert_blocked(result, f"{layout.home}/.dotfiles/gnupg")


def test_a_hard_link_to_a_real_file_is_blocked(tool_use, run_hook, layout):
    # Arrange
    command = f"ln {layout.home}/.dotfiles/install.sh {layout.scratch}/install.sh"

    # Act
    result = _run(tool_use, run_hook, layout, command)

    # Assert
    assert_blocked(result, "install.sh")


def test_a_target_directory_option_is_read(tool_use, run_hook, layout):
    # Arrange
    command = f"ln -s -t {layout.scratch} {layout.home}/.dotfiles"

    # Act
    result = _run(tool_use, run_hook, layout, command)

    # Assert
    assert_blocked(result, ".dotfiles")


def test_a_repository_outside_home_is_real(tool_use, run_hook, layout):
    # Arrange
    command = f"ln -s {layout.outside_repo}/src {layout.scratch}/src"

    # Act
    result = _run(tool_use, run_hook, layout, command)

    # Assert
    assert_blocked(result, f"{layout.outside_repo}/src")


def test_a_relative_source_resolves_from_the_link_folder(tool_use, run_hook, layout):
    # Arrange
    depth = "/".join([".."] * len(layout.scratch.relative_to(layout.home.parent).parts))
    command = f"ln -s {depth}/home/.dotfiles {layout.scratch}/dots"

    # Act
    result = _run(tool_use, run_hook, layout, command)

    # Assert
    assert_blocked(result, ".dotfiles")


def test_a_link_between_two_scratch_paths_is_allowed(tool_use, run_hook, layout):
    # Arrange
    command = f'S={layout.scratch} && ln -s "$S/a" "$S/b"'

    # Act
    result = _run(tool_use, run_hook, layout, command)

    # Assert
    assert_allowed(result)


def test_a_link_inside_its_own_mktemp_dir_is_allowed(tool_use, run_hook, layout):
    # Arrange
    command = 't=$(mktemp -d) && ln -s "$t/target" "$t/link" && ./run-tests "$t"'

    # Act
    result = _run(tool_use, run_hook, layout, command)

    # Assert
    assert_allowed(result)


def test_a_stub_pointing_at_a_system_binary_is_allowed(tool_use, run_hook, layout):
    # Arrange
    command = f"ln -s /usr/bin/true {layout.scratch}/bin/brew"

    # Act
    result = _run(tool_use, run_hook, layout, command)

    # Assert
    assert_allowed(result)


def test_installing_a_dotfile_into_home_is_allowed(tool_use, run_hook, layout):
    # Arrange
    command = f"ln -sfn {layout.home}/.dotfiles/zshrc {layout.home}/.zshrc"

    # Act
    result = _run(tool_use, run_hook, layout, command)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "ln --help",
        'ln -s "$UNKNOWN/a" "$OTHER/b"',
        "ln -s 'unterminated",
        "echo ln -s a b",
    ],
)
def test_commands_without_a_resolvable_link_are_allowed(
    tool_use, run_hook, layout, command
):
    # Arrange
    cwd = layout.home

    # Act
    result = _run(tool_use, run_hook, layout, command, cwd)

    # Assert
    assert_allowed(result)


def test_a_tool_other_than_bash_is_allowed(tool_use, run_hook, layout):
    # Arrange
    payload = tool_use("Write", {"file_path": "x", "content": "ln -s a b"})

    # Act
    result = run_hook(HOOK, payload, env=layout.env)

    # Assert
    assert_allowed(result)


def test_the_disable_variable_skips_the_check(tool_use, run_hook, layout):
    # Arrange
    command = f"ln -s {layout.home}/.dotfiles {layout.scratch}/dots"
    payload = tool_use("Bash", {"command": command}, cwd=str(layout.home))

    # Act
    result = run_hook(HOOK, payload, env={**layout.env, "SANDBOX_LINK_DISABLE": "1"})

    # Assert
    assert_allowed(result)
