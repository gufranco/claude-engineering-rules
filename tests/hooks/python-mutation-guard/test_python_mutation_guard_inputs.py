from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from _helpers.hook_assertions import assert_allowed, assert_blocked
from _pmg_support import (
    HOOK,
    OFFENDING,
    OFFENDING_PATH,
    _run_raw,
)


def test_raw_invalid_json_blocks():
    # Arrange
    stdin_text = "{not json at all"

    # Act
    code, _stderr = _run_raw(HOOK, stdin_text)

    # Assert
    assert code == 2


def test_empty_file_path_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": "", "content": OFFENDING})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": 42})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: python-mutation-guard could not read its input: tool_input.content is not a",
    )


def test_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit", {"file_path": OFFENDING_PATH, "old_string": "a", "new_string": 42}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: python-mutation-guard could not read its input: tool_input.new_string is not a",
    )


def test_non_dict_edits_block(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit", {"file_path": OFFENDING_PATH, "edits": ["not-a-dict", None]}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: python-mutation-guard could not read its input: tool_input.edits is not a list",
    )


def test_multiedit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {"file_path": OFFENDING_PATH, "edits": [{"old_string": "a", "new_string": 7}]},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: python-mutation-guard could not read its input: tool_input.edits is not a list",
    )


def test_profile_disable_short_circuits(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": OFFENDING})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": HOOK})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_live_bypass_entry_short_circuits(tmp_path, tool_use, run_hook):
    # Arrange
    state = tmp_path / "bypass.json"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    state.write_text(
        json.dumps(
            {"bypasses": [{"hook": HOOK, "expires_at": expires, "reason": "test"}]}
        )
    )
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": OFFENDING})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""
