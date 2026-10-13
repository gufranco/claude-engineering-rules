from __future__ import annotations

import json

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "dockerfile-compose-quality"
PIN = "FROM node:22@sha256:abc\n"


def _write(tool_use, content: str):
    return tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})


@pytest.mark.parametrize(
    "line",
    [
        "COPY package.json .env /app/",
        "ADD .env /app/.env",
        'COPY ["src", "certs/server.key", "/app/"]',
        "COPY --chown=1000:1000 app.js id_rsa /app/",
    ],
    ids=["second-source", "add", "json-form", "after-flag"],
)
def test_a_sensitive_source_anywhere_in_copy_or_add_blocks(tool_use, run_hook, line):
    # Arrange
    payload = _write(tool_use, f"{PIN}{line}\nUSER 1000\n")

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "sensitive file")


def test_copying_an_example_env_file_is_allowed(tool_use, run_hook):
    # Arrange
    payload = _write(tool_use, f"{PIN}COPY .env.example /app/\nUSER 1000\n")

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_root_in_a_build_stage_is_not_reported_as_the_final_stage(tool_use, run_hook):
    # Arrange
    content = (
        "FROM node:22@sha256:abc AS build\nUSER root\nRUN make\n"
        'FROM node:22@sha256:abc\nUSER 1000\nCMD ["node"]\n'
    )
    payload = _write(tool_use, content)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert (result.code, result.stdout) == (0, "")


def test_root_as_the_final_user_is_reported(tool_use, run_hook):
    # Arrange
    content = f'{PIN}USER 1000\nRUN make\nUSER 0\nCMD ["node"]\n'
    payload = _write(tool_use, content)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "final stage runs as root" in context
