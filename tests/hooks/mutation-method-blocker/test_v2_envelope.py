"""v2 hookSpecificOutput envelope contract.

Items 149-152 of the plan. Verifies that block decisions emit the v2 envelope
on stdout in addition to the v1 stderr text, so v2-aware orchestrators can
read the structured reason without parsing free-form stderr. Also exercises
the assert_blocks / assert_allows / assert_defers helper assertions added in
conftest.py.
"""

from __future__ import annotations

from conftest import (
    assert_allows,
    assert_blocks,
    assert_defers,
    make_edit_payload,
    make_write_payload,
    parse_v2_envelope,
)


def test_block_emits_v2_envelope_with_deny(run_hook_v2):
    # Arrange
    payload = make_write_payload("/repo/src/app.ts", "items.push(value);\n")

    # Act
    code, stdout, stderr = run_hook_v2(payload)

    # Assert
    assert_blocks(code, stdout, stderr, reason_substring="array.push")


def test_block_envelope_carries_reason_text(run_hook_v2):
    # Arrange
    payload = make_write_payload("/repo/src/app.ts", "items.push(value);\n")

    # Act
    code, stdout, _stderr = run_hook_v2(payload)

    # Assert
    assert code == 2
    inner = parse_v2_envelope(stdout)
    assert inner is not None
    reason = inner.get("permissionDecisionReason", "")
    assert "array.push" in reason
    assert "items.push(value)" in reason


def test_block_envelope_event_name_is_pretooluse(run_hook_v2):
    # Arrange
    payload = make_write_payload("/repo/src/app.ts", "items.push(value);\n")

    # Act
    _code, stdout, _stderr = run_hook_v2(payload)

    # Assert
    inner = parse_v2_envelope(stdout)
    assert inner is not None
    assert inner.get("hookEventName") == "PreToolUse"


def test_block_envelope_includes_v1_stderr(run_hook_v2):
    # Arrange
    payload = make_write_payload("/repo/src/app.ts", "items.push(value);\n")

    # Act
    code, stdout, stderr = run_hook_v2(payload)

    # Assert
    assert code == 2
    assert stderr.strip()
    inner = parse_v2_envelope(stdout)
    assert inner is not None
    assert inner["permissionDecisionReason"].startswith("Blocked: in-place mutation")


def test_allow_path_has_no_v2_envelope(run_hook_v2):
    # Arrange
    payload = make_write_payload(
        "/repo/src/app.ts",
        "const next = [...items, value];\n",
    )

    # Act
    code, stdout, stderr = run_hook_v2(payload)

    # Assert
    assert_allows(code, stdout, stderr)
    assert parse_v2_envelope(stdout) is None


def test_defer_path_has_no_v2_envelope(run_hook_v2):
    # Arrange
    payload = make_write_payload("/repo/README.md", "# Documentation\n")

    # Act
    code, stdout, stderr = run_hook_v2(payload)

    # Assert
    assert_defers(code, stdout, stderr)


def test_block_envelope_on_edit_payload(run_hook_v2):
    # Arrange
    payload = make_edit_payload(
        "/repo/src/app.ts",
        "items.push(value);",
    )

    # Act
    code, stdout, stderr = run_hook_v2(payload)

    # Assert
    assert_blocks(code, stdout, stderr, reason_substring="array.push")
