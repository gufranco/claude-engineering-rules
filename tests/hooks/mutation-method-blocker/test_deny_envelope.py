from __future__ import annotations

import json

from conftest import HOOK_PATH, run_hook_subprocess

BLOCKING_PAYLOAD = {
    "tool_name": "Write",
    "tool_input": {"file_path": "/repo/src/app.ts", "content": "items.push(value)"},
}


def test_block_exits_two_and_writes_reason_to_stderr():
    # Arrange
    payload = BLOCKING_PAYLOAD

    # Act
    code, _stdout, stderr = run_hook_subprocess(HOOK_PATH, payload)

    # Assert
    assert code == 2
    assert "array.push" in stderr


def test_block_emits_v2_deny_envelope_on_stdout():
    # Arrange
    payload = BLOCKING_PAYLOAD

    # Act
    _code, stdout, _stderr = run_hook_subprocess(HOOK_PATH, payload)

    # Assert
    envelope = json.loads(stdout)["hookSpecificOutput"]
    assert envelope["hookEventName"] == "PreToolUse"
    assert envelope["permissionDecision"] == "deny"
    assert "array.push" in envelope["permissionDecisionReason"]


def test_both_channels_carry_the_same_reason():
    # Arrange
    payload = BLOCKING_PAYLOAD

    # Act
    _code, stdout, stderr = run_hook_subprocess(HOOK_PATH, payload)

    # Assert
    reason = json.loads(stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert reason.strip() in stderr


def test_allowed_payload_emits_no_envelope():
    # Arrange
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/src/app.ts",
            "content": "const next = [...items, value];",
        },
    }

    # Act
    code, stdout, _stderr = run_hook_subprocess(HOOK_PATH, payload)

    # Assert
    assert code == 0
    assert stdout.strip() == ""
