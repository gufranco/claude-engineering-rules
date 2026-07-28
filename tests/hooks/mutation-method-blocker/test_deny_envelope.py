"""Dual-channel deny contract.

The hook must report a block on both channels: the human-readable reason on
stderr for v1 orchestrators, and an equivalent `hookSpecificOutput` deny
envelope on stdout for v2 orchestrators.
"""

from __future__ import annotations

import json

from conftest import HOOK_PATH, run_hook_subprocess

BLOCKING_PAYLOAD = {
    "tool_name": "Write",
    "tool_input": {"file_path": "/repo/src/app.ts", "content": "items.push(value)"},
}


def test_block_exits_two_and_writes_reason_to_stderr():
    code, _stdout, stderr = run_hook_subprocess(HOOK_PATH, BLOCKING_PAYLOAD)

    assert code == 2
    assert "array.push" in stderr


def test_block_emits_v2_deny_envelope_on_stdout():
    _code, stdout, _stderr = run_hook_subprocess(HOOK_PATH, BLOCKING_PAYLOAD)

    envelope = json.loads(stdout)["hookSpecificOutput"]

    assert envelope["hookEventName"] == "PreToolUse"
    assert envelope["permissionDecision"] == "deny"
    assert "array.push" in envelope["permissionDecisionReason"]


def test_both_channels_carry_the_same_reason():
    _code, stdout, stderr = run_hook_subprocess(HOOK_PATH, BLOCKING_PAYLOAD)

    reason = json.loads(stdout)["hookSpecificOutput"]["permissionDecisionReason"]

    assert reason.strip() in stderr


def test_allowed_payload_emits_no_envelope():
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/src/app.ts",
            "content": "const next = [...items, value];",
        },
    }

    code, stdout, _stderr = run_hook_subprocess(HOOK_PATH, payload)

    assert code == 0
    assert stdout.strip() == ""
