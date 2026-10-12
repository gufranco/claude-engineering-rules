from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from _helpers.timing import timed  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "statusline.py"


def run(stdin_json: dict, env: dict | None = None):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(stdin_json),
        capture_output=True,
        text=True,
        timeout=6,
        env=env,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def make_transcript(tmp_path: Path, usages: list[dict]) -> Path:
    p = tmp_path / "transcript.jsonl"
    lines = []
    for i, usage in enumerate(usages):
        lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "uuid": f"u-{i}",
                    "message": {
                        "id": f"m-{i}",
                        "model": "claude-opus-4-7",
                        "usage": usage,
                    },
                }
            )
        )
    p.write_text("\n".join(lines) + "\n")
    return p


def assert_contains(out: str, needles: list[str]):
    for n in needles:
        assert n in out, f"expected {n!r} in statusline output, got: {out!r}"


def test_outputs_single_line(tmp_path):
    # Arrange
    transcript = make_transcript(
        tmp_path,
        [
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 1000,
            }
        ],
    )
    payload = {
        "cwd": str(tmp_path),
        "model": "claude-opus-4-7",
        "transcript_path": str(transcript),
    }

    # Act
    code, stdout, _ = run(payload)

    # Assert
    assert code == 0
    assert stdout.count("\n") <= 1, "statusline must be a single line"
    assert stdout.strip() != "", "statusline must produce output"


def test_includes_model_short_name(tmp_path):
    # Arrange
    transcript = make_transcript(
        tmp_path,
        [
            {
                "input_tokens": 10,
                "output_tokens": 10,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            }
        ],
    )
    payload = {
        "cwd": str(tmp_path),
        "model": "claude-opus-4-7",
        "transcript_path": str(transcript),
    }

    # Act
    _, stdout, _ = run(payload)

    # Assert
    assert "opus" in stdout.lower()


def test_includes_cwd_basename(tmp_path):
    # Arrange
    transcript = make_transcript(
        tmp_path,
        [
            {
                "input_tokens": 10,
                "output_tokens": 10,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            }
        ],
    )
    cwd = tmp_path / "my-project"
    cwd.mkdir()
    payload = {
        "cwd": str(cwd),
        "model": "claude-opus-4-7",
        "transcript_path": str(transcript),
    }

    # Act
    _, stdout, _ = run(payload)

    # Assert
    assert "my-project" in stdout


def test_cache_hit_ratio_high(tmp_path):
    # Arrange
    transcript = make_transcript(
        tmp_path,
        [
            {
                "input_tokens": 100,
                "output_tokens": 10,
                "cache_read_input_tokens": 9000,
                "cache_creation_input_tokens": 900,
            },
        ],
    )
    payload = {
        "cwd": str(tmp_path),
        "model": "claude-opus-4-7",
        "transcript_path": str(transcript),
    }

    # Act
    _, stdout, _ = run(payload)

    # Assert
    assert "90%" in stdout or "89%" in stdout or "91%" in stdout


def test_cache_hit_ratio_zero(tmp_path):
    # Arrange
    transcript = make_transcript(
        tmp_path,
        [
            {
                "input_tokens": 1000,
                "output_tokens": 10,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
        ],
    )
    payload = {
        "cwd": str(tmp_path),
        "model": "claude-opus-4-7",
        "transcript_path": str(transcript),
    }

    # Act
    _, stdout, _ = run(payload)

    # Assert
    assert "0%" in stdout


def test_cost_estimation_opus(tmp_path):
    # Arrange
    transcript = make_transcript(
        tmp_path,
        [
            {
                "input_tokens": 1_000_000,
                "output_tokens": 100_000,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            }
        ],
    )
    payload = {
        "cwd": str(tmp_path),
        "model": "claude-opus-4-7",
        "transcript_path": str(transcript),
    }

    # Act
    _, stdout, _ = run(payload)

    # Assert
    assert "$2" in stdout, f"expected ~$22 in output, got: {stdout}"


def test_cost_estimation_sonnet(tmp_path):
    # Arrange
    transcript = make_transcript(
        tmp_path,
        [
            {
                "input_tokens": 1_000_000,
                "output_tokens": 100_000,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            }
        ],
    )
    payload = {
        "cwd": str(tmp_path),
        "model": "claude-sonnet-4-6",
        "transcript_path": str(transcript),
    }

    # Act
    _, stdout, _ = run(payload)

    # Assert
    assert "$4" in stdout, f"expected ~$4 in output, got: {stdout}"


def test_cost_aggregates_across_multiple_turns(tmp_path):
    # Arrange
    usage = {
        "input_tokens": 1000,
        "output_tokens": 500,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    transcript = make_transcript(tmp_path, [usage] * 10)
    payload = {
        "cwd": str(tmp_path),
        "model": "claude-opus-4-7",
        "transcript_path": str(transcript),
    }

    # Act
    _, stdout, _ = run(payload)

    # Assert
    assert "$" in stdout


def test_context_percentage_reported(tmp_path):
    # Arrange
    transcript = make_transcript(
        tmp_path,
        [
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 100_000,
            },
        ],
    )
    payload = {
        "cwd": str(tmp_path),
        "model": "claude-opus-4-7",
        "transcript_path": str(transcript),
    }

    # Act
    _, stdout, _ = run(payload)

    # Assert
    assert re.search(r"\d+%", stdout) is not None, (
        f"expected percentage in output, got: {stdout}"
    )


def test_handles_missing_transcript():
    # Arrange
    payload = {
        "cwd": "/tmp",
        "model": "claude-opus-4-7",
        "transcript_path": "/nonexistent/path.jsonl",
    }

    # Act
    code, stdout, _ = run(payload)

    # Assert
    assert code == 0
    assert stdout.strip() != ""


def test_handles_malformed_jsonl(tmp_path):
    # Arrange
    transcript = tmp_path / "bad.jsonl"
    transcript.write_text("not json\n{also not json}\nfine but no usage:{}\n")
    payload = {
        "cwd": str(tmp_path),
        "model": "claude-opus-4-7",
        "transcript_path": str(transcript),
    }

    # Act
    code, stdout, _ = run(payload)

    # Assert
    assert code == 0
    assert stdout.strip() != ""


def test_handles_empty_stdin():
    # Arrange
    argv = [sys.executable, str(SCRIPT)]

    # Act
    proc = subprocess.run(
        argv,
        input="",
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    # Assert
    assert proc.returncode == 0
    assert proc.stdout.strip() != ""


def test_handles_missing_fields():
    # Arrange
    payload = {"cwd": "/tmp"}

    # Act
    code, stdout, _ = run(payload)

    # Assert
    assert code == 0
    assert stdout.strip() != ""


def test_completes_under_one_second(tmp_path):
    # Arrange
    usages = [
        {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_input_tokens": 1000,
            "cache_creation_input_tokens": 0,
        }
    ] * 1000
    transcript = make_transcript(tmp_path, usages)
    payload = {
        "cwd": str(tmp_path),
        "model": "claude-opus-4-7",
        "transcript_path": str(transcript),
    }

    # Act
    (code, _, _), elapsed_ms = timed(run, payload)

    # Assert
    assert code == 0
    assert elapsed_ms < 1000.0, f"statusline took {elapsed_ms:.0f}ms, budget is 1000ms"
