from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_detectors_core import Match  # noqa: E402
from _lib.mutation_scan_totals import FileScan, aggregate_scans  # noqa: E402


def _match(detector: str, confidence: str) -> Match:
    return Match(
        line=1, col=1, text="x", detector=detector, metadata={"confidence": confidence}
    )


def test_aggregate_scans_sums_counts_and_keeps_zero_reasons() -> None:
    # Arrange
    first = FileScan(
        reasons={"ts-nocheck": 0},
        survived=(_match("array.push", "7"), _match("array.sort", "x")),
        findings=("  - a.ts:", "      L1:1 [array.push] x"),
    )
    second = FileScan(
        reasons={"framework-receiver": 2},
        survived=(_match("array.push", "4"),),
        findings=("  - b.ts:",),
    )

    # Act
    totals = aggregate_scans([first, second])

    # Assert
    assert totals.files_scanned == 2
    assert totals.findings == (
        "  - a.ts:",
        "      L1:1 [array.push] x",
        "  - b.ts:",
    )
    assert totals.detector_counts == {"array.push": 2, "array.sort": 1}
    assert totals.allow_counts == {"ts-nocheck": 0, "framework-receiver": 2}
    assert totals.confidence_max == 7


def test_aggregate_scans_of_nothing_is_empty() -> None:
    # Arrange
    scans: list[FileScan] = []

    # Act
    totals = aggregate_scans(scans)

    # Assert
    assert (totals.files_scanned, totals.findings, totals.confidence_max) == (0, (), 0)
