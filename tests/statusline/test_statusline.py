"""Coverage for scripts/statusline.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path.home() / ".claude" / "scripts" / "statusline.py"


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
    """Build a JSONL transcript with N assistant turns each carrying given usage."""
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


# ---------------------------------------------------------------------------
# Basic happy path
# ---------------------------------------------------------------------------


def test_outputs_single_line(tmp_path):
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

    code, stdout, _ = run(payload)

    assert code == 0
    assert stdout.count("\n") <= 1, "statusline must be a single line"
    assert stdout.strip(), "statusline must produce output"


def test_includes_model_short_name(tmp_path):
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

    _, stdout, _ = run(payload)

    assert "opus" in stdout.lower()


def test_includes_cwd_basename(tmp_path):
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

    _, stdout, _ = run(payload)

    assert "my-project" in stdout


# ---------------------------------------------------------------------------
# Cache hit ratio
# ---------------------------------------------------------------------------


def test_cache_hit_ratio_high(tmp_path):
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

    _, stdout, _ = run(payload)

    assert "90%" in stdout or "89%" in stdout or "91%" in stdout


def test_cache_hit_ratio_zero(tmp_path):
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

    _, stdout, _ = run(payload)

    assert "0%" in stdout


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def test_cost_estimation_opus(tmp_path):
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

    _, stdout, _ = run(payload)

    assert "$2" in stdout, f"expected ~$22 in output, got: {stdout}"


def test_cost_estimation_sonnet(tmp_path):
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

    _, stdout, _ = run(payload)

    assert "$4" in stdout, f"expected ~$4 in output, got: {stdout}"


def test_cost_aggregates_across_multiple_turns(tmp_path):
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

    _, stdout, _ = run(payload)

    assert "$" in stdout


# ---------------------------------------------------------------------------
# Context-window percentage
# ---------------------------------------------------------------------------


def test_context_percentage_reported(tmp_path):
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

    _, stdout, _ = run(payload)

    import re

    assert re.search(r"\d+%", stdout), f"expected percentage in output, got: {stdout}"


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_handles_missing_transcript():
    payload = {
        "cwd": "/tmp",
        "model": "claude-opus-4-7",
        "transcript_path": "/nonexistent/path.jsonl",
    }

    code, stdout, _ = run(payload)

    assert code == 0
    assert stdout.strip()


def test_handles_malformed_jsonl(tmp_path):
    transcript = tmp_path / "bad.jsonl"
    transcript.write_text("not json\n{also not json}\nfine but no usage:{}\n")
    payload = {
        "cwd": str(tmp_path),
        "model": "claude-opus-4-7",
        "transcript_path": str(transcript),
    }

    code, stdout, _ = run(payload)

    assert code == 0
    assert stdout.strip()


def test_handles_empty_stdin():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="",
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stdout.strip()


def test_handles_missing_fields():
    payload = {"cwd": "/tmp"}

    code, stdout, _ = run(payload)

    assert code == 0
    assert stdout.strip()


# ---------------------------------------------------------------------------
# Performance budget
# ---------------------------------------------------------------------------


def test_completes_under_one_second(tmp_path):
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

    import time

    t0 = time.time()
    code, _, _ = run(payload)
    elapsed = time.time() - t0

    assert code == 0
    assert elapsed < 1.0, f"statusline took {elapsed:.2f}s, budget is 1.0s"
