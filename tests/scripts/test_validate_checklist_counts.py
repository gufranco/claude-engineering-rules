from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from _helpers.cov_env import apply_coverage_env

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-checklist-counts.py"
CHECKLIST = "### 1. One\n- [ ] a\n- [x] b\n### 2. Two\n- [ ] c\n"


@pytest.fixture
def counts() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_checklist_counts", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tree(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


def test_counts_categories_and_items(counts, tmp_path):
    # Arrange
    root = _tree(tmp_path, {"checklists/checklist.md": CHECKLIST})

    # Act
    result = counts.count_checklist_items(str(root / "checklists/checklist.md"))

    # Assert
    assert result == (2, 3)


def test_mismatched_declarations_are_reported(counts, tmp_path, capsys):
    # Arrange
    root = _tree(
        tmp_path,
        {
            "checklists/checklist.md": CHECKLIST,
            "CLAUDE.md": "A 5 categories list with 3 items.\n",
            "README.md": "2 categories and 40 items.\n",
        },
    )

    # Act
    code = counts.main(str(root))

    # Assert
    assert code == 1
    assert capsys.readouterr().out == (
        "Checklist: 2 categories, 3 items\n\nCount mismatches found:\n"
        "  CLAUDE.md: declares 5 categories, checklist has 2\n"
        "  README.md: declares 40 items, checklist has 3 (diff > 10)\n"
    )


def test_matching_declarations_pass(counts, tmp_path, capsys):
    # Arrange
    root = _tree(tmp_path, {"checklists/checklist.md": CHECKLIST})

    # Act
    code = counts.main(str(root))

    # Assert
    assert (code, capsys.readouterr().out.splitlines()[-1]) == (
        0,
        "All count declarations match.",
    )


def test_a_missing_checklist_fails(counts, tmp_path, capsys):
    # Arrange
    root = tmp_path

    # Act
    code = counts.main(str(root))

    # Assert
    assert code == 1
    assert capsys.readouterr().err.startswith("ERROR: checklist not found at ")


def test_the_script_validates_this_repository():
    # Arrange
    env = apply_coverage_env(dict(os.environ))

    # Act
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

    # Assert
    assert (proc.returncode, proc.stdout.splitlines()[-1]) == (
        0,
        "All count declarations match.",
    )
