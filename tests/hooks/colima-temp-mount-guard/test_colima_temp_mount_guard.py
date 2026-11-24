from __future__ import annotations

from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "colima-temp-mount-guard"


@pytest.fixture
def colima_home(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    (home / ".colima").mkdir(parents=True)
    return {"HOME": str(home)}


@pytest.fixture
def plain_home(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "plain"
    home.mkdir()
    return {"HOME": str(home)}


@pytest.mark.parametrize(
    "cmd",
    [
        "docker run --rm -v /tmp/work:/app node:24 ls",
        "docker run --rm -v /var/folders/ab/xyz/T/repo:/app image",
        "docker run --rm --volume=/private/tmp/data:/data image",
        "docker create --mount type=bind,source=/tmp/q,target=/x image",
        'docker run --rm -v "$TMPDIR/repo":/app image',
        'W=$(mktemp -d -t before-XXXXXX)/repo; git worktree add "$W" HEAD && docker run --rm -v "$W":/app image',
    ],
)
def test_blocks_a_temp_folder_mount_under_colima(tool_use, run_hook, colima_home, cmd):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act
    result = run_hook(HOOK, payload, env=colima_home)

    # Assert
    assert_blocked(result, "mounts it empty")


@pytest.mark.parametrize(
    "cmd",
    [
        'docker run --rm -v "$HOME/.cache/repo":/app image',
        'docker run --rm -v "$PWD":/app -v nijimi-node-modules:/app/node_modules image',
        'W=$(mktemp -d "$HOME/.cache/before-XXXXXX")/repo && docker run --rm -v "$W":/app image',
        "W=$(mktemp -d) && cp file $W/",
        "docker run --rm image echo /tmp/x",
        "docker volume ls",
        "ls /tmp",
    ],
)
def test_allows_home_mounts_named_volumes_and_commands_without_mounts(
    tool_use, run_hook, colima_home, cmd
):
    # Arrange
    payload = tool_use("Bash", {"command": cmd})

    # Act
    result = run_hook(HOOK, payload, env=colima_home)

    # Assert
    assert_allowed(result)


def test_allows_temp_mounts_without_colima(tool_use, run_hook, plain_home):
    # Arrange
    payload = tool_use("Bash", {"command": "docker run --rm -v /tmp/work:/app image"})

    # Act
    result = run_hook(HOOK, payload, env=plain_home)

    # Assert
    assert_allowed(result)


def test_disable_env_allows_a_temp_mount(tool_use, run_hook, colima_home):
    # Arrange
    payload = tool_use("Bash", {"command": "docker run --rm -v /tmp/work:/app image"})

    # Act
    result = run_hook(
        HOOK, payload, env={**colima_home, "COLIMA_TEMP_MOUNT_GUARD_DISABLE": "1"}
    )

    # Assert
    assert_allowed(result)


def test_ignores_other_tools_and_empty_commands(tool_use, run_hook, colima_home):
    # Arrange
    payloads = [
        tool_use("Read", {"file_path": "/tmp/x"}),
        tool_use("Bash", {"command": ""}),
    ]

    # Act
    results = [run_hook(HOOK, payload, env=colima_home) for payload in payloads]

    # Assert
    for result in results:
        assert_allowed(result)
