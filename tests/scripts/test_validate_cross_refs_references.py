from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-cross-refs.py"


@pytest.fixture
def cross_refs() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_cross_refs", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(root: Path, relative: str, text: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def test_reports_a_hook_citing_a_rule_file_that_does_not_exist(
    cross_refs: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    write(
        tmp_path,
        "hooks/orm-guard.py",
        'MESSAGE = "Rule: ~/.claude/rules/lang/gone.md."\n',
    )

    # Act
    errors = cross_refs.find_missing_hook_citations(str(tmp_path))

    # Assert
    assert errors == [
        "hooks/orm-guard.py cites ~/.claude/rules/lang/gone.md, which does not exist"
    ]


def test_accepts_a_hook_citing_an_existing_rule_file(
    cross_refs: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    write(tmp_path, "rules/lang/orm-migrations.md", "# ORM\n")
    write(
        tmp_path,
        "hooks/orm-guard.py",
        'MESSAGE = "Rule: ~/.claude/rules/lang/orm-migrations.md."\n',
    )

    # Act
    errors = cross_refs.find_missing_hook_citations(str(tmp_path))

    # Assert
    assert errors == []


def test_reports_a_slash_reference_to_a_skill_that_does_not_exist(
    cross_refs: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    write(tmp_path, "skills/plan/SKILL.md", "# Plan\n")
    write(
        tmp_path,
        "skills/review/SKILL.md",
        "- `/office-hours` - Brainstorming.\n- `/plan adr new x`\n",
    )

    # Act
    errors = cross_refs.find_unknown_skill_references(
        str(tmp_path), frozenset({"loop"})
    )

    # Assert
    assert errors == [
        "skills/review/SKILL.md:1 references /office-hours, which is neither a skill nor a built-in command"
    ]


def test_accepts_skills_built_ins_and_paths_that_only_look_like_commands(
    cross_refs: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    write(tmp_path, "skills/plan/SKILL.md", "# Plan\n")
    write(
        tmp_path,
        "CLAUDE.md",
        "Run `/plan` and `/plan adr`, then `/loop 5m /plan`, in `/tmp/work`, never `/opt/x`.\n",
    )

    # Act
    errors = cross_refs.find_unknown_skill_references(
        str(tmp_path), frozenset({"loop"})
    )

    # Assert
    assert errors == []


def test_skill_reference_scope_skips_standards_where_slashes_are_url_paths(
    cross_refs: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    write(
        tmp_path,
        "standards/api-design.md",
        "Resources are nouns: `/users`, `/orders`.\n",
    )

    # Act
    errors = cross_refs.find_unknown_skill_references(str(tmp_path), frozenset())

    # Assert
    assert errors == []
