from __future__ import annotations

from faker import Faker
from _helpers.hook_assertions import assert_allowed, assert_blocked
from _tdd_gate_helpers import HOOK

fake = Faker()
Faker.seed(20261027)


def _test_path(tmp_path, suffix: str = ".py") -> str:
    return str(tmp_path / "tests" / f"test_{fake.word()}{suffix}")


def test_blocks_edit_that_removes_an_assertion(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": _test_path(tmp_path),
            "old_string": "    assert total == 1550\n    assert count == 2\n",
            "new_string": "    assert total == 1550\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "assertions drop from 2 to 1")


def test_blocks_edit_that_skips_a_test(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": _test_path(tmp_path, ".test.ts"),
            "old_string": "it('totals the order', async () => {",
            "new_string": "it.skip('totals the order', async () => {",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "skip markers rise from 0 to 1")


def test_allows_edit_that_keeps_every_assertion(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": _test_path(tmp_path),
            "old_string": "    assert result\n",
            "new_string": "    assert result == {'status': 'COMPLETED'}\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_assertion_removal_outside_test_files(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "src" / f"{fake.word()}.py"
    target.parent.mkdir(parents=True)
    target.write_text("assert invariant\n", encoding="utf-8")
    payload = tool_use(
        "Edit",
        {
            "file_path": str(target),
            "old_string": "assert invariant\n",
            "new_string": "check(invariant)\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_weakening_bypass_allows_the_edit(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": _test_path(tmp_path),
            "old_string": "    assert count == 2\n",
            "new_string": "",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"TEST_WEAKENING_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_tdd_bypass_does_not_disable_the_weakening_check(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": _test_path(tmp_path),
            "old_string": "    assert count == 2\n",
            "new_string": "",
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"TDD_GATE_DISABLE": "1"})

    # Assert
    assert_blocked(result, "weakens the test file")
