from __future__ import annotations
import json
import sys
from pathlib import Path
from _stop_format_typecheck_helpers import TSC_ARGS, _load, _make_recording_stub, _run


def test_typescript_workspace_runs_tsc(tmp_path: Path) -> None:
    # Arrange
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "package.json").write_text("{}", encoding="utf-8")
    (ws / "tsconfig.json").write_text("{}", encoding="utf-8")
    src = ws / "src"
    src.mkdir()
    target = src / "main.ts"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "prettier", log)
    _make_recording_stub(bin_dir, "npx", log)
    python_dir = str(Path(sys.executable).parent)

    # Act
    result = _run(batch, bin_dir=bin_dir, env={"PATH": f"{bin_dir}:{python_dir}"})

    # Assert
    assert result.returncode == 0
    calls = json.loads(log.read_text())
    assert [c for c in calls if c["tool"] == "npx"] == [
        {"tool": "npx", "args": TSC_ARGS}
    ]


def test_typescript_file_outside_a_workspace_skips_tsc(
    tmp_path: Path,
) -> None:
    # Arrange
    target = tmp_path / "main.ts"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "prettier", log)
    _make_recording_stub(bin_dir, "npx", log)
    python_dir = str(Path(sys.executable).parent)

    # Act
    result = _run(batch, bin_dir=bin_dir, env={"PATH": f"{bin_dir}:{python_dir}"})

    # Assert
    calls = json.loads(log.read_text()) if log.exists() else []
    assert (result.returncode, [c for c in calls if c["tool"] == "npx"]) == (0, [])


def test_find_ts_workspace_returns_none_when_missing(tmp_path: Path) -> None:
    # Arrange
    module = _load("_sft_mod3")

    # Act
    result = module._find_ts_workspace(tmp_path / "x.ts")

    # Assert
    assert result is None


def test_a_silent_tsc_failure_still_names_the_workspace(tmp_path: Path) -> None:
    # Arrange
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "package.json").write_text("{}", encoding="utf-8")
    (ws / "tsconfig.json").write_text("{}", encoding="utf-8")
    target = ws / "main.ts"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fail_npx = bin_dir / "npx"
    fail_npx.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    fail_npx.chmod(0o755)
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "prettier", log)
    python_dir = str(Path(sys.executable).parent)

    # Act
    result = _run(batch, bin_dir=bin_dir, env={"PATH": f"{bin_dir}:{python_dir}"})

    # Assert
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert result.returncode == 0
    assert f"tsc in {ws} failed:" in context


def test_a_tsc_failure_is_reported_back(tmp_path: Path) -> None:
    # Arrange
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "package.json").write_text("{}", encoding="utf-8")
    (ws / "tsconfig.json").write_text("{}", encoding="utf-8")
    target = ws / "main.ts"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    npx = bin_dir / "npx"
    npx.write_text(
        "#!/bin/sh\necho 'main.ts(1,1): error TS2304'\nexit 2\n", encoding="utf-8"
    )
    npx.chmod(0o755)

    # Act
    result = _run(batch, bin_dir=bin_dir)

    # Assert
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "error TS2304" in context


def test_a_missing_npx_is_reported_as_tsc_not_running(tmp_path: Path) -> None:
    # Arrange
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "package.json").write_text("{}", encoding="utf-8")
    (ws / "tsconfig.json").write_text("{}", encoding="utf-8")
    target = ws / "main.ts"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python_dir = str(Path(sys.executable).parent)

    # Act
    result = _run(batch, bin_dir=bin_dir, env={"PATH": f"{bin_dir}:{python_dir}"})

    # Assert
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert result.returncode == 0
    assert f"tsc in {ws} did not run:" in context
