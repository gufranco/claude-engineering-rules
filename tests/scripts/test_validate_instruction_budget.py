"""Tests for .github/scripts/validate-instruction-budget.py.

Claude Code loads CLAUDE.md, every file it imports with an @ line, and every
Markdown file under rules/ into each session, and warns once the total passes
150,000 characters. The set once reached 539,200 characters with no check
noticing. These tests pin the gate that fails before the warning appears.

Source rule: standards/rules-vs-standards.md.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-instruction-budget.py"


@pytest.fixture
def budget_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_budget", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tree(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def test_counts_claude_md_imports_and_nested_rules(
    budget_module: ModuleType, tmp_path: Path
) -> None:
    _tree(
        tmp_path,
        {
            "CLAUDE.md": "abc\n@RTK.md\n",
            "RTK.md": "12345",
            "rules/a.md": "xy",
            "rules/lang/b.md": "z",
            "standards/full.md": "not loaded",
        },
    )

    files = budget_module.always_loaded_files(tmp_path)

    assert sorted(p.relative_to(tmp_path).as_posix() for p in files) == [
        "CLAUDE.md",
        "RTK.md",
        "rules/a.md",
        "rules/lang/b.md",
    ]
    assert budget_module.total_chars(files) == 20


def test_ignores_an_import_that_does_not_resolve(
    budget_module: ModuleType, tmp_path: Path
) -> None:
    _tree(tmp_path, {"CLAUDE.md": "@missing.md\n"})

    files = budget_module.always_loaded_files(tmp_path)

    assert [p.name for p in files] == ["CLAUDE.md"]


def test_passes_at_the_budget(budget_module: ModuleType, tmp_path: Path) -> None:
    _tree(tmp_path, {"CLAUDE.md": "a" * 10})

    exit_code = budget_module.check(tmp_path, budget=10)

    assert exit_code == 0


def test_fails_over_the_budget_and_names_the_largest_file(
    budget_module: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _tree(tmp_path, {"CLAUDE.md": "a" * 5, "rules/big.md": "b" * 20})

    exit_code = budget_module.check(tmp_path, budget=10)

    assert exit_code == 1
    assert "rules/big.md" in capsys.readouterr().out


def test_the_real_tree_is_within_budget(budget_module: ModuleType) -> None:
    exit_code = budget_module.check(REPO_ROOT, budget=budget_module.BUDGET_CHARS)

    assert exit_code == 0
