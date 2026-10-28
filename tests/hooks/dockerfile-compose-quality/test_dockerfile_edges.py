from __future__ import annotations

from _helpers.hook_assertions import assert_allowed

HOOK = "dockerfile-compose-quality"
PIN = "FROM node:22@sha256:abc\n"


def _write(tool_use, content: str):
    return tool_use("Write", {"file_path": "/repo/Dockerfile", "content": content})


def test_a_broken_json_copy_form_reads_its_words_as_sources(tool_use, run_hook):
    # Arrange
    payload = _write(tool_use, f'{PIN}COPY [".env" /app/\nUSER 1000\n')

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_full_dockerfile_without_from_has_no_user_warning(tool_use, run_hook):
    # Arrange
    payload = _write(tool_use, "RUN echo hi\n")

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
