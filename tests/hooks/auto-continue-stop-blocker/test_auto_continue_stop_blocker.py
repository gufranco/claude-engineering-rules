"""Coverage for auto-continue-stop-blocker hook.

Source rule: `~/.claude/CLAUDE.md` "Execute, don't ask".
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = "auto-continue-stop-blocker"


def _write_transcript(tmp_path: Path, messages: list[dict]) -> str:
    """Write a JSONL transcript file and return its absolute path."""
    p = tmp_path / "transcript.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m) + "\n")
    return str(p)


def _assistant_text_msg(text: str) -> dict:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }


def _assistant_with_tool(tool_name: str, text: str = "") -> dict:
    content = []
    if text:
        content.append({"type": "text", "text": text})
    content.append({"type": "tool_use", "name": tool_name, "input": {}})
    return {"type": "assistant", "message": {"content": content}}


def _user_msg(text: str) -> dict:
    return {"type": "user", "message": {"content": text}}


@pytest.fixture
def _run(run_hook):
    """Wrapper that returns (code, stderr) for a raw Stop payload via the shared harness."""

    def _runner(payload: dict, env: dict | None = None) -> tuple[int, str]:
        code, _stdout, stderr = run_hook(HOOK, payload, env=env)
        return code, stderr

    return _runner


@pytest.mark.parametrize(
    "phrase",
    [
        "Stopping here for the moment.",
        "This is a natural checkpoint.",
        "Tell me to continue with the rest.",
        "Say go when ready.",
        "If you want me to continue, let me know.",
        "Or which phase to jump to next?",
        "Next batch: more work coming.",
        "Awaiting your direction.",
        "Give me the go-ahead.",
        "Continuing in subsequent turns.",
        "Resume in the next session.",
        "Would you like me to continue?",
        "I'll continue in the next session.",
    ],
)
def test_blocks_checkpoint_patterns(tmp_path, phrase, _run):
    # Arrange
    transcript = _write_transcript(tmp_path, [_assistant_text_msg(phrase)])
    payload = {"transcript_path": transcript}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 2, f"expected block (exit 2), got {code}.\nstderr:\n{stderr}"


def test_blocks_done_summary_with_next_batch(tmp_path, _run):
    # Arrange
    text = "DONE: completed step 3. Next batch starts after this."
    transcript = _write_transcript(tmp_path, [_assistant_text_msg(text)])
    payload = {"transcript_path": transcript}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 2, stderr


def test_allows_clean_completion(tmp_path, _run):
    # Arrange
    text = "FIXED: race condition in createUser by adding cleanup order."
    transcript = _write_transcript(tmp_path, [_assistant_text_msg(text)])
    payload = {"transcript_path": transcript}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 0, f"expected allow, got {code}.\nstderr:\n{stderr}"


def test_allows_when_ask_user_question_called(tmp_path, _run):
    # Arrange: even if the text contains a checkpoint phrase, AskUserQuestion legitimizes the stop
    transcript = _write_transcript(
        tmp_path,
        [_assistant_with_tool("AskUserQuestion", text="Tell me to continue.")],
    )
    payload = {"transcript_path": transcript}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 0, stderr


def test_allows_when_exit_plan_mode_called(tmp_path, _run):
    # Arrange
    transcript = _write_transcript(
        tmp_path,
        [_assistant_with_tool("ExitPlanMode", text="Say go when ready.")],
    )
    payload = {"transcript_path": transcript}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 0, stderr


def test_breaks_recursion_when_already_active(tmp_path, _run):
    # Arrange
    transcript = _write_transcript(
        tmp_path, [_assistant_text_msg("Tell me to continue when ready.")]
    )
    payload = {"transcript_path": transcript, "stop_hook_active": True}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 0, stderr


def test_bypass_env_var_allows(tmp_path, _run):
    # Arrange
    transcript = _write_transcript(
        tmp_path, [_assistant_text_msg("Tell me to continue.")]
    )
    payload = {"transcript_path": transcript}

    # Act
    code, stderr = _run(payload, env={"AUTO_CONTINUE_DISABLE": "1"})

    # Assert
    assert code == 0, stderr


def test_missing_transcript_path_allows(_run):
    # Arrange
    payload = {}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 0, stderr


def test_nonexistent_transcript_allows(_run):
    # Arrange
    payload = {"transcript_path": "/tmp/nonexistent-transcript-xyz123.jsonl"}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 0, stderr


def test_invalid_json_returns_zero(_run):
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "auto-continue-stop-blocker.py"
    )

    # Act
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )

    # Assert
    assert proc.returncode == 0


def test_empty_transcript_allows(tmp_path, _run):
    # Arrange: transcript exists but has no assistant turns
    transcript = _write_transcript(tmp_path, [_user_msg("hello")])
    payload = {"transcript_path": transcript}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 0, stderr


def test_transcript_with_invalid_jsonl_lines(tmp_path, _run):
    # Arrange
    p = tmp_path / "transcript.jsonl"
    with p.open("w", encoding="utf-8") as f:
        f.write("not valid json\n")
        f.write(json.dumps(_assistant_text_msg("clean work")) + "\n")
        f.write("\n")
        f.write("also not json\n")
    payload = {"transcript_path": str(p)}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 0, stderr


def test_transcript_with_string_content(tmp_path, _run):
    # Arrange: message.content can be a string instead of a list
    msg = {"type": "assistant", "message": {"content": "Tell me to continue."}}
    transcript = _write_transcript(tmp_path, [msg])
    payload = {"transcript_path": transcript}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 2, stderr


def test_transcript_with_non_dict_block(tmp_path, _run):
    # Arrange: malformed block (string instead of dict)
    msg = {
        "type": "assistant",
        "message": {"content": ["not-a-dict", {"type": "text", "text": "clean"}]},
    }
    transcript = _write_transcript(tmp_path, [msg])
    payload = {"transcript_path": transcript}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 0, stderr


def test_finds_most_recent_assistant_turn(tmp_path, _run):
    # Arrange: leak in older turn, clean in newest
    transcript = _write_transcript(
        tmp_path,
        [
            _assistant_text_msg("Tell me when to continue."),
            _user_msg("continue"),
            _assistant_text_msg("FIXED: work complete."),
        ],
    )
    payload = {"transcript_path": transcript}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 0, f"newest turn was clean, should allow.\nstderr:\n{stderr}"


def test_finds_leak_in_newest_turn(tmp_path, _run):
    # Arrange: clean in older turn, leak in newest
    transcript = _write_transcript(
        tmp_path,
        [
            _assistant_text_msg("FIXED: earlier work"),
            _user_msg("more"),
            _assistant_text_msg("Awaiting your direction."),
        ],
    )
    payload = {"transcript_path": transcript}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 2, stderr


def test_tool_use_block_without_name_is_skipped(tmp_path, _run):
    # Arrange: tool_use block missing the 'name' field
    msg = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use"},
                {"type": "text", "text": "Tell me to continue."},
            ]
        },
    }
    transcript = _write_transcript(tmp_path, [msg])
    payload = {"transcript_path": transcript}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 2, stderr


def test_text_block_with_non_string_text(tmp_path, _run):
    # Arrange: text block where 'text' is not a string
    msg = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": 12345},
                {"type": "text", "text": "Tell me to continue."},
            ]
        },
    }
    transcript = _write_transcript(tmp_path, [msg])
    payload = {"transcript_path": transcript}

    # Act
    code, stderr = _run(payload)

    # Assert
    assert code == 2, stderr
