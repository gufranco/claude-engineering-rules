from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRS = ("hooks", "hooks/_lib", ".github/scripts", "scripts", "tools")
MODULES = sorted(
    path
    for directory in SCRIPT_DIRS
    for path in (REPO_ROOT / directory).glob("*.py")
    if "__name__" in path.read_text(encoding="utf-8")
)


@pytest.mark.parametrize("path", MODULES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_importing_a_script_runs_nothing(path, monkeypatch, capsys):
    # Arrange
    monkeypatch.setattr(sys, "argv", [str(path)])
    name = "imported_" + path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)

    # Act
    spec.loader.exec_module(module)

    # Assert
    assert capsys.readouterr() == ("", "")
