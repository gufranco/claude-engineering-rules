from __future__ import annotations

import json

import pytest
from faker import Faker

from _helpers.hook_assertions import (
    HookResult,
    assert_allowed,
    assert_blocked,
    assert_modified,
)


def _envelope(decision: str, modified: object) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "permissionDecision": decision,
                "modifiedInput": modified,
            }
        }
    )


def test_hook_result_unpacks_as_code_stdout_stderr(faker: Faker) -> None:
    # Arrange
    stdout = faker.sentence()
    stderr = faker.sentence()

    # Act
    code, out, err = HookResult(2, stdout, stderr)

    # Assert
    assert (code, out, err) == (2, stdout, stderr)


def test_assert_blocked_returns_code_and_stderr_on_exit_two(faker: Faker) -> None:
    # Arrange
    reason = faker.word()
    result = HookResult(2, "", f"{faker.sentence()} {reason}")

    # Act
    returned = assert_blocked(result, reason)

    # Assert
    assert returned == (2, result.stderr)


def test_assert_blocked_without_reason_accepts_any_stderr(faker: Faker) -> None:
    # Arrange
    result = HookResult(2, "", faker.sentence())

    # Act
    returned = assert_blocked(result)

    # Assert
    assert returned == (2, result.stderr)


def test_assert_blocked_fails_when_the_hook_allowed(faker: Faker) -> None:
    # Arrange
    result = HookResult(0, "", faker.sentence())

    # Act
    with pytest.raises(AssertionError) as raised:
        assert_blocked(result)

    # Assert
    assert str(raised.value).splitlines()[0] == (
        "expected hook to block (exit 2) but got exit 0."
    )
    assert result.stderr in str(raised.value)


def test_assert_blocked_fails_when_the_reason_is_missing(faker: Faker) -> None:
    # Arrange
    reason = faker.uuid4()
    result = HookResult(2, "", faker.sentence())

    # Act
    with pytest.raises(AssertionError) as raised:
        assert_blocked(result, reason)

    # Assert
    assert str(raised.value).splitlines()[0] == (
        f"expected stderr to contain {reason!r}."
    )
    assert result.stderr in str(raised.value)


def test_assert_allowed_returns_code_and_stderr_on_exit_zero(faker: Faker) -> None:
    # Arrange
    result = HookResult(0, faker.sentence(), faker.sentence())

    # Act
    returned = assert_allowed(result)

    # Assert
    assert returned == (0, result.stderr)


def test_assert_allowed_fails_when_the_hook_blocked(faker: Faker) -> None:
    # Arrange
    result = HookResult(2, "", faker.sentence())

    # Act
    with pytest.raises(AssertionError) as raised:
        assert_allowed(result)

    # Assert
    assert str(raised.value).splitlines()[0] == (
        "expected hook to allow (exit 0) but got exit 2."
    )
    assert result.stderr in str(raised.value)


def test_assert_modified_returns_the_parsed_envelope(faker: Faker) -> None:
    # Arrange
    command = faker.sentence()
    stdout = _envelope("allow", {"command": command, "timeout": 5})
    result = HookResult(0, stdout, "")

    # Act
    parsed = assert_modified(result, {"command": command})

    # Assert
    assert parsed == json.loads(stdout)


def test_assert_modified_fails_on_a_nonzero_exit(faker: Faker) -> None:
    # Arrange
    result = HookResult(2, "", faker.sentence())

    # Act
    with pytest.raises(AssertionError) as raised:
        assert_modified(result, {})

    # Assert
    assert str(raised.value).splitlines()[0] == (
        "expected hook to allow with modified input (exit 0) but got exit 2."
    )
    assert result.stderr in str(raised.value)


def test_assert_modified_fails_on_empty_stdout() -> None:
    # Arrange
    result = HookResult(0, "  \n", "")

    # Act
    with pytest.raises(AssertionError) as raised:
        assert_modified(result, {})

    # Assert
    assert str(raised.value).splitlines()[0] == (
        "expected hook to print a v2 envelope on stdout but stdout was empty"
    )


def test_assert_modified_fails_when_the_decision_is_not_allow() -> None:
    # Arrange
    result = HookResult(0, _envelope("deny", {}), "")

    # Act
    with pytest.raises(AssertionError) as raised:
        assert_modified(result, {})

    # Assert
    assert str(raised.value).splitlines()[0] == (
        "expected permissionDecision=allow, got 'deny'"
    )


def test_assert_modified_fails_when_modified_input_is_not_a_dict(
    faker: Faker,
) -> None:
    # Arrange
    result = HookResult(0, _envelope("allow", [faker.word()]), "")

    # Act
    with pytest.raises(AssertionError) as raised:
        assert_modified(result, {})

    # Assert
    assert str(raised.value).splitlines()[0] == (
        "expected modifiedInput to be a dict, got list"
    )


def test_assert_modified_fails_when_an_expected_key_is_absent(faker: Faker) -> None:
    # Arrange
    result = HookResult(0, _envelope("allow", {}), "")

    # Act
    with pytest.raises(AssertionError) as raised:
        assert_modified(result, {"command": faker.sentence()})

    # Assert
    assert str(raised.value).splitlines()[0] == (
        "expected modifiedInput to include key 'command'"
    )


def test_assert_modified_fails_when_a_value_differs(faker: Faker) -> None:
    # Arrange
    actual = faker.sentence()
    expected = f"{actual} {faker.word()}"
    result = HookResult(0, _envelope("allow", {"command": actual}), "")

    # Act
    with pytest.raises(AssertionError) as raised:
        assert_modified(result, {"command": expected})

    # Assert
    assert str(raised.value).splitlines()[0] == (
        f"expected modifiedInput['command'] == {expected!r}, got {actual!r}"
    )
