from __future__ import annotations

from dataclasses import dataclass

from .mutation_detectors_core import Match


@dataclass(frozen=True)
class FileScan:
    reasons: dict[str, int]
    survived: tuple[Match, ...]
    findings: tuple[str, ...]


@dataclass(frozen=True)
class ScanTotals:
    findings: tuple[str, ...]
    detector_counts: dict[str, int]
    allow_counts: dict[str, int]
    files_scanned: int
    confidence_max: int


def _merge_counts(parts: list[dict[str, int]]) -> dict[str, int]:
    keys = dict.fromkeys(key for part in parts for key in part)
    return {key: sum(part.get(key, 0) for part in parts) for key in keys}


def _confidence_of(match: Match) -> int:
    raw_confidence = str(match.metadata.get("confidence", "0"))
    return int(raw_confidence) if raw_confidence.isdigit() else 0


def aggregate_scans(scans: list[FileScan]) -> ScanTotals:
    survived = [m for scan in scans for m in scan.survived]
    detectors = [m.detector for m in survived]
    return ScanTotals(
        findings=tuple(line for scan in scans for line in scan.findings),
        detector_counts={d: detectors.count(d) for d in dict.fromkeys(detectors)},
        allow_counts=_merge_counts([scan.reasons for scan in scans]),
        files_scanned=len(scans),
        confidence_max=max([0, *(_confidence_of(m) for m in survived)]),
    )
