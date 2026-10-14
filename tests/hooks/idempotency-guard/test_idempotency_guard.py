from __future__ import annotations

import json

from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "idempotency-guard"


def test_blocks_a_bare_mkdir_in_an_install_script(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/install.sh", "content": 'mkdir "$HOME/.cache/app"\n'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "`mkdir -p`")
    assert "IDEMPOTENCY_GUARD_DISABLE" in stderr


def test_blocks_timestamp_in_terraform_edit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/infra/main.tf",
            "old_string": "a",
            "new_string": "  tags = { at = timestamp() }\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "`timestamp()`")


def test_path_growth_is_advisory(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/home/u/.zshrc", "content": 'export PATH="$HOME/bin:$PATH"\n'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "typeset -U path" in context


def test_skips_bats_tests(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/tests/install.bats", "content": "mkdir build\n"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_disable_env_short_circuits(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/install.sh", "content": "mkdir build\n"}
    )

    # Act
    result = run_hook(HOOK, payload, env={"IDEMPOTENCY_GUARD_DISABLE": "1"})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_blocks_a_payload_that_is_not_an_object(run_hook):
    # Arrange
    command = "not-json"

    # Act
    result = run_hook(HOOK, command)

    # Assert
    assert_blocked(result, "could not read its input")
