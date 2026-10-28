from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.cov_env import apply_coverage_env

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
        env=apply_coverage_env(dict(os.environ)),
        timeout=30,
        check=False,
    )

    # Assert
    assert (proc.returncode, proc.stderr) == (0, "")


def _load_monitor():
    import importlib.util

    spec = importlib.util.spec_from_file_location("context_monitor", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


monitor = _load_monitor()


@pytest.mark.parametrize(
    ("percentage", "expected"),
    [(95, "CRITICAL"), (85, "HIGH"), (70, "MED"), (50, "LOW"), (49, "")],
)
def test_get_level_names_each_band(percentage, expected):
    # Arrange
    value = percentage

    # Act
    result = monitor.get_level(value)

    # Assert
    assert result == expected


def test_context_percentage_is_zero_without_a_transcript(tmp_path):
    # Arrange
    missing = str(tmp_path / "none.jsonl")

    # Act
    result = monitor.get_context_percentage(missing, "opus")

    # Assert
    assert result == 0


def test_context_percentage_falls_back_to_the_default_limit(tmp_path):
    # Arrange
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("x" * 60000, encoding="utf-8")

    # Act
    result = monitor.get_context_percentage(str(transcript), "gpt")

    # Assert
    assert result == 10


@pytest.mark.parametrize(
    ("cost", "expected"),
    [("", ""), ("0.001", ""), ("1.5", "$1.50"), ("abc", ""), (["x"], "")],
)
def test_format_cost_shows_only_real_amounts(cost, expected):
    # Arrange
    value = cost

    # Act
    result = monitor.format_cost(value)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("age_seconds", "expected"),
    [(30, ""), (600, "10m"), (3 * 3600 + 120, "3h02m")],
)
def test_format_duration_reads_the_transcript_age(
    tmp_path, monkeypatch, age_seconds, expected
):
    # Arrange
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("{}", encoding="utf-8")
    created = transcript.stat().st_ctime
    monkeypatch.setattr(monitor.time, "time", lambda: created + age_seconds)

    # Act
    result = monitor.format_duration(str(transcript))

    # Assert
    assert result == expected


def test_format_duration_is_empty_without_a_transcript():
    # Arrange
    path = ""

    # Act
    result = monitor.format_duration(path)

    # Assert
    assert result == ""


def test_git_info_marks_a_dirty_branch(tmp_path):
    # Arrange
    subprocess.run(["git", "init", "-q", "-b", "work", str(tmp_path)], check=True)
    (tmp_path / "new.txt").write_text("x", encoding="utf-8")

    # Act
    result = monitor.get_git_info(str(tmp_path))

    # Assert
    assert result == "work*"


def test_git_info_is_empty_when_git_is_missing(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setenv("PATH", str(tmp_path))

    # Act
    result = monitor.get_git_info(str(tmp_path))

    # Assert
    assert result == ""


def test_git_info_is_empty_when_git_hangs(tmp_path, monkeypatch):
    # Arrange
    stub = tmp_path / "git"
    stub.write_text("#!/bin/sh\nexec /bin/sleep 5\n", encoding="utf-8")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))

    # Act
    result = monitor.get_git_info(str(tmp_path))

    # Assert
    assert result == ""


def test_main_prints_an_empty_line_for_unreadable_input():
    # Arrange
    stdin = "not json"

    # Act
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin,
        capture_output=True,
        text=True,
        env=apply_coverage_env(dict(os.environ)),
        timeout=30,
        check=False,
    )

    # Assert
    assert (proc.returncode, proc.stdout) == (0, "\n")
