"""Coverage for dockerfile-compose-quality hook.

Source rule: standards/container-security.md.
"""

from __future__ import annotations

HOOK = "dockerfile-compose-quality"


# --- Dockerfile BLOCKs -----------------------------------------------------


def test_blocks_copy_env_file(tool_use, assert_blocks):
    # Arrange
    content = "FROM node:22-alpine@sha256:abc\nCOPY .env /app/.env\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act / Assert
    _, stderr = assert_blocks(HOOK, payload, "COPY of sensitive file")
    assert ".env" in stderr


def test_blocks_copy_env_variant(tool_use, assert_blocks):
    # Arrange
    content = "FROM node:22-alpine@sha256:abc\nCOPY .env.production /app/\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act / Assert
    assert_blocks(HOOK, payload, "COPY of sensitive file")


def test_blocks_copy_pem(tool_use, assert_blocks):
    # Arrange
    content = "FROM alpine\nCOPY cert.pem /etc/ssl/\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act / Assert
    assert_blocks(HOOK, payload, "COPY of sensitive file")


def test_blocks_copy_key(tool_use, assert_blocks):
    # Arrange
    content = "FROM alpine\nCOPY tls.key /etc/ssl/\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act / Assert
    assert_blocks(HOOK, payload, "COPY of sensitive file")


def test_blocks_copy_id_rsa(tool_use, assert_blocks):
    # Arrange
    content = "FROM alpine\nCOPY id_rsa /root/.ssh/\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act / Assert
    assert_blocks(HOOK, payload, "COPY of sensitive file")


def test_blocks_env_with_literal_secret(tool_use, assert_blocks):
    # Arrange
    content = "FROM node:22@sha256:abc\nENV API_TOKEN=abc123xyz\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act / Assert
    _, stderr = assert_blocks(HOOK, payload, "literal value")
    assert "API_TOKEN" in stderr


def test_blocks_arg_with_literal_secret(tool_use, assert_blocks):
    # Arrange
    content = "FROM node:22@sha256:abc\nARG DB_PASSWORD=hunter2\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act / Assert
    assert_blocks(HOOK, payload, "literal value")


def test_allows_env_with_var_reference(tool_use, assert_allows):
    # Arrange
    content = "FROM node:22@sha256:abc\nENV TOKEN=$BUILD_TOKEN\nUSER 1001\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act / Assert
    assert_allows(HOOK, payload)


# --- Dockerfile WARNs ------------------------------------------------------


def test_warns_floating_latest_tag(tool_use, assert_allows):
    # Arrange
    content = 'FROM node:latest\nUSER 1001\nCMD ["node"]\n'
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    code, stderr = assert_allows(HOOK, payload)

    # Assert
    assert "floating tag 'latest'" in stderr


def test_warns_lts_tag(tool_use, assert_allows):
    # Arrange
    content = 'FROM node:lts\nUSER 1001\nCMD ["node"]\n'
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    code, stderr = assert_allows(HOOK, payload)

    # Assert
    assert "floating tag 'lts'" in stderr


def test_warns_no_tag(tool_use, assert_allows):
    # Arrange
    content = 'FROM ubuntu\nUSER 1001\nCMD ["bash"]\n'
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    code, stderr = assert_allows(HOOK, payload)

    # Assert
    assert "no tag or digest" in stderr


def test_warns_user_root_in_final_stage(tool_use, assert_allows):
    # Arrange
    content = 'FROM node:22@sha256:abc\nUSER root\nCMD ["node"]\n'
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    code, stderr = assert_allows(HOOK, payload)

    # Assert
    assert "USER root" in stderr


def test_warns_missing_user_on_write(tool_use, assert_allows):
    # Arrange
    content = 'FROM node:22@sha256:abc\nCMD ["node"]\n'
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    code, stderr = assert_allows(HOOK, payload)

    # Assert
    assert "no USER directive in the final stage" in stderr


def test_no_warn_when_non_root_user(tool_use, assert_allows):
    # Arrange
    content = 'FROM node:22@sha256:abc\nUSER 1001\nCMD ["node"]\n'
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    code, stderr = assert_allows(HOOK, payload)

    # Assert
    assert "WARN" not in stderr
    assert "no USER directive" not in stderr


# --- Compose BLOCKs --------------------------------------------------------


def test_blocks_compose_privileged(tool_use, assert_blocks):
    # Arrange
    content = "services:\n  app:\n    image: foo\n    privileged: true\n"
    payload = tool_use("Write", {"file_path": "/repo/compose.yml", "content": content})

    # Act / Assert
    assert_blocks(HOOK, payload, "privileged: true")


def test_blocks_compose_pid_host(tool_use, assert_blocks):
    # Arrange
    content = "services:\n  app:\n    image: foo\n    pid: host\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/docker-compose.yml", "content": content}
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "host namespace toggle")


def test_blocks_compose_ipc_host(tool_use, assert_blocks):
    # Arrange
    content = "services:\n  app:\n    image: foo\n    ipc: host\n"
    payload = tool_use("Write", {"file_path": "/repo/compose.yml", "content": content})

    # Act / Assert
    assert_blocks(HOOK, payload, "host namespace toggle")


def test_blocks_compose_network_mode_host(tool_use, assert_blocks):
    # Arrange
    content = "services:\n  app:\n    image: foo\n    network_mode: host\n"
    payload = tool_use("Write", {"file_path": "/repo/compose.yml", "content": content})

    # Act / Assert
    assert_blocks(HOOK, payload, "host namespace toggle")


def test_blocks_compose_userns_mode_host(tool_use, assert_blocks):
    # Arrange
    content = "services:\n  app:\n    image: foo\n    userns_mode: host\n"
    payload = tool_use("Write", {"file_path": "/repo/compose.yml", "content": content})

    # Act / Assert
    assert_blocks(HOOK, payload, "host namespace toggle")


# --- Compose WARNs ---------------------------------------------------------


def test_warns_top_level_version(tool_use, assert_allows):
    # Arrange
    content = 'version: "3.8"\nservices:\n  app:\n    image: foo\n'
    payload = tool_use("Write", {"file_path": "/repo/compose.yml", "content": content})

    # Act
    code, stderr = assert_allows(HOOK, payload)

    # Assert
    assert "version:" in stderr and "deprecated" in stderr


def test_warns_environment_literal_secret(tool_use, assert_allows):
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
    code, stderr = assert_allows(HOOK, payload)

    # Assert
    assert "DB_PASSWORD" in stderr


def test_no_warn_when_environment_uses_var(tool_use, assert_allows):
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
    code, stderr = assert_allows(HOOK, payload)

    # Assert
    assert "DB_PASSWORD" not in stderr


# --- Path filtering --------------------------------------------------------


def test_ignores_non_docker_file(tool_use, assert_allows):
    # Arrange
    content = "COPY .env /app/\nprivileged: true\n"
    payload = tool_use("Write", {"file_path": "/repo/notes.txt", "content": content})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_recognises_dockerfile_variant(tool_use, assert_blocks):
    # Arrange
    content = "FROM alpine\nCOPY .env /app/\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/api.Dockerfile", "content": content}
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "COPY of sensitive file")


def test_recognises_dockerfile_dot_prefix(tool_use, assert_blocks):
    # Arrange
    content = "FROM alpine\nCOPY .env /app/\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/Dockerfile.prod", "content": content}
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "COPY of sensitive file")


def test_recognises_compose_override(tool_use, assert_blocks):
    # Arrange
    content = "services:\n  app:\n    privileged: true\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/docker-compose.override.yml", "content": content}
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "privileged: true")


def test_recognises_compose_yaml_extension(tool_use, assert_blocks):
    # Arrange
    content = "services:\n  app:\n    privileged: true\n"
    payload = tool_use("Write", {"file_path": "/repo/compose.yaml", "content": content})

    # Act / Assert
    assert_blocks(HOOK, payload, "privileged: true")


# --- Edit / MultiEdit ------------------------------------------------------


def test_edit_blocks_added_copy_env(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/Dockerfile",
            "old_string": "FROM alpine\n",
            "new_string": "FROM alpine\nCOPY .env /app/\n",
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "COPY of sensitive file")


def test_multiedit_blocks_added_privileged(tool_use, assert_blocks):
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

    # Act / Assert
    assert_blocks(HOOK, payload, "privileged: true")


def test_edit_skips_missing_user_check(tool_use, assert_allows):
    """Edits cannot determine whether the post-edit file has a final-stage USER
    directive, so the missing-USER warning must not fire on Edit."""
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
    code, stderr = assert_allows(HOOK, payload)

    # Assert
    assert "no USER directive in the final stage" not in stderr


# --- Bypass ----------------------------------------------------------------


def test_bypass_env_var(tool_use, assert_allows):
    # Arrange
    content = "FROM node:latest\nCOPY .env /app/.env\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act / Assert
    assert_allows(HOOK, payload, env={"DOCKERFILE_QUALITY_DISABLE": "1"})


# --- Edge cases ------------------------------------------------------------


def test_ignores_unsupported_tool(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Read", {"file_path": "/repo/Dockerfile"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_ignores_empty_content(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": ""})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_ignores_missing_file_path(tool_use, assert_allows):
    # Arrange
    payload = tool_use("Write", {"content": "FROM alpine\nCOPY .env /app/\n"})

    # Act / Assert
    assert_allows(HOOK, payload)


def test_comments_do_not_trigger(tool_use, assert_allows):
    # Arrange
    content = (
        "FROM node:22@sha256:abc\n"
        "# COPY .env /app/.env  -- this is documentation\n"
        "USER 1001\n"
    )
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    code, stderr = assert_allows(HOOK, payload)

    # Assert
    assert "COPY of sensitive file" not in stderr


def test_disabled_profile(tool_use, assert_allows):
    """Hook short-circuits when its ID is in CLAUDE_DISABLED_HOOKS."""
    # Arrange
    content = "FROM node:latest\nCOPY .env /app/.env\n"
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act / Assert
    assert_allows(
        HOOK,
        payload,
        env={"CLAUDE_DISABLED_HOOKS": "dockerfile-compose-quality"},
    )


def test_invalid_json_silently_allows(tool_use, assert_allows):
    """Garbage on stdin should not crash the hook; it should exit 0."""
    # Arrange
    # The harness only accepts dicts; emulate the contract by sending an empty
    # payload that yields no tool_input.
    payload = {"tool_name": "Write"}

    # Act / Assert
    assert_allows(HOOK, payload)


def test_multistage_user_before_final_from_warns(tool_use, assert_allows):
    """A USER in the builder stage does not satisfy the final stage."""
    # Arrange
    content = (
        "FROM node:22@sha256:abc AS builder\n"
        "USER 1001\n"
        "FROM gcr.io/distroless/nodejs22\n"
        'CMD ["node"]\n'
    )
    payload = tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})

    # Act
    code, stderr = assert_allows(HOOK, payload)

    # Assert
    assert "no USER directive in the final stage" in stderr


def test_environment_block_exit_does_not_warn(tool_use, assert_allows):
    """Content after the environment block should not be scanned as env."""
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
    code, stderr = assert_allows(HOOK, payload)

    # Assert
    assert "literal value" not in stderr


def test_multiedit_with_empty_edit_skipped(tool_use, assert_allows):
    """A MultiEdit with an empty new_string should not crash; just skip it."""
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

    # Act / Assert
    assert_allows(HOOK, payload)
