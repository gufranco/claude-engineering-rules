from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-skills.py"


@pytest.fixture
def skills_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_skills", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_dirs(root: Path, names: tuple[str, ...]) -> None:
    for name in names:
        (root / name).mkdir(parents=True)


def test_skill_dirs_skip_dot_prefixed_and_harness_directories(
    skills_module: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    make_dirs(tmp_path, ("plan", ".trash", ".cache", "synced", "ship"))
    (tmp_path / "README.md").write_text("not a directory")

    # Act
    found = skills_module.skill_dirs(str(tmp_path))

    # Assert
    assert [Path(p).name for p in found] == ["plan", "ship"]


def test_the_real_tree_validates_every_top_level_skill(
    skills_module: ModuleType,
) -> None:
    # Arrange
    found = skills_module.skill_dirs(skills_module.SKILLS_DIR)

    # Act
    errors = [e for d in found for e in skills_module.validate_skill(d)]

    # Assert
    assert errors == []
