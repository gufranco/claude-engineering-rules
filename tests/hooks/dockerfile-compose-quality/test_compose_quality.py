from __future__ import annotations

import json
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "dockerfile-compose-quality"


def test_blocks_compose_privileged(tool_use, run_hook):
    # Arrange
    content = "services:\n  app:\n    image: foo\n    privileged: true\n"
    payload = tool_use("Write", {"file_path": "/repo/compose.yml", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "privileged: true")


def test_blocks_compose_pid_host(tool_use, run_hook):
    # Arrange
    content = "services:\n  app:\n    image: foo\n    pid: host\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/docker-compose.yml", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "host namespace toggle")


def test_blocks_compose_ipc_host(tool_use, run_hook):
    # Arrange
    content = "services:\n  app:\n    image: foo\n    ipc: host\n"
    payload = tool_use("Write", {"file_path": "/repo/compose.yml", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "host namespace toggle")


def test_blocks_compose_network_mode_host(tool_use, run_hook):
    # Arrange
    content = "services:\n  app:\n    image: foo\n    network_mode: host\n"
    payload = tool_use("Write", {"file_path": "/repo/compose.yml", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "host namespace toggle")


def test_blocks_compose_userns_mode_host(tool_use, run_hook):
    # Arrange
    content = "services:\n  app:\n    image: foo\n    userns_mode: host\n"
    payload = tool_use("Write", {"file_path": "/repo/compose.yml", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "host namespace toggle")


def test_warns_top_level_version(tool_use, run_hook):
    # Arrange
    content = 'version: "3.8"\nservices:\n  app:\n    image: foo\n'
    payload = tool_use("Write", {"file_path": "/repo/compose.yml", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "version:" in context and "deprecated" in context


def test_warns_environment_literal_secret(tool_use, run_hook):
    # Arrange
    content = (
        "services:\n"
        "  app:\n"
        "    image: foo\n"
        "    environment:\n"
        "      DB_PASSWORD: hunter2\n"
    )
    payload = tool_use("Write", {"file_path": "/repo/compose.yml", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "DB_PASSWORD" in context


def test_no_warn_when_environment_uses_var(tool_use, run_hook):
    # Arrange
    content = (
        "services:\n"
        "  app:\n"
        "    image: foo\n"
        "    environment:\n"
        "      DB_PASSWORD: ${DB_PASSWORD}\n"
    )
    payload = tool_use("Write", {"file_path": "/repo/compose.yml", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_allowed(result)
    assert "DB_PASSWORD" not in stderr


def test_recognises_compose_override(tool_use, run_hook):
    # Arrange
    content = "services:\n  app:\n    privileged: true\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/docker-compose.override.yml", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "privileged: true")


def test_recognises_compose_yaml_extension(tool_use, run_hook):
    # Arrange
    content = "services:\n  app:\n    privileged: true\n"
    payload = tool_use("Write", {"file_path": "/repo/compose.yaml", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "privileged: true")


def test_multiedit_blocks_added_privileged(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/compose.yml",
            "edits": [
                {
                    "old_string": "    image: foo\n",
                    "new_string": "    image: foo\n    privileged: true\n",
                }
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "privileged: true")


def test_environment_block_exit_does_not_warn(tool_use, run_hook):
    # Arrange
    content = (
        "services:\n"
        "  app:\n"
        "    image: foo\n"
        "    environment:\n"
        "      LOG_LEVEL: info\n"
        "    ports:\n"
        '      - "127.0.0.1:8080:8080"\n'
    )
    payload = tool_use("Write", {"file_path": "/repo/compose.yml", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_allowed(result)
    assert "literal value" not in stderr
