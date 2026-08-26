"""Tests for the dead-pattern guard in .github/scripts/validate-counts.py.

A count check that matches nothing reports success, because there is no
mismatch to report. That is how a stale number survives: the prose gains an
adjective, the pattern stops matching, and the check keeps passing while
verifying nothing. These tests pin the guard that turns a never-matching
pattern into a finding.

Source rules: rules/verification.md, rules/agent-operating-limits.md.
"""

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
    doc = tmp_path / "doc.md"
    doc.write_text("**7** runtime hooks ship here.\n")

    _, matched = counts_module.scan_file(str(doc), {"hooks": 7})

    assert "hooks count in bold" in matched


def test_wrong_number_is_reported_as_a_mismatch(counts_module, tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("**99** runtime hooks ship here.\n")

    mismatches, _ = counts_module.scan_file(str(doc), {"hooks": 7})

    assert any("hooks" in m and "99" in m for m in mismatches)


def test_an_adjective_between_number_and_noun_still_matches(
    counts_module, tmp_path: Path
) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("**5** always-on rules and **9** slash-command skills.\n")

    _, matched = counts_module.scan_file(str(doc), {"always_on_rules": 5, "skills": 9})

    assert "always-on rules count in bold" in matched
    assert "skills count in bold" in matched


def test_required_label_that_never_matched_is_reported(counts_module) -> None:
    dead = counts_module.dead_patterns(matched_labels=set())

    assert dead, "a run where nothing matched must report every required label"
    assert any("hooks" in finding for finding in dead)


def test_no_dead_patterns_when_every_required_label_matched(counts_module) -> None:
    dead = counts_module.dead_patterns(
        matched_labels=set(counts_module.REQUIRED_LABELS)
    )

    assert dead == []


def test_the_real_repository_exercises_every_required_label(counts_module) -> None:
    matched: set[str] = set()
    for filepath in counts_module.files_to_scan():
        _, labels = counts_module.scan_file(filepath, counts_module.derive_counts())
        matched |= labels

    assert counts_module.dead_patterns(matched) == []
