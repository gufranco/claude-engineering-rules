from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-counts.py"


@pytest.fixture
def counts_module():
    spec = importlib.util.spec_from_file_location("validate_counts", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_matching_prose_records_the_label(counts_module, tmp_path: Path) -> None:
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text("**7** runtime hooks ship here.\n")

    # Act
    _, matched = counts_module.scan_file(str(doc), {"hooks": 7})

    # Assert
    assert "hooks count in bold" in matched


def test_wrong_number_is_reported_as_a_mismatch(counts_module, tmp_path: Path) -> None:
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text("**99** runtime hooks ship here.\n")

    # Act
    mismatches, _ = counts_module.scan_file(str(doc), {"hooks": 7})

    # Assert
    assert len(mismatches) == 1
    assert "hooks count in bold: found 99, expected 7" in mismatches[0]


def test_an_adjective_between_number_and_noun_still_matches(
    counts_module, tmp_path: Path
) -> None:
    # Arrange
    doc = tmp_path / "doc.md"
    doc.write_text("**5** always-on rules and **9** slash-command skills.\n")

    # Act
    _, matched = counts_module.scan_file(str(doc), {"always_on_rules": 5, "skills": 9})

    # Assert
    assert "always-on rules count in bold" in matched
    assert "skills count in bold" in matched


def test_required_label_that_never_matched_is_reported(counts_module) -> None:
    # Arrange
    matched_labels = set()

    # Act
    dead = counts_module.dead_patterns(matched_labels=matched_labels)

    # Assert
    assert len(dead) == len(counts_module.REQUIRED_LABELS), (
        "a run where nothing matched must report every required label"
    )
    assert any("'hooks count in bold'" in finding for finding in dead)


def test_no_dead_patterns_when_every_required_label_matched(counts_module) -> None:
    # Arrange
    matched_labels = set(counts_module.REQUIRED_LABELS)

    # Act
    dead = counts_module.dead_patterns(matched_labels=matched_labels)

    # Assert
    assert dead == []


def _labels_matched_in_repository(counts_module) -> set[str]:
    counts = counts_module.derive_counts()
    matched: set[str] = set()
    for filepath in counts_module.files_to_scan():
        _, labels = counts_module.scan_file(filepath, counts)
        matched |= labels
    return matched


def test_the_real_repository_exercises_every_required_label(counts_module) -> None:
    # Arrange
    matched = _labels_matched_in_repository(counts_module)

    # Act
    dead = counts_module.dead_patterns(matched)

    # Assert
    assert dead == []
