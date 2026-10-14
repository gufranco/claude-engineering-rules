from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest
from _stop_format_typecheck_helpers import _make_recording_stub, _run


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
