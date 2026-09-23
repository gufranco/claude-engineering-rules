"""Tests for the session-start compile hook."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[3] / "hooks" / "vault-compile.py"


def load():
    spec = importlib.util.spec_from_file_location("vault_compile", HOOK)
    module = importlib.util.module_from_spec(spec)
    sys.modules["vault_compile"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run(
    payload: dict[str, str], env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_the_slug_matches_how_claude_code_names_a_project(tmp_path: Path) -> None:
    module = load()

    memory = module.memory_dir_for(
        Path("/Users/someone/Dropbox/Workspace/@ Pessoal/battle")
    )

    assert memory.parent.name == "-Users-someone-Dropbox-Workspace---Pessoal-battle"
    assert memory.name == "memory"


def test_no_vault_configured_is_silent(tmp_path: Path) -> None:
    result = run(
        {"cwd": str(tmp_path)}, {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    )

    assert result.returncode == 0
    assert result.stdout == ""


def test_a_broken_compile_never_fails_the_session(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / ".ci").mkdir(parents=True)
    (vault / ".ci" / "compile.py").write_text(
        "import sys; sys.exit(3)", encoding="utf-8"
    )
    project = tmp_path / "work"
    project.mkdir()
    module = load()
    memory = Path(
        str(module.memory_dir_for(project)).replace(str(Path.home()), str(tmp_path))
    )
    memory.mkdir(parents=True)

    result = run(
        {"cwd": str(project)},
        {
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "SECOND_BRAIN_VAULT": str(vault),
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""


def test_a_compile_that_changed_nothing_says_nothing(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / ".ci").mkdir(parents=True)
    (vault / ".ci" / "compile.py").write_text(
        "print('applied: 0'); print('unchanged: 12')", encoding="utf-8"
    )
    project = tmp_path / "work"
    project.mkdir()
    module = load()
    memory = Path(
        str(module.memory_dir_for(project)).replace(str(Path.home()), str(tmp_path))
    )
    memory.mkdir(parents=True)

    result = run(
        {"cwd": str(project)},
        {
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "SECOND_BRAIN_VAULT": str(vault),
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""


def test_a_compile_that_changed_something_reports_it(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / ".ci").mkdir(parents=True)
    (vault / ".ci" / "compile.py").write_text("print('applied: 3')", encoding="utf-8")
    project = tmp_path / "work"
    project.mkdir()
    module = load()
    memory = Path(
        str(module.memory_dir_for(project)).replace(str(Path.home()), str(tmp_path))
    )
    memory.mkdir(parents=True)

    result = run(
        {"cwd": str(project)},
        {
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "SECOND_BRAIN_VAULT": str(vault),
        },
    )

    assert result.returncode == 0
    assert "applied: 3" in result.stdout


@pytest.mark.parametrize("value", ["1"])
def test_the_bypass_switches_it_off(tmp_path: Path, value: str) -> None:
    result = run(
        {"cwd": str(tmp_path)},
        {
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "SECOND_BRAIN_VAULT": str(tmp_path),
            "VAULT_COMPILE_DISABLE": value,
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""


def test_a_worktree_with_no_memory_directory_yet_gets_one(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / ".ci").mkdir(parents=True)
    (vault / ".ci" / "compile.py").write_text("print('applied: 2')", encoding="utf-8")
    project = tmp_path / "work-eng-1933"
    project.mkdir()
    module = load()
    memory = Path(
        str(module.memory_dir_for(project)).replace(str(Path.home()), str(tmp_path))
    )
    memory.parent.mkdir(parents=True)

    result = run(
        {"cwd": str(project)},
        {
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "SECOND_BRAIN_VAULT": str(vault),
        },
    )

    assert result.returncode == 0
    assert memory.is_dir()
    assert "applied: 2" in result.stdout


def test_a_directory_claude_code_never_opened_is_left_alone(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / ".ci").mkdir(parents=True)
    (vault / ".ci" / "compile.py").write_text("print('applied: 2')", encoding="utf-8")
    project = tmp_path / "work"
    project.mkdir()
    module = load()
    memory = Path(
        str(module.memory_dir_for(project)).replace(str(Path.home()), str(tmp_path))
    )

    result = run(
        {"cwd": str(project)},
        {
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "SECOND_BRAIN_VAULT": str(vault),
        },
    )

    assert result.returncode == 0
    assert not memory.exists()
    assert result.stdout == ""
