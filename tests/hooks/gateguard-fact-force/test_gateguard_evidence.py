from __future__ import annotations

import json
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "gateguard-fact-force"


def _env(tmp_home: Path) -> dict[str, str]:
    return {"HOME": str(tmp_home), "CLAUDE_HOOK_PROFILE": "strict"}


def _assistant_call(name: str, tool_input: dict[str, str]) -> dict[str, object]:
    block = {"type": "tool_use", "id": "toolu_1", "name": name, "input": tool_input}
    return {"type": "assistant", "message": {"role": "assistant", "content": [block]}}


def _user_text(text: str) -> dict[str, object]:
    return {"type": "user", "message": {"role": "user", "content": text}}


def _edit(tool_use, transcript: Path, target: Path, session: str):
    return tool_use(
        "Edit",
        {"file_path": str(target), "old_string": "a", "new_string": "b"},
        session_id=session,
        transcript_path=str(transcript),
    )


def _transcript(tmp_path: Path, entries: list[dict[str, object]]) -> Path:
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "entries_for",
    [
        lambda target: [_assistant_call("Edit", {"file_path": str(target)})],
        lambda target: [
            _assistant_call(
                "Read", {"file_path": str(target.parent / "b" / target.name)}
            )
        ],
        lambda target: [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "x",
                            "content": str(target),
                        }
                    ],
                },
            }
        ],
    ],
    ids=["pending-call-only", "same-basename-elsewhere", "tool-output-mention"],
)
def test_a_mention_that_is_not_a_read_blocks(tool_use, run_hook, tmp_path, entries_for):
    # Arrange
    target = tmp_path / "a" / "index.ts"
    transcript = _transcript(tmp_path, entries_for(target))

    # Act
    result = run_hook(
        HOOK, _edit(tool_use, transcript, target, "s-block"), env=_env(tmp_path)
    )

    # Assert
    assert_blocked(result, "evidence")


@pytest.mark.parametrize(
    "entries_for",
    [
        lambda target: [_assistant_call("Read", {"file_path": str(target)})],
        lambda target: [_user_text(f"please fix {target}")],
        lambda target: [
            _assistant_call("Grep", {"pattern": "x", "path": str(target.parent)})
        ],
    ],
    ids=["read", "user-names-path", "grep-covers-path"],
)
def test_a_read_or_a_user_mention_allows(tool_use, run_hook, tmp_path, entries_for):
    # Arrange
    target = tmp_path / "a" / "index.ts"
    transcript = _transcript(tmp_path, entries_for(target))

    # Act
    result = run_hook(
        HOOK, _edit(tool_use, transcript, target, "s-allow"), env=_env(tmp_path)
    )

    # Assert
    assert_allowed(result)
