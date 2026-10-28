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
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-agents.py"

BODY = "\nDo not spawn subagents. Do not push.\n"
GOOD = (
    "---\nname: a\ndescription: d\nmodel: sonnet\ntools:\n  - Read\n  - Grep\n---\n"
    + BODY
)


@pytest.fixture
def agents() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_agents", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _agent(root: Path, name: str, text: str) -> Path:
    path = root / "agents" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_frontmatter_reads_scalars_and_lists(agents):
    # Arrange
    content = "---\n  - orphan\nname: a\ntools:\n  - Read\n  - Grep\nempty:\nplain words\n---\nbody\n"

    # Act
    result = agents.parse_frontmatter(content)

    # Assert
    assert result == {"name": "a", "tools": ["Read", "Grep"]}


def test_a_valid_agent_has_no_errors(agents, tmp_path):
    # Arrange
    path = _agent(tmp_path, "good.md", GOOD)

    # Act
    result = agents.validate_agent(str(path), str(tmp_path))

    # Assert
    assert result == []


def test_a_file_without_frontmatter_is_reported(agents, tmp_path):
    # Arrange
    path = _agent(tmp_path, "bare.md", "# just text\n")

    # Act
    result = agents.validate_agent(str(path), str(tmp_path))

    # Assert
    assert result == ["  agents/bare.md: missing YAML frontmatter (--- delimiters)"]


def test_field_and_body_problems_are_all_reported(agents, tmp_path):
    # Arrange
    path = _agent(
        tmp_path, "bad.md", "---\nname: b\nmodel: gpt\ntools: Read\n---\nbody\n"
    )

    # Act
    result = agents.validate_agent(str(path), str(tmp_path))

    # Assert
    assert result == [
        "  agents/bad.md: missing required field 'description'",
        "  agents/bad.md: invalid model 'gpt', must be one of: haiku, opus, sonnet",
        "  agents/bad.md: 'tools' must be a list",
        "  agents/bad.md:5: body missing 'Do not spawn subagents' constraint",
        "  agents/bad.md:5: body missing 'Do not push' prohibition "
        "(orchestrator pushes; agents must not)",
    ]


def test_an_empty_tools_list_is_reported(agents):
    # Arrange
    fields = {"name": "a", "description": "d", "model": "opus", "tools": []}

    # Act
    result = agents._field_errors("agents/x.md", fields)

    # Assert
    assert result == ["  agents/x.md: 'tools' list is empty"]


def test_main_reports_failures(agents, tmp_path, capsys):
    # Arrange
    _agent(tmp_path, "bare.md", "text\n")
    _agent(tmp_path, "TEMPLATE.md", "text\n")

    # Act
    code = agents.main(str(tmp_path))

    # Assert
    assert code == 1
    assert capsys.readouterr().out.startswith(
        "Validated 1 agent definitions\n\nFAILED: 1 error(s) found:\n"
    )


def test_main_passes_with_no_agents(agents, tmp_path, capsys):
    # Arrange
    root = tmp_path

    # Act
    code = agents.main(str(root))

    # Assert
    assert (code, capsys.readouterr().out) == (0, "No agent files found in agents/\n")


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
    assert proc.stdout.endswith("PASSED: All agent definitions valid\n")
