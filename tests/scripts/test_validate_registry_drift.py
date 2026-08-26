"""Tests for .github/scripts/validate-registry-drift.py.

The validator walks from files on disk back to the registries that are
supposed to load or document them, which is the direction the existing
one-directional validators miss. Each test builds a synthetic tree so a
finding is proven to depend on the drift and not on the real repository.

Source rules: rules/doc-truth.md, rules/testing.md.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

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

README_TEMPLATE = """\
# Config

| Skill | What |
|:--|:--|
| [`/one`](skills/one/SKILL.md) | Does one thing |

| Agent | Purpose |
|:--|:--|
| [`auditor`](agents/auditor.md) | Audits |
"""


def load_validator(root: Path):
    """Import the validator with its ROOT pointed at a synthetic tree."""
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
    """A synthetic config tree with no drift."""
    root = tmp_path / "config"
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
    findings = run(tree)

    assert findings == []


def test_unregistered_rule_is_reported(tree: Path) -> None:
    (tree / "rules" / "orphan.md").write_text("# Orphan\n")

    findings = run(tree)

    assert any("rules/orphan.md" in f for f in findings)


def test_unregistered_standard_is_reported(tree: Path) -> None:
    (tree / "standards" / "orphan.md").write_text("# Orphan\n")

    findings = run(tree)

    assert any("standards/orphan.md" in f for f in findings)


def test_undocumented_skill_is_reported(tree: Path) -> None:
    (tree / "skills" / "two").mkdir()
    (tree / "skills" / "two" / "SKILL.md").write_text("---\nname: two\n---\n")

    findings = run(tree)

    assert any("skills/two/" in f for f in findings)


def test_documented_skill_that_does_not_exist_is_reported(tree: Path) -> None:
    readme = tree / "README.md"
    readme.write_text(
        readme.read_text() + "| [`/ghost`](skills/ghost/SKILL.md) | Missing |\n"
    )

    findings = run(tree)

    assert any("ghost" in f and "does not exist" in f for f in findings)


def test_undocumented_agent_is_reported(tree: Path) -> None:
    (tree / "agents" / "reviewer.md").write_text("---\nname: reviewer\n---\n")

    findings = run(tree)

    assert any("agents/reviewer.md" in f for f in findings)


def test_agent_template_is_not_treated_as_an_agent(tree: Path) -> None:
    (tree / "agents" / "TEMPLATE.md").write_text("# Template\n")
    (tree / "agents" / "_shared-principles.md").write_text("# Shared\n")

    findings = run(tree)

    assert findings == []


@pytest.mark.parametrize(
    "name", ["test_thing.py", "thing_test.py", "thing.test.py", "conftest.py"]
)
def test_test_shaped_file_in_hooks_is_reported(tree: Path, name: str) -> None:
    (tree / "hooks" / name).write_text("import unittest\n")

    findings = run(tree)

    assert any(name in f for f in findings)


def test_index_entry_naming_a_missing_path_is_reported(tree: Path) -> None:
    (tree / "standards" / "gamma.md").unlink()

    findings = run(tree)

    assert any("standards/gamma.md" in f for f in findings)


def test_main_exits_zero_on_a_clean_tree(tree: Path, capsys) -> None:
    module = load_validator(tree)

    code = module.main()

    assert code == 0
    assert "PASSED" in capsys.readouterr().out


def test_main_exits_one_and_names_each_finding(tree: Path, capsys) -> None:
    (tree / "rules" / "orphan.md").write_text("# Orphan\n")
    module = load_validator(tree)

    code = module.main()

    out = capsys.readouterr().out
    assert code == 1
    assert "FAILED" in out
    assert "rules/orphan.md" in out
