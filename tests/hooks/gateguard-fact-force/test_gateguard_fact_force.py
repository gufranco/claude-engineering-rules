"""Coverage for gateguard-fact-force hook."""

from __future__ import annotations

import json
from pathlib import Path

HOOK = "gateguard-fact-force"


def _env(tmp_home: Path, **extra: str) -> dict[str, str]:
    env = {"HOME": str(tmp_home), "CLAUDE_HOOK_PROFILE": "strict"}
    env.update(extra)
    return env


def test_blocks_first_edit_without_evidence(tool_use, run_hook, tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("")
    payload = tool_use(
        "Edit",
        {
            "file_path": str(tmp_path / "file.py"),
            "old_string": "a",
            "new_string": "b",
        },
        session_id="s1",
        transcript_path=str(transcript),
    )

    code, _out, err = run_hook(HOOK, payload, env=_env(tmp_path))

    assert code == 2
    assert "evidence" in err


def test_allows_with_transcript_evidence(tool_use, assert_allows, tmp_path):
    target = tmp_path / "file.py"
    target.write_text("x")
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps({"role": "user", "content": str(target)}))
    payload = tool_use(
        "Edit",
        {"file_path": str(target), "old_string": "a", "new_string": "b"},
        session_id="s2",
        transcript_path=str(transcript),
    )

    assert_allows(HOOK, payload, env=_env(tmp_path))


def test_allows_with_disable_env(tool_use, run_hook, tmp_path):
    payload = tool_use(
        "Edit",
        {
            "file_path": str(tmp_path / "x.py"),
            "old_string": "a",
            "new_string": "b",
        },
    )

    code, _out, _err = run_hook(
        HOOK, payload, env=_env(tmp_path, GATEGUARD_DISABLE="1")
    )

    assert code == 0


def test_allows_new_file_write_with_opt_in(tool_use, assert_allows, tmp_path):
    payload = tool_use(
        "Write",
        {"file_path": str(tmp_path / "new.py"), "content": "x"},
    )

    assert_allows(HOOK, payload, env=_env(tmp_path, GATEGUARD_ALLOW_NEW_FILES="1"))


def test_allows_missing_file_path(tool_use, assert_allows, tmp_path):
    payload = tool_use("Edit", {"old_string": "a", "new_string": "b"})

    assert_allows(HOOK, payload, env=_env(tmp_path))


def test_second_edit_passes_without_check(tool_use, assert_allows, tmp_path):
    target = tmp_path / "file.py"
    target.write_text("x")
    cache_dir = tmp_path / ".claude" / "cache"
    cache_dir.mkdir(parents=True)
    import time

    (cache_dir / "gateguard-state.json").write_text(
        json.dumps(
            {
                "session-x": {
                    "ts": time.time(),
                    "files": {str(target): True},
                }
            }
        )
    )
    payload = tool_use(
        "Edit",
        {"file_path": str(target), "old_string": "a", "new_string": "b"},
        session_id="session-x",
        transcript_path="",
    )

    assert_allows(HOOK, payload, env=_env(tmp_path))
