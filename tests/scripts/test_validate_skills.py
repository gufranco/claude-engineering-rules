from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env

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
    skills_module: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    make_dirs(tmp_path, ("plan", ".trash", ".cache", "synced", "ship"))
    (tmp_path / "README.md").write_text(faker.sentence())

    # Act
    found = skills_module.skill_dirs(str(tmp_path))

    # Assert
    assert [Path(p).name for p in found] == ["plan", "ship"]


def test_the_real_tree_validates_every_top_level_skill(
    skills_module: ModuleType,
) -> None:
    # Arrange
    found = skills_module.skill_dirs(str(REPO_ROOT / "skills"))

    # Act
    errors = [e for d in found for e in skills_module.validate_skill(d)]

    # Assert
    assert errors == []


LONG = "x" * 120
RISKY_VERB = "git " + "push"


def _skill(root: Path, name: str, text: str | None) -> None:
    folder = root / "skills" / name
    folder.mkdir(parents=True)
    if text is not None:
        (folder / "SKILL.md").write_text(text, encoding="utf-8")


def test_every_skill_problem_is_reported(
    skills_module: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    _skill(tmp_path, "absent", None)
    _skill(tmp_path, "blank", "   \n")
    _skill(tmp_path, "short", "---\nname: s\n---\nbody\n")
    _skill(tmp_path, "loose", "no frontmatter " + LONG)
    _skill(
        tmp_path,
        "risky",
        f"---\nname: r\ndescription: d\n---\n{LONG}\nthen {RISKY_VERB} it\n",
    )
    _skill(
        tmp_path,
        "declared",
        f"---\nname: d\ndescription: d\nsensitive: true\n---\n{LONG}\n{RISKY_VERB}\n",
    )

    # Act
    code = skills_module.main(str(tmp_path))

    # Assert
    assert code == 1
    assert capsys.readouterr().out.splitlines()[4:] == [
        "  skills/absent: missing SKILL.md",
        "  skills/blank/SKILL.md: empty",
        "  skills/loose/SKILL.md: missing YAML frontmatter",
        f"  skills/risky/SKILL.md:6: body mentions irreversible action '{RISKY_VERB}' "
        "but frontmatter is missing 'sensitive: true'",
        "  skills/short/SKILL.md: suspiciously short (21 chars)",
        "  skills/short/SKILL.md: missing required field 'description'",
    ]


def test_main_passes_without_a_skills_directory(
    skills_module: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    root = tmp_path

    # Act
    code = skills_module.main(str(root))

    # Assert
    assert (code, capsys.readouterr().out) == (0, "No skills/ directory found\n")


def test_main_passes_valid_skills(
    skills_module: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    _skill(tmp_path, "good", f"---\nname: g\ndescription: d\n---\n{LONG}\n")

    # Act
    code = skills_module.main(str(tmp_path))

    # Assert
    assert (code, capsys.readouterr().out) == (
        0,
        "Validated 1 skills\nPASSED: all skills valid\n",
    )


def test_the_script_validates_this_repository() -> None:
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
        "PASSED: all skills valid",
    )
