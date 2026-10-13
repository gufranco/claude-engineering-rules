from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2] / ".github" / "scripts" / "context-monitor.py"
)


@pytest.mark.parametrize(
    "model",
    [
        {"id": "claude-opus-5-5", "display_name": "Opus 5.5"},
        "claude-sonnet-5-5",
        None,
    ],
    ids=["object", "string", "missing"],
)
def test_every_model_shape_renders_a_status_line(tmp_path, model):
    # Arrange
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("x" * 4000, encoding="utf-8")
    payload = {
        "model": model,
        "workspace": {"current_dir": str(tmp_path)},
        "transcript_path": str(transcript),
    }

    # Act
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    # Assert
    assert (proc.returncode, proc.stderr) == (0, "")
