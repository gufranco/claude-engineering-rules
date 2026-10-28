from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from _helpers.cov_env import apply_coverage_env

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-counts.py"

INDEX = """always_loaded:
  alpha:
    description: a
  beta:
    triggers: [x]

on_demand:
  gamma:
    path: standards/gamma.md
other:
  delta:
"""


@pytest.fixture
def counts() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_counts_tree", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


def _tree(root: Path, readme: str) -> Path:
    return _write(
        root,
        {
            "rules/index.yml": INDEX,
            "rules/a.md": "# A\n",
            "rules/lang/python.md": "# Py\n",
            "rules/lang/README.md": "# Lang\n",
            "standards/gamma.md": "# Gamma\n",
            "skills/one/SKILL.md": "# One\n",
            "hooks/a.py": "",
            "hooks/b.sh": "",
            "agents/x.md": "x\n",
            "agents/TEMPLATE.md": "t\n",
            "checklists/checklist.md": "### 1. One\n- [ ] a\n- [ ] b\n",
            "settings.json": json.dumps({"mcpServers": {"m": {}}}),
            "tests/test-hooks.sh": "run_test a\nrun_test b\n",
            "README.md": readme,
        },
    )


GOOD_README = (
    "**2** always-on rules, **1** standards, **1** skills, **2** hooks.\n"
    "It has 1 categories, 2 items.\n"
)


def test_derive_counts_reads_every_source(counts, tmp_path):
    # Arrange
    root = _tree(tmp_path, GOOD_README)

    # Act
    result = counts.derive_counts(str(root))

    # Assert
    assert result == {
        "rules": 1,
        "lang_rules": 1,
        "agents": 1,
        "always_on_rules": 2,
        "standards": 1,
        "skills": 1,
        "hooks": 2,
        "checklist_items": 2,
        "checklist_categories": 1,
        "mcp_servers": 1,
        "test_cases": 2,
        "on_demand_standards": 1,
    }


def test_derive_counts_tolerates_missing_and_broken_sources(counts, tmp_path):
    # Arrange
    root = _write(tmp_path, {"settings.json": "{broken"})

    # Act
    result = counts.derive_counts(str(root))

    # Assert
    assert (
        result["always_on_rules"],
        result["checklist_items"],
        result["mcp_servers"],
        result["test_cases"],
    ) == (0, 0, 0, 0)


def test_main_passes_a_consistent_tree(counts, tmp_path, capsys):
    # Arrange
    root = _tree(tmp_path, GOOD_README)

    # Act
    code = counts.main(str(root))

    # Assert
    assert code == 0
    assert capsys.readouterr().out.endswith(
        "PASSED: All count references match source, and every required\n"
        "check matched at least once.\n"
    )


def test_main_reports_stale_counts_and_dead_checks(counts, tmp_path, capsys):
    # Arrange
    root = _tree(tmp_path, "**9** hooks and 3 categories, 7 items.\n")

    # Act
    code = counts.main(str(root))

    # Assert
    output = capsys.readouterr().out
    assert code == 1
    assert "README.md:1: hooks count in bold: found 9, expected 2" in output
    assert "README.md:1: categories and items: found 3 categories, expected 1" in output
    assert "README.md:1: categories and items: found 7 items, expected 2" in output
    assert "FAILED: 3 check(s) matched nothing:" in output


def test_an_unreadable_file_is_reported(counts, tmp_path):
    # Arrange
    path = tmp_path / "bad.md"
    path.write_bytes(b"\xff\xfe")

    # Act
    mismatches, labels = counts.scan_file(str(path), {}, str(tmp_path))

    # Assert
    assert (len(mismatches), labels) == (1, set())
    assert mismatches[0].startswith(f"  {path}: unreadable: ")


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
    assert proc.returncode == 0


def test_main_reports_only_stale_counts_when_every_check_fires(
    counts, tmp_path, capsys
):
    # Arrange
    root = _tree(tmp_path, GOOD_README.replace("**2** hooks", "**5** hooks"))

    # Act
    code = counts.main(str(root))

    # Assert
    output = capsys.readouterr().out
    assert code == 1
    assert "FAILED: 1 stale reference(s) found:" in output
    assert "matched nothing" not in output


def test_main_reports_only_dead_checks_when_counts_agree(counts, tmp_path, capsys):
    # Arrange
    root = _tree(tmp_path, "It has 1 categories, 2 items.\n")

    # Act
    code = counts.main(str(root))

    # Assert
    output = capsys.readouterr().out
    assert code == 1
    assert "stale reference" not in output
    assert "FAILED: 4 check(s) matched nothing:" in output
