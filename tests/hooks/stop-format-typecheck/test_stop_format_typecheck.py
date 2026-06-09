"""Tests for `hooks/stop-format-typecheck.py`.

Observable behavior:
- Empty/missing batch file: exit 0, no formatter calls.
- Batch file with paths: dedupe, group by extension, call each formatter once.
- TypeScript files trigger a tsc run scoped to each workspace root.
- Clear the batch file after success.
- Bypass via env or file registry returns 0 with batch untouched.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "stop-format-typecheck.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

_TESTS_DIR = ROOT / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _helpers.cov_env import apply_coverage_env  # noqa: E402


def _make_recording_stub(bin_dir: Path, name: str, log_file: Path) -> None:
    body = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        import sys, json
        from pathlib import Path
        log = Path({str(log_file)!r})
        existing = json.loads(log.read_text()) if log.exists() else []
        existing.append({{"tool": {name!r}, "args": sys.argv[1:]}})
        log.write_text(json.dumps(existing))
        sys.exit(0)
        """
    )
    target = bin_dir / name
    target.write_text(body, encoding="utf-8")
    target.chmod(0o755)


def _run(
    batch: Path, *, bin_dir: Path | None = None, env: dict | None = None
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged["CLAUDE_FORMATTER_BATCH"] = str(batch)
    if bin_dir is not None:
        merged["PATH"] = f"{bin_dir}:{merged.get('PATH', '')}"
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input="",
        capture_output=True,
        text=True,
        env=apply_coverage_env(merged),
        timeout=10,
    )


def test_empty_batch_file_noop(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    batch.write_text("", encoding="utf-8")
    # Act
    result = _run(batch)
    # Assert
    assert result.returncode == 0


def test_missing_batch_file_noop(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    # Act
    result = _run(batch)
    # Assert
    assert result.returncode == 0


def test_calls_prettier_once_for_js_files(tmp_path: Path) -> None:
    # Arrange
    a = tmp_path / "a.ts"
    a.write_text("x\n", encoding="utf-8")
    b = tmp_path / "b.tsx"
    b.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{a}\n{b}\n{a}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "prettier", log)
    # Act
    result = _run(batch, bin_dir=bin_dir)
    # Assert
    assert result.returncode == 0
    calls = json.loads(log.read_text())
    prettier_calls = [c for c in calls if c["tool"] == "prettier"]
    assert len(prettier_calls) == 1
    args = prettier_calls[0]["args"]
    assert "--write" in args
    assert str(a) in args
    assert str(b) in args


def test_clears_batch_file_after_run(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "f.py"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_recording_stub(bin_dir, "ruff", tmp_path / "calls.json")
    # Act
    result = _run(batch, bin_dir=bin_dir)
    # Assert
    assert result.returncode == 0
    assert batch.read_text(encoding="utf-8") == ""


def test_skips_missing_files(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{tmp_path}/missing.ts\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "prettier", log)
    # Act
    result = _run(batch, bin_dir=bin_dir)
    # Assert
    assert result.returncode == 0
    assert not log.exists()


def test_python_uses_ruff_when_black_missing(tmp_path: Path) -> None:
    # Arrange
    py = tmp_path / "f.py"
    py.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{py}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "ruff", log)
    python_dir = str(Path(sys.executable).parent)
    # Act
    result = _run(batch, bin_dir=bin_dir, env={"PATH": f"{bin_dir}:{python_dir}"})
    # Assert
    assert result.returncode == 0
    calls = json.loads(log.read_text())
    ruff_calls = [c for c in calls if c["tool"] == "ruff"]
    assert len(ruff_calls) == 1
    assert "format" in ruff_calls[0]["args"]


def test_python_prefers_black_when_available(tmp_path: Path) -> None:
    # Arrange
    py = tmp_path / "f.py"
    py.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{py}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "black", log)
    _make_recording_stub(bin_dir, "ruff", log)
    python_dir = str(Path(sys.executable).parent)
    # Act
    result = _run(batch, bin_dir=bin_dir, env={"PATH": f"{bin_dir}:{python_dir}"})
    # Assert
    assert result.returncode == 0
    calls = json.loads(log.read_text())
    assert any(c["tool"] == "black" for c in calls)
    assert not any(c["tool"] == "ruff" for c in calls)


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
    npx_calls = [c for c in calls if c["tool"] == "npx"]
    assert len(npx_calls) >= 1
    assert "tsc" in " ".join(npx_calls[0]["args"])


def test_env_disable_short_circuits(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "x.ts"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "prettier", log)
    # Act
    result = _run(batch, bin_dir=bin_dir, env={"STOP_FORMAT_DISABLE": "1"})
    # Assert
    assert result.returncode == 0
    assert not log.exists()
    assert batch.read_text(encoding="utf-8") != ""


def test_file_bypass_short_circuits(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "x.ts"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    state = tmp_path / "state.json"
    set_bypass("stop-format-typecheck", ttl_seconds=120, state_path=state)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "prettier", log)
    # Act
    result = _run(batch, bin_dir=bin_dir, env={"CLAUDE_BYPASS_STATE": str(state)})
    # Assert
    assert result.returncode == 0
    assert not log.exists()


def test_profile_disable_short_circuits(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "x.ts"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "prettier", log)
    # Act
    result = _run(
        batch,
        bin_dir=bin_dir,
        env={"CLAUDE_DISABLED_HOOKS": "stop-format-typecheck"},
    )
    # Assert
    assert result.returncode == 0
    assert not log.exists()


def test_go_files_invoke_gofmt(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "main.go"
    target.write_text("package main\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "gofmt", log)
    python_dir = str(Path(sys.executable).parent)
    # Act
    result = _run(batch, bin_dir=bin_dir, env={"PATH": f"{bin_dir}:{python_dir}"})
    # Assert
    assert result.returncode == 0
    calls = json.loads(log.read_text())
    assert any(c["tool"] == "gofmt" for c in calls)


def test_rust_files_invoke_rustfmt(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "main.rs"
    target.write_text("fn main() {}\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "rustfmt", log)
    python_dir = str(Path(sys.executable).parent)
    # Act
    result = _run(batch, bin_dir=bin_dir, env={"PATH": f"{bin_dir}:{python_dir}"})
    # Assert
    assert result.returncode == 0
    calls = json.loads(log.read_text())
    assert any(c["tool"] == "rustfmt" for c in calls)


def test_ruby_files_invoke_rubocop(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "main.rb"
    target.write_text("puts 'hi'\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "rubocop", log)
    python_dir = str(Path(sys.executable).parent)
    # Act
    result = _run(batch, bin_dir=bin_dir, env={"PATH": f"{bin_dir}:{python_dir}"})
    # Assert
    assert result.returncode == 0
    calls = json.loads(log.read_text())
    assert any(c["tool"] == "rubocop" for c in calls)


def test_shell_files_invoke_shfmt(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "x.sh"
    target.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "shfmt", log)
    python_dir = str(Path(sys.executable).parent)
    # Act
    result = _run(batch, bin_dir=bin_dir, env={"PATH": f"{bin_dir}:{python_dir}"})
    # Assert
    assert result.returncode == 0
    calls = json.loads(log.read_text())
    assert any(c["tool"] == "shfmt" for c in calls)


def test_workspace_skipped_when_dir_removed_between_discovery_and_run(
    tmp_path: Path,
) -> None:
    # Arrange: workspace exists at discovery time but is removed before tsc runs.
    # Cleanest emulation: point the ts file at a workspace that lacks both
    # package.json and tsconfig.json so _find_ts_workspace returns None.
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
    assert result.returncode == 0
    calls = json.loads(log.read_text())
    assert not any(c["tool"] == "npx" for c in calls)


def test_run_quietly_swallows_subprocess_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    import importlib.util as _util

    spec = _util.spec_from_file_location("_sft_mod", str(HOOK))
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def boom(*args: object, **_kwargs: object) -> object:
        raise OSError("simulated")

    monkeypatch.setattr(module.subprocess, "run", boom)
    # Act: should not raise despite OSError
    module._run_quietly(["does-not-matter"])
    # Assert: no exception propagated


def test_format_with_skips_missing_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    import importlib.util as _util

    spec = _util.spec_from_file_location("_sft_mod2", str(HOOK))
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.shutil, "which", lambda _name: None)
    calls: list[object] = []
    monkeypatch.setattr(module, "_run_quietly", lambda argv: calls.append(argv))
    # Act
    module._format_with("never-installed", "--write", "/tmp/x")
    # Assert
    assert calls == []


def test_main_skips_workspace_that_no_longer_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange: create workspace, queue a ts file under it, then remove the
    # workspace between batch processing and tsc invocation.
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "package.json").write_text("{}", encoding="utf-8")
    (ws / "tsconfig.json").write_text("{}", encoding="utf-8")
    target = ws / "src.ts"
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")

    import importlib.util as _util

    spec = _util.spec_from_file_location("_sft_mod4", str(HOOK))
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("CLAUDE_FORMATTER_BATCH", str(batch))
    # Remove workspace AFTER batch lookups but BEFORE tsc runs by patching
    # `_find_ts_workspace` to return a path that does not exist.
    monkeypatch.setattr(module, "_find_ts_workspace", lambda _p: tmp_path / "gone")
    monkeypatch.setattr(module, "_format_with", lambda *_a, **_k: None)
    called = {"npx": 0}

    def fake_run(*_a: object, **_k: object) -> object:
        called["npx"] += 1

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    # Act
    rc = module.main()
    # Assert
    assert rc == 0
    assert called["npx"] == 0


def test_find_ts_workspace_returns_none_when_missing(tmp_path: Path) -> None:
    # Arrange
    import importlib.util as _util

    spec = _util.spec_from_file_location("_sft_mod3", str(HOOK))
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Act
    result = module._find_ts_workspace(tmp_path / "x.ts")
    # Assert
    assert result is None


def test_tsc_failure_swallowed(tmp_path: Path) -> None:
    # Arrange: workspace exists; npx stub exits non-zero; hook must still succeed
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
    assert result.returncode == 0
