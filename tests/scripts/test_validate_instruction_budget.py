from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

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
    budget_module: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    _tree(
        tmp_path,
        {
            "CLAUDE.md": "abc\n@RTK.md\n",
            "RTK.md": faker.pystr(min_chars=5, max_chars=5),
            "rules/a.md": faker.pystr(min_chars=2, max_chars=2),
            "rules/lang/b.md": faker.pystr(min_chars=1, max_chars=1),
            "standards/full.md": faker.sentence(),
        },
    )

    # Act
    files = budget_module.always_loaded_files(tmp_path)

    # Assert
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
    # Arrange
    _tree(tmp_path, {"CLAUDE.md": "@missing.md\n"})

    # Act
    files = budget_module.always_loaded_files(tmp_path)

    # Assert
    assert [p.name for p in files] == ["CLAUDE.md"]


def test_passes_at_the_budget(
    budget_module: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    _tree(tmp_path, {"CLAUDE.md": faker.pystr(min_chars=10, max_chars=10)})

    # Act
    exit_code = budget_module.check(tmp_path, budget=10)

    # Assert
    assert exit_code == 0


def test_fails_over_the_budget_and_names_the_largest_file(
    budget_module: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    faker: Faker,
) -> None:
    # Arrange
    _tree(
        tmp_path,
        {
            "CLAUDE.md": faker.pystr(min_chars=5, max_chars=5),
            "rules/big.md": faker.pystr(min_chars=20, max_chars=20),
        },
    )

    # Act
    exit_code = budget_module.check(tmp_path, budget=10)

    # Assert
    assert exit_code == 1
    assert capsys.readouterr().out.splitlines()[1:4] == [
        "FAILED: 15 chars over budget. Largest files:",
        "       20  rules/big.md",
        "        5  CLAUDE.md",
    ]


def test_the_real_tree_is_within_budget(budget_module: ModuleType) -> None:
    # Arrange
    budget = budget_module.BUDGET_CHARS

    # Act
    exit_code = budget_module.check(REPO_ROOT, budget=budget)

    # Assert
    assert exit_code == 0
