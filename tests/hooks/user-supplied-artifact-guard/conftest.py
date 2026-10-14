from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from _usag_support import GIT_ENV, HOOK_PATH, _stage


@pytest.fixture()
def hook(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("_usag_mod", str(HOOK_PATH))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.delenv("USER_SUPPLIED_ARTIFACT_DISABLE", raising=False)
    monkeypatch.delenv("CLAUDE_DISABLED_HOOKS", raising=False)
    monkeypatch.setenv("CLAUDE_HOOK_AUDIT_DISABLE", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    monkeypatch.setattr("_lib.bypass.STATE_PATH", Path(os.devnull))
    return module


@pytest.fixture()
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-q", str(repo)],
        check=True,
        env={**os.environ, **GIT_ENV},
        timeout=30,
    )
    monkeypatch.chdir(repo)
    return repo


@pytest.fixture()
def staged_rom(hook: ModuleType, git_repo: Path, faker) -> Path:
    _stage(git_repo, "game.gba", faker.binary(length=64))
    return git_repo
