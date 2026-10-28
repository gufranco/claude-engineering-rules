from __future__ import annotations

import json

from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "coverage-exclusion-guard"
NO_COVER = "# " + "prag" + "ma: no cover"


def test_a_write_adding_a_directive_is_blocked(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "app.py"), "content": f"x = 1  {NO_COVER}\n"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "adds 1 coverage exclusion directive")


def test_an_edit_lowering_a_threshold_is_blocked(tool_use, run_hook, tmp_path):
    # Arrange
    config = tmp_path / ".coveragerc"
    config.write_text("[report]\nfail_under = 100\n", encoding="utf-8")
    payload = tool_use(
        "Edit",
        {
            "file_path": str(config),
            "old_string": "fail_under = 100",
            "new_string": "fail_under = 90",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "threshold of 90, below 100")


def test_a_new_omit_entry_asks(tool_use, run_hook, tmp_path):
    # Arrange
    config = tmp_path / ".coveragerc"
    config.write_text("[run]\nomit =\n    */gen/*\n", encoding="utf-8")
    payload = tool_use(
        "Edit",
        {
            "file_path": str(config),
            "old_string": "    */gen/*\n",
            "new_string": "    */gen/*\n    */src/app.py\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    decision = json.loads(result.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "ask"
    assert "line 4: */src/app.py" in decision["permissionDecisionReason"]


def test_an_ordinary_edit_passes(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": str(tmp_path / "app.py"), "content": "x = 1\n"}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert (result.code, result.stdout) == (0, "")


def test_an_unresolvable_edit_passes(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": str(tmp_path / "missing.py"),
            "old_string": "a",
            "new_string": "b",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert (result.code, result.stdout) == (0, "")


def test_a_malformed_tool_input_fails_closed(run_hook):
    # Arrange
    payload = {"tool_name": "Write", "tool_input": "not a mapping"}

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "tool_input is not an object")


def test_the_bypass_variable_allows(tool_use, run_hook, tmp_path):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "app.py"), "content": f"x = 1  {NO_COVER}\n"},
    )

    # Act
    result = run_hook(HOOK, payload, env={"COVERAGE_EXCLUSION_GUARD_DISABLE": "1"})

    # Assert
    assert (result.code, result.stdout) == (0, "")
