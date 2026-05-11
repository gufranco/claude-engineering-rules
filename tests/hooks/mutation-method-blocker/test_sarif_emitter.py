"""SARIF 2.1.0 emitter tests.

Items 219, 220, 224, 225 of the plan. Verifies:

  * Schema URI and version pinning per D25.
  * Tool driver identity (`mutation-method-blocker`, `2.3.0`).
  * Per-rule metadata: `helpUri`, `defaultConfiguration.level`,
    `properties.tags` listing the category (item 225).
  * Per-result `partialFingerprints.primaryLocationLineHash` for cross-run
    dedup (item 224).
  * Confidence level mapping: confidence >= 5 -> error, 3-4 -> warning,
    <= 2 -> note.
  * Stable ordering and deduplication of rule entries.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "scripts"))

from mutation_detectors_core import Match  # noqa: E402
from sarif_emitter import (  # noqa: E402
    SARIF_SCHEMA_URI,
    SARIF_VERSION,
    TOOL_NAME,
    TOOL_VERSION,
    Finding,
    emit_sarif,
)


def _match(
    detector: str,
    line: int = 10,
    col: int = 4,
    text: str = "  arr.push(item)",
    confidence: str = "5",
    mmb_code: str | None = None,
) -> Match:
    metadata: dict[str, str] = {"confidence": confidence}
    if mmb_code is not None:
        metadata["mmb_code"] = mmb_code
    return Match(
        line=line,
        col=col,
        text=text,
        detector=detector,
        fix_hint=f"Replace mutation in {detector}",
        metadata=metadata,
    )


def test_emit_sarif_returns_valid_json():
    # Arrange
    findings = [Finding("/repo/src/a.ts", _match("array.push", mmb_code="MMB001"))]

    # Act
    payload = emit_sarif(findings)

    # Assert
    parsed = json.loads(payload)
    assert parsed["$schema"] == SARIF_SCHEMA_URI
    assert parsed["version"] == SARIF_VERSION


def test_emit_sarif_pins_tool_identity():
    # Arrange
    findings = [Finding("/repo/src/a.ts", _match("array.push", mmb_code="MMB001"))]

    # Act
    parsed = json.loads(emit_sarif(findings))

    # Assert
    driver = parsed["runs"][0]["tool"]["driver"]
    assert driver["name"] == TOOL_NAME
    assert driver["version"] == TOOL_VERSION
    assert driver["informationUri"].startswith("https://")


def test_emit_sarif_emits_rule_per_unique_detector_code():
    # Arrange
    findings = [
        Finding("/repo/src/a.ts", _match("array.push", line=1, mmb_code="MMB001")),
        Finding("/repo/src/a.ts", _match("array.push", line=2, mmb_code="MMB001")),
        Finding("/repo/src/b.ts", _match("array.sort", line=5, mmb_code="MMB006")),
    ]

    # Act
    parsed = json.loads(emit_sarif(findings))

    # Assert
    rules = parsed["runs"][0]["tool"]["driver"]["rules"]
    rule_ids = [r["id"] for r in rules]
    assert sorted(rule_ids) == ["MMB001", "MMB006"]


def test_emit_sarif_rule_metadata_includes_help_and_tags():
    # Arrange
    findings = [
        Finding("/repo/src/a.ts", _match("array.push", mmb_code="MMB001")),
    ]

    # Act
    parsed = json.loads(emit_sarif(findings))
    rule = parsed["runs"][0]["tool"]["driver"]["rules"][0]

    # Assert
    assert rule["helpUri"].startswith("https://")
    assert "mutation" in rule["properties"]["tags"]
    assert "immutability" in rule["properties"]["tags"]
    assert rule["properties"]["category"] == "array"


def test_emit_sarif_confidence_high_maps_to_error():
    # Arrange
    findings = [
        Finding(
            "/repo/src/a.ts", _match("array.push", confidence="5", mmb_code="MMB001")
        ),
    ]

    # Act
    parsed = json.loads(emit_sarif(findings))

    # Assert
    rule = parsed["runs"][0]["tool"]["driver"]["rules"][0]
    assert rule["defaultConfiguration"]["level"] == "error"
    assert parsed["runs"][0]["results"][0]["level"] == "error"


def test_emit_sarif_confidence_medium_maps_to_warning():
    # Arrange
    findings = [
        Finding(
            "/repo/src/a.ts",
            _match("web-api.form-data.append", confidence="3", mmb_code="MMB046"),
        ),
    ]

    # Act
    parsed = json.loads(emit_sarif(findings))

    # Assert
    assert parsed["runs"][0]["results"][0]["level"] == "warning"


def test_emit_sarif_confidence_low_maps_to_note():
    # Arrange
    findings = [
        Finding(
            "/repo/src/a.ts", _match("array.push", confidence="1", mmb_code="MMB001")
        ),
    ]

    # Act
    parsed = json.loads(emit_sarif(findings))

    # Assert
    assert parsed["runs"][0]["results"][0]["level"] == "note"


def test_emit_sarif_partial_fingerprints_present():
    # Arrange
    findings = [
        Finding(
            "/repo/src/a.ts",
            _match("array.push", line=42, text="arr.push(item)", mmb_code="MMB001"),
        ),
    ]

    # Act
    parsed = json.loads(emit_sarif(findings))
    result = parsed["runs"][0]["results"][0]

    # Assert
    fp = result["partialFingerprints"]["primaryLocationLineHash"]
    expected = hashlib.sha256(
        b"/repo/src/a.ts:42:array.push:arr.push(item)"
    ).hexdigest()
    assert fp == expected


def test_emit_sarif_partial_fingerprints_stable_across_calls():
    # Arrange
    findings = [
        Finding("/repo/src/a.ts", _match("array.push", line=42, mmb_code="MMB001")),
    ]

    # Act
    fp1 = json.loads(emit_sarif(findings))["runs"][0]["results"][0][
        "partialFingerprints"
    ]["primaryLocationLineHash"]
    fp2 = json.loads(emit_sarif(findings))["runs"][0]["results"][0][
        "partialFingerprints"
    ]["primaryLocationLineHash"]

    # Assert
    assert fp1 == fp2


def test_emit_sarif_result_location_round_trip():
    # Arrange
    findings = [
        Finding(
            "/repo/src/feature.ts",
            _match(
                "collection.map.set",
                line=15,
                col=8,
                text="  map.set('k', 'v')",
                mmb_code="MMB011",
            ),
        )
    ]

    # Act
    parsed = json.loads(emit_sarif(findings))
    result = parsed["runs"][0]["results"][0]
    loc = result["locations"][0]["physicalLocation"]

    # Assert
    assert loc["artifactLocation"]["uri"] == "/repo/src/feature.ts"
    assert loc["region"]["startLine"] == 15
    assert loc["region"]["startColumn"] == 8
    assert loc["region"]["snippet"]["text"] == "  map.set('k', 'v')"


def test_emit_sarif_empty_findings_emits_valid_envelope():
    # Arrange
    findings: list[Finding] = []

    # Act
    parsed = json.loads(emit_sarif(findings))

    # Assert
    assert parsed["runs"][0]["results"] == []
    assert parsed["runs"][0]["tool"]["driver"]["rules"] == []


def test_emit_sarif_column_kind_utf16():
    """SARIF requires columnKind for editors to interpret startColumn."""
    # Arrange
    findings = [Finding("/repo/src/a.ts", _match("array.push", mmb_code="MMB001"))]

    # Act
    parsed = json.loads(emit_sarif(findings))

    # Assert
    assert parsed["runs"][0]["columnKind"] == "utf16CodeUnits"


def test_emit_sarif_resolves_mmb_code_via_lookup_table():
    """When mmb_code metadata is missing, the resolver looks up the
    detector tag in the fix-suggestions table and returns the stable
    MMB code (e.g., array.push -> MMB001).
    """
    # Arrange
    findings = [Finding("/repo/src/a.ts", _match("array.push"))]

    # Act
    parsed = json.loads(emit_sarif(findings))
    rule = parsed["runs"][0]["tool"]["driver"]["rules"][0]

    # Assert
    assert rule["id"] == "MMB001"


def test_emit_sarif_falls_back_to_category_for_unknown_detector():
    """An unknown detector tag falls back to the uppercased category."""
    # Arrange
    findings = [Finding("/repo/src/a.ts", _match("custom.unknown.detector"))]

    # Act
    parsed = json.loads(emit_sarif(findings))
    rule = parsed["runs"][0]["tool"]["driver"]["rules"][0]

    # Assert
    assert rule["id"] == "CUSTOM"
