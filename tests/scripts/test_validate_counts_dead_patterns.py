from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-counts.py"
HOOKS_DEAD_MESSAGE = (
    "  check 'hooks count in bold' matched nothing in any scanned file. Either "
    "the prose that carried it changed shape, or the check is dead. A check that "
    "never fires reports success while verifying nothing."
)


@pytest.fixture
def counts_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_counts", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_matching_prose_records_the_label(
    counts_module: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    count = faker.pyint(min_value=1, max_value=500)
    doc = tmp_path / "doc.md"
    doc.write_text(f"**{count}** runtime hooks ship here.\n")

    # Act
    mismatches, matched = counts_module.scan_file(str(doc), {"hooks": count})

    # Assert
    assert (mismatches, matched) == ([], {"hooks count in bold"})


def test_wrong_number_is_reported_as_a_mismatch(
    counts_module: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    expected = faker.pyint(min_value=1, max_value=500)
    found = expected + faker.pyint(min_value=1, max_value=500)
    doc = tmp_path / "doc.md"
    doc.write_text(f"**{found}** runtime hooks ship here.\n")
    rel_path = os.path.relpath(doc, counts_module.CLAUDE_DIR)

    # Act
    mismatches, _ = counts_module.scan_file(str(doc), {"hooks": expected})

    # Assert
    assert mismatches == [
        f"  {rel_path}:1: hooks count in bold: found {found}, expected {expected}"
    ]


def test_an_adjective_between_number_and_noun_still_matches(
    counts_module: ModuleType, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    rules = faker.pyint(min_value=1, max_value=500)
    skills = faker.pyint(min_value=1, max_value=500)
    doc = tmp_path / "doc.md"
    doc.write_text(
        f"**{rules}** always-on rules and **{skills}** slash-command skills.\n"
    )

    # Act
    _, matched = counts_module.scan_file(
        str(doc), {"always_on_rules": rules, "skills": skills}
    )

    # Assert
    assert matched == {"always-on rules count in bold", "skills count in bold"}


def test_required_label_that_never_matched_is_reported(
    counts_module: ModuleType,
) -> None:
    # Arrange
    matched_labels: set[str] = set()

    # Act
    dead = counts_module.dead_patterns(matched_labels=matched_labels)

    # Assert
    assert len(dead) == 4
    assert dead[3] == HOOKS_DEAD_MESSAGE


def test_only_the_unmatched_label_is_reported(counts_module: ModuleType) -> None:
    # Arrange
    matched_labels = {
        "always-on rules count in bold",
        "standards count in bold",
        "skills count in bold",
    }

    # Act
    dead = counts_module.dead_patterns(matched_labels=matched_labels)

    # Assert
    assert dead == [HOOKS_DEAD_MESSAGE]


def test_no_dead_patterns_when_every_required_label_matched(
    counts_module: ModuleType,
) -> None:
    # Arrange
    matched_labels = set(counts_module.REQUIRED_LABELS)

    # Act
    dead = counts_module.dead_patterns(matched_labels=matched_labels)

    # Assert
    assert dead == []


def _labels_matched_in_repository(counts_module: ModuleType) -> set[str]:
    counts = counts_module.derive_counts()
    matched: set[str] = set()
    for filepath in counts_module.files_to_scan():
        _, labels = counts_module.scan_file(filepath, counts)
        matched |= labels
    return matched


def test_the_real_repository_exercises_every_required_label(
    counts_module: ModuleType,
) -> None:
    # Arrange
    matched = _labels_matched_in_repository(counts_module)

    # Act
    dead = counts_module.dead_patterns(matched)

    # Assert
    assert dead == []
