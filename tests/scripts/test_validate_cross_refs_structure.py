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
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-cross-refs.py"

INDEX = """# catalog
always_loaded:
  present:
    description: x
  missing-rule:
    triggers: [a, b]
on_demand:
  custom:
    path: standards/elsewhere.md
  gone:
    path: standards/gone.md
"""


@pytest.fixture
def cross_refs() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_cross_refs_s", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(root: Path, relative: str, text: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _fixture_repo(root: Path) -> Path:
    write(root, "rules/index.yml", INDEX)
    write(root, "rules/present.md", "# Present\n")
    write(root, "standards/elsewhere.md", "# Elsewhere\n")
    write(root, "standards/plain.md", "no heading here\n")
    write(root, "agents/good.md", "---\nname: g\ndescription: d\ntools: Read\n---\n")
    write(root, "agents/partial.md", "---\nname: p\n# note\n\nbare line\n---\n")
    write(root, "agents/loose.md", "no frontmatter\n")
    write(root, "agents/cut.md", "---\nname: c\n")
    write(root, "agents/TEMPLATE.md", "anything\n")
    return root


def test_parse_index_yml_reads_sections_entries_and_lists(cross_refs, tmp_path):
    # Arrange
    path = tmp_path / "index.yml"
    path.write_text(INDEX, encoding="utf-8")

    # Act
    result = cross_refs.parse_index_yml(str(path))

    # Assert
    assert result == {
        "always_loaded": {
            "present": {"description": "x"},
            "missing-rule": {"triggers": ["a", "b"]},
        },
        "on_demand": {
            "custom": {"path": "standards/elsewhere.md"},
            "gone": {"path": "standards/gone.md"},
        },
    }


def test_collect_errors_reports_every_structural_problem(cross_refs, tmp_path):
    # Arrange
    root = _fixture_repo(tmp_path)

    # Act
    result = cross_refs.collect_errors(str(root))

    # Assert
    assert result == [
        "index.yml [always_loaded] 'missing-rule': path 'rules/missing-rule.md' does not exist",
        "index.yml [on_demand] 'gone': path 'standards/gone.md' does not exist",
        "agents/cut.md: missing or malformed frontmatter",
        "agents/loose.md: missing or malformed frontmatter",
        "agents/partial.md: missing required field 'description'",
        "agents/partial.md: missing required field 'tools'",
        "standards/plain.md: missing top-level heading",
    ]


def test_main_prints_each_error_and_fails(cross_refs, tmp_path, capsys):
    # Arrange
    root = _fixture_repo(tmp_path)

    # Act
    code = cross_refs.main(str(root))

    # Assert
    output = capsys.readouterr().out
    assert code == 1
    assert output.startswith("Cross-reference validation failed with 7 error(s):\n")


def test_main_passes_on_a_clean_tree(cross_refs, tmp_path, capsys):
    # Arrange
    write(tmp_path, "rules/index.yml", "always_loaded:\n")

    # Act
    code = cross_refs.main(str(tmp_path))

    # Assert
    assert (code, capsys.readouterr().out) == (0, "All cross-references valid\n")


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
    assert (proc.returncode, proc.stdout) == (0, "All cross-references valid\n")
