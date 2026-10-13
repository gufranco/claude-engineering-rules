from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-registry-drift.py"

INDEX_TEMPLATE = """\
always_loaded:
  alpha:
    description: An always-loaded rule.
    triggers: [alpha]

on_demand:
  beta:
    path: rules/beta.md
    description: An on-demand rule.
    triggers: [beta]
  gamma:
    path: standards/gamma.md
    description: An on-demand standard.
    triggers: [gamma]
"""

ORPHAN_RULE_FINDING = (
    "rules/orphan.md exists but has no entry in rules/index.yml. "
    "An unregistered rule never loads, so it silently does nothing."
)

README_TEMPLATE = """\
# Config

| Skill | What |
|:--|:--|
| [`/one`](skills/one/SKILL.md) | Does one thing |

| Agent | Purpose |
|:--|:--|
| [`auditor`](agents/auditor.md) | Audits |
"""


def load_validator(root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"vrd_{root.name}", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = root
    return module


def vendor_the_index_parser_the_validator_imports(root: Path) -> None:
    scripts = root / ".github" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(
        REPO_ROOT / ".github" / "scripts" / "validate-cross-refs.py",
        scripts / "validate-cross-refs.py",
    )


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    return build_tree(tmp_path / "config")


def build_tree(root: Path) -> Path:
    for sub in ("rules", "standards", "hooks", "agents", "skills"):
        (root / sub).mkdir(parents=True)

    (root / "rules" / "alpha.md").write_text("# Alpha\n")
    (root / "rules" / "beta.md").write_text("# Beta\n")
    (root / "rules" / "index.yml").write_text(INDEX_TEMPLATE)
    (root / "standards" / "gamma.md").write_text("# Gamma\n")
    (root / "agents" / "auditor.md").write_text("---\nname: auditor\n---\n")
    (root / "skills" / "one").mkdir()
    (root / "skills" / "one" / "SKILL.md").write_text("---\nname: one\n---\n")
    (root / "hooks" / "real-hook.py").write_text("#!/usr/bin/env python3\n")
    (root / "README.md").write_text(README_TEMPLATE)

    vendor_the_index_parser_the_validator_imports(root)
    return root


def run(root: Path) -> list[str]:
    module = load_validator(root)
    findings: list[str] = []
    index = module.load_index()
    readme = (root / "README.md").read_text()

    module.check_rules_registered(index, findings)
    module.check_standards_registered(index, findings)
    module.check_skills_documented(readme, findings)
    module.check_agents_documented(readme, findings)
    module.check_no_stray_hook_files(findings)
    module.check_index_rule_paths(index, findings)
    return findings


def test_clean_tree_reports_nothing(tree: Path) -> None:
    # Arrange
    tree_input = tree

    # Act
    findings = run(tree_input)

    # Assert
    assert findings == []


def test_unregistered_rule_is_reported(tree: Path, faker: Faker) -> None:
    # Arrange
    (tree / "rules" / "orphan.md").write_text(f"# {faker.word()}\n")

    # Act
    findings = run(tree)

    # Assert
    assert findings == [ORPHAN_RULE_FINDING]


def test_unregistered_standard_is_reported(tree: Path, faker: Faker) -> None:
    # Arrange
    (tree / "standards" / "orphan.md").write_text(f"# {faker.word()}\n")

    # Act
    findings = run(tree)

    # Assert
    assert findings == [
        "standards/orphan.md exists but has no on_demand entry in "
        "rules/index.yml, so no trigger can ever load it."
    ]


def test_undocumented_skill_is_reported(tree: Path) -> None:
    # Arrange
    (tree / "skills" / "two").mkdir()
    (tree / "skills" / "two" / "SKILL.md").write_text("---\nname: two\n---\n")

    # Act
    findings = run(tree)

    # Assert
    assert findings == ["skills/two/ has no row in the README skills table."]


def test_documented_skill_that_does_not_exist_is_reported(tree: Path) -> None:
    # Arrange
    readme = tree / "README.md"
    readme.write_text(
        readme.read_text() + "| [`/ghost`](skills/ghost/SKILL.md) | Missing |\n"
    )

    # Act
    findings = run(tree)

    # Assert
    assert findings == ["README lists /ghost but skills/ghost/SKILL.md does not exist."]


def test_undocumented_agent_is_reported(tree: Path) -> None:
    # Arrange
    (tree / "agents" / "reviewer.md").write_text("---\nname: reviewer\n---\n")

    # Act
    findings = run(tree)

    # Assert
    assert findings == ["agents/reviewer.md has no row in the README agents table."]


def test_agent_template_is_not_treated_as_an_agent(tree: Path, faker: Faker) -> None:
    # Arrange
    (tree / "agents" / "TEMPLATE.md").write_text(f"# {faker.word()}\n")
    (tree / "agents" / "_shared-principles.md").write_text(f"# {faker.word()}\n")

    # Act
    findings = run(tree)

    # Assert
    assert findings == []


@pytest.mark.parametrize(
    "name", ["test_thing.py", "thing_test.py", "thing.test.py", "conftest.py"]
)
def test_test_shaped_file_in_hooks_is_reported(tree: Path, name: str) -> None:
    # Arrange
    (tree / "hooks" / name).write_text("import unittest\n")

    # Act
    findings = run(tree)

    # Assert
    assert findings == [
        f"hooks/{name} is test-shaped but sits in hooks/. The file-bypass smoke "
        "test executes every hooks/*.py, so this runs a test runner as a "
        "subprocess and hangs until the harness times out. Move it under "
        "tests/hooks/."
    ]


def test_index_entry_naming_a_missing_path_is_reported(tree: Path) -> None:
    # Arrange
    (tree / "standards" / "gamma.md").unlink()

    # Act
    findings = run(tree)

    # Assert
    assert findings == [
        "rules/index.yml: on_demand 'gamma' names a missing standards/gamma.md"
    ]


def test_main_exits_zero_on_a_clean_tree(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    module = load_validator(tree)

    # Act
    code = module.main()

    # Assert
    assert code == 0
    assert capsys.readouterr().out == (
        "PASSED: no registry drift. Rules and standards are registered,\n"
        "skills and agents are documented, hooks/ holds only hooks.\n"
    )


def test_main_exits_one_and_names_each_finding(
    tree: Path, capsys: pytest.CaptureFixture[str], faker: Faker
) -> None:
    # Arrange
    (tree / "rules" / "orphan.md").write_text(f"# {faker.word()}\n")
    module = load_validator(tree)

    # Act
    code = module.main()

    # Assert
    assert code == 1
    assert capsys.readouterr().out == (
        "FAILED: 1 registry drift finding(s)\n\n"
        f"  {ORPHAN_RULE_FINDING}\n\n"
        "Every artifact on disk must be reachable from the registry\n"
        "that is supposed to load or document it.\n"
    )
