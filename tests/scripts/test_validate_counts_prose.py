from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-counts.py"


@pytest.fixture
def counts_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_counts", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scan(module: ModuleType, tmp_path: Path, text: str) -> list[str]:
    doc = tmp_path / "doc.md"
    doc.write_text(text)
    mismatches, _ = module.scan_file(str(doc), {"skills": 42, "hooks": 84})
    return mismatches


def test_line_leading_skills_count_mismatch_is_reported(
    counts_module: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    text = "33 skills in [`skills/`](skills/). Each is a folder.\n"

    # Act
    mismatches = scan(counts_module, tmp_path, text)

    # Assert
    assert len(mismatches) == 1
    assert "found 33, expected 42" in mismatches[0]


def test_line_leading_hooks_count_mismatch_is_reported(
    counts_module: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    text = "70 hooks in [`hooks/`](hooks/) wired through settings.\n"

    # Act
    mismatches = scan(counts_module, tmp_path, text)

    # Assert
    assert len(mismatches) == 1
    assert "found 70, expected 84" in mismatches[0]


def test_mid_sentence_hooks_in_mismatch_is_reported(
    counts_module: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    text = "The repository ships 12 hooks in the hooks directory.\n"

    # Act
    mismatches = scan(counts_module, tmp_path, text)

    # Assert
    assert len(mismatches) == 1
    assert "found 12, expected 84" in mismatches[0]


def test_line_leading_count_with_adjective_is_checked(
    counts_module: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    text = "80 runtime hooks intercept tool calls before they run.\n"

    # Act
    mismatches = scan(counts_module, tmp_path, text)

    # Assert
    assert len(mismatches) == 1
    assert "found 80, expected 84" in mismatches[0]


def test_matching_counts_report_nothing(
    counts_module: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    text = "42 skills in the folder.\n84 hooks intercept tool calls.\n"

    # Act
    mismatches = scan(counts_module, tmp_path, text)

    # Assert
    assert mismatches == []


def test_incidental_numbers_are_not_counts(
    counts_module: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    text = (
        "Choose 2 to 5 skills the resuming agent should consider.\n"
        "- The Hooks table now lists all 44 hooks, previously 30.\n"
    )

    # Act
    mismatches = scan(counts_module, tmp_path, text)

    # Assert
    assert mismatches == []


FULL_COUNTS = {
    "skills": 42,
    "hooks": 84,
    "rules": 45,
    "lang_rules": 5,
    "standards": 139,
    "agents": 18,
    "mcp_servers": 42,
}


def scan_all(module: ModuleType, tmp_path: Path, text: str) -> list[str]:
    doc = tmp_path / "doc.md"
    doc.write_text(text)
    mismatches, _ = module.scan_file(str(doc), FULL_COUNTS)
    return mismatches


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "83 standards in [`standards/`](standards/). Each entry.\n",
            "found 83, expected 139",
        ),
        (
            "44 rules in [`rules/`](rules/) plus 5 in [`rules/lang/`](rules/lang/).\n",
            "found 44, expected 45",
        ),
        (
            "45 rules in [`rules/`](rules/) plus 4 in [`rules/lang/`](rules/lang/).\n",
            "found 4, expected 5",
        ),
        (
            "Plus 6 language-specific files in [`rules/lang/`](rules/lang/).\n",
            "found 6, expected 5",
        ),
        (
            "20 specialized subagents in [`agents/`](agents/).\n",
            "found 20, expected 18",
        ),
        (
            "  agents/                20 specialized subagents\n",
            "found 20, expected 18",
        ),
        ("**17** custom agents\n", "found 17, expected 18"),
        ("36 MCP servers wired in settings.\n", "found 36, expected 42"),
        ("The 76 standards total roughly 16,000 lines.\n", "found 76, expected 139"),
        (
            "  rules/                 44 short rule cores, each linking.\n",
            "found 44, expected 45",
        ),
        (
            "    lang/                4 language-specific cores: TypeScript.\n",
            "found 4, expected 5",
        ),
        ("  skills/                40 slash-command skills\n", "found 40, expected 42"),
        ("  hooks/                 80 runtime hooks\n", "found 80, expected 84"),
    ],
)
def test_readme_count_prose_mismatch_is_reported(
    counts_module: ModuleType, tmp_path: Path, text: str, expected: str
) -> None:
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text(text)

    # Act
    mismatches, _ = counts_module.scan_file(str(doc), FULL_COUNTS)

    # Assert
    assert len(mismatches) == 1
    assert expected in mismatches[0]


def test_readme_count_prose_matching_reports_nothing(
    counts_module: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    text = (
        "139 standards in [`standards/`](standards/).\n"
        "45 rules in [`rules/`](rules/) plus 5 in [`rules/lang/`](rules/lang/).\n"
        "Plus 5 language-specific files in [`rules/lang/`](rules/lang/).\n"
        "18 specialized subagents in [`agents/`](agents/).\n"
        "42 MCP servers wired in settings.\n"
        "The 139 standards total roughly 26,000 lines.\n"
    )

    # Act
    mismatches = scan_all(counts_module, tmp_path, text)

    # Assert
    assert mismatches == []


def test_derived_counts_include_agents_and_language_rules(
    counts_module: ModuleType,
) -> None:
    # Arrange
    agents = [
        p
        for p in (REPO_ROOT / "agents").glob("*.md")
        if p.name not in {"TEMPLATE.md", "_shared-principles.md"}
    ]
    lang_rules = [
        p for p in (REPO_ROOT / "rules" / "lang").glob("*.md") if p.name != "README.md"
    ]

    # Act
    counts = counts_module.derive_counts()

    # Assert
    assert counts["agents"] == len(agents)
    assert counts["lang_rules"] == len(lang_rules)
