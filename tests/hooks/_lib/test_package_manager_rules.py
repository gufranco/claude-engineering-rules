from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.package_manager_rules import violations  # noqa: E402


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("npm install", ["npm install: use pnpm install"]),
        ("npm ci", ["npm ci: use pnpm install --frozen-lockfile"]),
        ("cd web && npm run build", ["npm run build: use pnpm run build"]),
        ("npx prettier --check .", ["npx prettier: use pnpm exec prettier"]),
        ("yarn add zod", ["yarn add zod: use pnpm add zod"]),
        ("pip install ruff", ["pip install: use uv add, uv sync or uv tool install"]),
        (
            "python3 -m pip install -r requirements.txt",
            ["pip install: use uv add, uv sync or uv tool install"],
        ),
        (
            "npm i && pip3 install x",
            [
                "npm i: use pnpm install",
                "pip install: use uv add, uv sync or uv tool install",
            ],
        ),
    ],
)
def test_npm_npx_yarn_and_pip_installs_are_named_with_their_replacement(
    command, expected
):
    # Arrange
    candidate = command

    # Act
    result = violations(candidate)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    "command",
    [
        "pnpm install --frozen-lockfile",
        "corepack pnpm exec prettier --check .",
        "uv pip install -e .",
        "uv sync --locked",
        "npm --version",
        "npx -v",
        "yarn help",
        "pip index versions ruff",
        "echo 'run npm install first'",
        "git commit -m 'drop npm install from the docs'",
    ],
)
def test_pnpm_uv_version_probes_and_quoted_text_pass(command):
    # Arrange
    candidate = command

    # Act
    result = violations(candidate)

    # Assert
    assert result == []
