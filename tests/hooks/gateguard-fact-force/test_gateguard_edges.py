from __future__ import annotations

import json
import time
from pathlib import Path

from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "gateguard-fact-force"
BLOCKED = "requires evidence of prior read or user instruction"


def _env(tmp_home: Path) -> dict[str, str]:
    return {"HOME": str(tmp_home), "CLAUDE_HOOK_PROFILE": "strict"}


def _payload(tool_use, transcript: Path, target: Path, session: str = "s1"):
    return tool_use(
        "Edit",
        {"file_path": str(target), "old_string": "a", "new_string": "b"},
        session_id=session,
        transcript_path=str(transcript),
    )


def _lines(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _read_call(target: Path) -> str:
    block = {"type": "tool_use", "name": "Read", "input": {"file_path": str(target)}}
    return json.dumps({"message": {"role": "assistant", "content": [block]}})


def _state_path(home: Path) -> Path:
    return home / ".claude" / "cache" / "gateguard-state.json"


def test_entries_that_carry_no_evidence_are_ignored(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "f.py"
    noise = [
        "not json",
        "[1, 2]",
        json.dumps({"message": "plain"}),
        json.dumps({"message": {"role": "system", "content": str(target)}}),
        json.dumps({"message": {"role": "user", "content": 5}}),
        json.dumps({"message": {"role": "assistant", "content": "text"}}),
        json.dumps(
            {
                "message": {
                    "role": "assistant",
                    "content": [
                        "loose",
                        {"type": "text", "text": str(target)},
                        {"type": "tool_use", "name": "Read", "input": "x"},
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "ls"},
                        },
                    ],
                }
            }
        ),
    ]
    payload = _payload(tool_use, _lines(tmp_path, noise), target)

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path))

    # Assert
    assert_blocked(result, BLOCKED)


def test_a_corrupt_state_file_starts_fresh(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "f.py"
    state = _state_path(tmp_path)
    state.parent.mkdir(parents=True)
    state.write_text("{broken", encoding="utf-8")
    payload = _payload(tool_use, _lines(tmp_path, [_read_call(target)]), target)

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path))

    # Assert
    assert_allowed(result)


def test_an_unwritable_state_file_still_allows(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "f.py"
    _state_path(tmp_path).mkdir(parents=True)
    payload = _payload(tool_use, _lines(tmp_path, [_read_call(target)]), target)

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path))

    # Assert
    assert_allowed(result)


def test_an_unreadable_transcript_is_no_evidence(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "f.py"
    folder = tmp_path / "transcript-dir"
    folder.mkdir()
    payload = _payload(tool_use, folder, target)

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path))

    # Assert
    assert_blocked(result, BLOCKED)


def test_a_session_entry_with_malformed_files_is_repaired(tool_use, run_hook, tmp_path):
    # Arrange
    target = tmp_path / "f.py"
    state = _state_path(tmp_path)
    state.parent.mkdir(parents=True)
    state.write_text(
        json.dumps({"s1": {"ts": time.time(), "files": []}}), encoding="utf-8"
    )
    payload = _payload(tool_use, _lines(tmp_path, [_read_call(target)]), target)

    # Act
    result = run_hook(HOOK, payload, env=_env(tmp_path))

    # Assert
    assert_allowed(result)
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert saved["s1"]["files"] == {str(target): True}
