"""Bypass environment variable coverage.

Item 125 of the plan. Validates the two opt-out env vars:

  - MUTATION_METHOD_DISABLE=1: full opt-out, audit-logged.
  - MUTATION_METHOD_AST=0: regex-only mode (skip ast-grep escalation).

The first should completely bypass detection. The second should still
detect via the regex floor; tests assert that mutations are still caught
even with AST escalation disabled.
"""

from __future__ import annotations

from conftest import make_write_payload


def test_disable_env_bypasses_block(run_hook):
    # Arrange
    snippet = """items.push(value)
items.sort()
arr.splice(0, 1)
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload, env={"MUTATION_METHOD_DISABLE": "1"})

    # Assert
    assert code == 0, f"DISABLE env var should bypass\n{stderr}"


def test_disable_env_value_other_than_one_does_not_bypass(run_hook):
    # Arrange
    snippet = "items.push(value)\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload, env={"MUTATION_METHOD_DISABLE": "0"})

    # Assert
    assert code == 2, "only DISABLE=1 should bypass; '0' must still block"
    assert "array.push" in stderr


def test_ast_zero_falls_back_to_regex_and_still_blocks(run_hook):
    # Arrange
    snippet = "items.push(value)\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload, env={"MUTATION_METHOD_AST": "0"})

    # Assert
    assert code == 2, "regex-only mode must still detect mutations"
    assert "array.push" in stderr


def test_disable_env_unset_default_blocks(run_hook):
    # Arrange
    snippet = "items.push(value)\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "array.push" in stderr
