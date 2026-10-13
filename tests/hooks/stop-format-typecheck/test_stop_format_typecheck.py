from __future__ import annotations

import importlib.util as _util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from _helpers.cov_env import apply_coverage_env

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "stop-format-typecheck.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

TIMEOUT_S = 30
TSC_ARGS = [
    "--no-install",
    "tsc",
    "--noEmit",
    "--incremental",
    "--tsBuildInfoFile",
    "node_modules/.cache/tsc-hook.tsbuildinfo",
]


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
    batch: Path,
    *,
    bin_dir: Path | None = None,
    env: dict | None = None,
    stdin: str = "",
) -> subprocess.CompletedProcess[str]:
    merged = {
        **os.environ,
        "CLAUDE_FORMATTER_BATCH": str(batch),
        "CLAUDE_HOOK_AUDIT_DISABLE": "1",
        "CLAUDE_BYPASS_STATE": os.devnull,
    }
    if bin_dir is not None:
        merged["PATH"] = f"{bin_dir}:{merged.get('PATH', '')}"
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        env=apply_coverage_env(merged),
        timeout=TIMEOUT_S,
        check=False,
    )


def _load(name: str):
    spec = _util.spec_from_file_location(name, str(HOOK))
    assert spec is not None
    assert spec.loader is not None
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_empty_batch_file_is_consumed_without_output(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    batch.write_text("", encoding="utf-8")

    # Act
    result = _run(batch)

    # Assert
    assert (result.returncode, result.stdout, batch.exists()) == (0, "", False)


def test_missing_batch_file_produces_no_output(tmp_path: Path) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"

    # Act
    result = _run(batch)

    # Assert
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_calls_prettier_once_for_js_files(tmp_path: Path) -> None:
    # Arrange
    (tmp_path / ".prettierrc").write_text("{}", encoding="utf-8")
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
    assert calls == [{"tool": "prettier", "args": ["--write", str(a), str(b)]}]


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
    assert (result.returncode, batch.exists()) == (0, False)


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
    assert log.exists() is False


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
    assert calls == [{"tool": "ruff", "args": ["format", str(py)]}]


def test_python_prefers_ruff_when_both_are_available(tmp_path: Path) -> None:
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
    tools = [c["tool"] for c in json.loads(log.read_text())]
    assert (result.returncode, tools) == (0, ["ruff"])


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
    assert log.exists() is False
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
    assert log.exists() is False


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
    assert log.exists() is False


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
    assert calls == [{"tool": "gofmt", "args": ["-w", str(target)]}]


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
    assert calls == [{"tool": "rustfmt", "args": [str(target)]}]


def test_ruby_files_invoke_rubocop(tmp_path: Path) -> None:
    # Arrange
    (tmp_path / ".rubocop.yml").write_text("", encoding="utf-8")
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
    assert calls == [
        {"tool": "rubocop", "args": ["-A", "--fail-level", "E", str(target)]}
    ]


def test_shell_files_invoke_shfmt(tmp_path: Path) -> None:
    # Arrange
    (tmp_path / ".editorconfig").write_text("", encoding="utf-8")
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
    assert calls == [{"tool": "shfmt", "args": ["-w", str(target)]}]


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


def test_run_quietly_reports_a_tool_that_cannot_start(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    module = _load("_sft_mod")
    missing = str(tmp_path / "never-installed")

    # Act
    module._run_quietly([missing])

    # Assert
    assert capsys.readouterr().err.startswith(
        f"stop-format-typecheck: {missing} failed: "
    )


def test_format_with_skips_a_tool_missing_from_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    module = _load("_sft_mod2")
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    # Act
    module._format_with("never-installed", "--write", str(tmp_path / "x"))

    # Assert
    assert capsys.readouterr().err == ""


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


@pytest.mark.parametrize(
    ("tool", "name"), [("prettier", "notes.md"), ("shfmt", "run.sh")]
)
def test_a_formatter_the_project_does_not_configure_is_not_run(
    tmp_path: Path, tool: str, name: str
) -> None:
    # Arrange
    target = tmp_path / name
    target.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{target}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, tool, log)

    # Act
    result = _run(batch, bin_dir=bin_dir)

    # Assert
    assert (result.returncode, log.exists()) == (0, False)


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


def test_each_session_has_its_own_batch_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    module = _load("_sft_mod5")
    monkeypatch.delenv("CLAUDE_FORMATTER_BATCH", raising=False)
    cache = Path.home() / ".claude" / "cache"

    # Act
    paths = [module.batch_path("session-a"), module.batch_path("session-b")]

    # Assert
    assert paths == [
        cache / "edit-batch-session-a.txt",
        cache / "edit-batch-session-b.txt",
    ]


def test_an_unreadable_payload_is_reported_and_the_batch_still_runs(
    tmp_path: Path,
) -> None:
    # Arrange
    batch = tmp_path / "batch.txt"
    batch.write_text("", encoding="utf-8")

    # Act
    result = _run(batch, stdin="not json")

    # Assert
    assert result.returncode == 0
    assert result.stderr.startswith("stop-format-typecheck: unreadable payload: ")
    assert batch.exists() is False


def test_python_falls_back_to_black_when_ruff_is_missing(tmp_path: Path) -> None:
    # Arrange
    py = tmp_path / "f.py"
    py.write_text("x\n", encoding="utf-8")
    batch = tmp_path / "batch.txt"
    batch.write_text(f"{py}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.json"
    _make_recording_stub(bin_dir, "black", log)
    (bin_dir / "python3").symlink_to(sys.executable)

    # Act
    result = _run(batch, bin_dir=bin_dir, env={"PATH": str(bin_dir)})

    # Assert
    calls = json.loads(log.read_text())
    assert result.returncode == 0
    assert calls == [{"tool": "black", "args": ["--quiet", str(py)]}]


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
