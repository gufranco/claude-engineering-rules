from __future__ import annotations

import re

import pytest

from _dcb_support import load_module

MODULE = load_module()


def _pattern(message: str) -> str:
    return next(regex for regex, text in MODULE.CRITICAL_PATHS if text == message)


@pytest.mark.parametrize(
    ("message", "command"),
    [
        ("Docker forced container removal", "docker rm -f app-db"),
        ("Docker forced container removal", "docker rm -vf app-db"),
        ("Docker forced container removal", "docker rm --force app-db"),
        ("Docker forced image removal", "docker rmi -f app:1"),
        ("Docker system prune -a removes all unused data", "docker system prune -a"),
        ("Docker Compose down -v destroys volumes", "docker compose down -v"),
        ("Deleting .env removes environment configuration", "rm -f .env"),
        ("Deleting .env removes environment configuration", "rm app/.env.local"),
        (
            "Deleting .env removes environment configuration",
            "rm -f /tmp/../Users/dev/app/.env",
        ),
        ("Podman system prune -a removes all unused data", "podman system prune --all"),
        ("Deleting .claude/ removes Claude configuration", "rm -rf ~/.claude"),
        (
            "Deleting .claude/ removes Claude configuration",
            'rm -rf "$HOME/.claude/hooks"',
        ),
        ("Deleting .git/ destroys repository history", "rm -rf repo/.git"),
        ("Deleting .git/ destroys repository history", "rm -rf .git"),
        ("Deleting .git/ destroys repository history", 'rm -rf "repo/.git/objects"'),
    ],
)
def test_still_matches_the_destructive_form(message: str, command: str) -> None:
    # Arrange
    pattern = _pattern(message)

    # Act
    match = re.search(pattern, command)

    # Assert
    assert match is not None


@pytest.mark.parametrize(
    ("message", "command"),
    [
        (
            "Docker forced container removal",
            "docker rm -v app-db && docker ps -a --format '{{.Names}}'",
        ),
        ("Docker forced container removal", "docker rm -v fullstack-db"),
        ("Docker forced image removal", "docker rmi app:1 && docker images --filter x"),
        (
            "Docker system prune -a removes all unused data",
            "docker system prune && ls -a",
        ),
        (
            "Docker Compose down -v destroys volumes",
            "docker compose down && docker ps -v",
        ),
        (
            "Deleting .env removes environment configuration",
            "rm -f /private/tmp/claude-501/scratchpad/vercel/.env.preview",
        ),
        (
            "Deleting .env removes environment configuration",
            "rm -f /tmp/pull/.env.production",
        ),
        (
            "Deleting .env removes environment configuration",
            "rm -f build.log && cat .env.example",
        ),
        (
            "Deleting .claude/ removes Claude configuration",
            'rm -rf /tmp/gate && cd "$HOME/.claude" && git log -1',
        ),
        (
            "Deleting .git/ destroys repository history",
            "rm -f out.log && git -C repo/.git log",
        ),
        (
            "Deleting .git/ destroys repository history",
            'rm -rf "$SCRATCH/mirror.git"',
        ),
        ("Deleting .git/ destroys repository history", "rm -f notes/.gitkeep"),
    ],
)
def test_ignores_a_flag_or_path_outside_the_destructive_call(
    message: str, command: str
) -> None:
    # Arrange
    pattern = _pattern(message)

    # Act
    match = re.search(pattern, command)

    # Assert
    assert match is None
