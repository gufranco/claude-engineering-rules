from __future__ import annotations

import json
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "dockerfile-compose-quality"


def test_blocks_copy_env_file(tool_use, run_hook):
    # Arrange
    content = "FROM node:22-alpine@sha256:abc\nCOPY .env /app/.env\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, "COPY of sensitive file")
    assert ".env" in stderr


def test_blocks_copy_env_variant(tool_use, run_hook):
    # Arrange
    content = "FROM node:22-alpine@sha256:abc\nCOPY .env.production /app/\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "COPY of sensitive file")


def test_blocks_copy_pem(tool_use, run_hook):
    # Arrange
    content = "FROM alpine\nCOPY cert.pem /etc/ssl/\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "COPY of sensitive file")


def test_blocks_copy_key(tool_use, run_hook):
    # Arrange
    content = "FROM alpine\nCOPY tls.key /etc/ssl/\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "COPY of sensitive file")


def test_blocks_copy_id_rsa(tool_use, run_hook):
    # Arrange
    content = "FROM alpine\nCOPY id_rsa /root/.ssh/\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "COPY of sensitive file")


def test_blocks_env_with_literal_secret(tool_use, run_hook):
    # Arrange
    content = "FROM node:22@sha256:abc\nENV API_TOKEN=abc123xyz\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_blocked(result, "literal value")
    assert "API_TOKEN" in stderr


def test_blocks_arg_with_literal_secret(tool_use, run_hook):
    # Arrange
    content = "FROM node:22@sha256:abc\nARG DB_PASSWORD=hunter2\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "literal value")


def test_allows_env_with_var_reference(tool_use, run_hook):
    # Arrange
    content = "FROM node:22@sha256:abc\nENV TOKEN=$BUILD_TOKEN\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_warns_floating_latest_tag(tool_use, run_hook):
    # Arrange
    content = 'FROM node:latest\nUSER 1001\nCMD ["node"]\n'
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "floating tag 'latest'" in context


def test_warns_lts_tag(tool_use, run_hook):
    # Arrange
    content = 'FROM node:lts\nUSER 1001\nCMD ["node"]\n'
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "floating tag 'lts'" in context


def test_warns_no_tag(tool_use, run_hook):
    # Arrange
    content = 'FROM ubuntu\nUSER 1001\nCMD ["bash"]\n'
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "no tag or digest" in context


def test_warns_user_root_in_final_stage(tool_use, run_hook):
    # Arrange
    content = 'FROM node:22@sha256:abc\nUSER root\nCMD ["node"]\n'
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "final stage runs as root" in context


def test_warns_missing_user_on_write(tool_use, run_hook):
    # Arrange
    content = 'FROM node:22@sha256:abc\nCMD ["node"]\n'
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "no USER directive in the final stage" in context


def test_no_warn_when_non_root_user(tool_use, run_hook):
    # Arrange
    content = 'FROM node:22@sha256:abc\nUSER 1001\nCMD ["node"]\n'
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_allowed(result)
    assert "WARN" not in stderr
    assert "no USER directive" not in stderr


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


def test_ignores_non_docker_file(tool_use, run_hook):
    # Arrange
    content = "COPY .env /app/\nprivileged: true\n"
    payload = tool_use("Write", {"file_path": "/repo/notes.txt", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_recognises_dockerfile_variant(tool_use, run_hook):
    # Arrange
    content = "FROM alpine\nCOPY .env /app/\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/api.Dockerfile", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "COPY of sensitive file")


def test_recognises_dockerfile_dot_prefix(tool_use, run_hook):
    # Arrange
    content = "FROM alpine\nCOPY .env /app/\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/Dockerfile.prod", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "COPY of sensitive file")


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


def test_edit_blocks_added_copy_env(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/Dockerfile",
            "old_string": "FROM alpine\n",
            "new_string": "FROM alpine\nCOPY .env /app/\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "COPY of sensitive file")


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


def test_edit_skips_missing_user_check(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/Dockerfile",
            "old_string": "FROM alpine\n",
            "new_string": "FROM alpine\nRUN echo hello\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_allowed(result)
    assert "no USER directive in the final stage" not in stderr


def test_bypass_env_var(tool_use, run_hook):
    # Arrange
    content = "FROM node:latest\nCOPY .env /app/.env\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload, env={"DOCKERFILE_QUALITY_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_ignores_unsupported_tool(tool_use, run_hook):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/Dockerfile"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_ignores_empty_content(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": ""})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_ignores_missing_file_path(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"content": "FROM alpine\nCOPY .env /app/\n"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_comments_do_not_trigger(tool_use, run_hook):
    # Arrange
    content = (
        "FROM node:22@sha256:abc\n"
        "# COPY .env /app/.env  -- this is documentation\n"
        "USER 1001\n"
    )
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _, stderr = assert_allowed(result)
    assert "COPY of sensitive file" not in stderr


def test_disabled_profile(tool_use, run_hook):
    # Arrange
    content = "FROM node:latest\nCOPY .env /app/.env\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(
        HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": "dockerfile-compose-quality"}
    )

    # Assert
    assert_allowed(result)


def test_write_without_tool_input_is_allowed_silently(run_hook):
    # Arrange
    payload = {"tool_name": "Write"}

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert (result.code, result.stdout, result.stderr) == (0, "", "")


def test_multistage_user_before_final_from_warns(tool_use, run_hook):
    # Arrange
    content = (
        "FROM node:22@sha256:abc AS builder\n"
        "USER 1001\n"
        "FROM gcr.io/distroless/nodejs22\n"
        'CMD ["node"]\n'
    )
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "no USER directive in the final stage" in context


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


def test_multiedit_with_empty_edit_skipped(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/Dockerfile",
            "edits": [
                {"old_string": "x", "new_string": ""},
                {"old_string": "y", "new_string": "FROM alpine\nUSER 1001\n"},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
