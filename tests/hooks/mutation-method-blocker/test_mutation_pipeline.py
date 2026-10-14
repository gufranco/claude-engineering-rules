from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.mutation_detectors_core import Match  # noqa: E402
from _lib.mutation_pipeline import (  # noqa: E402
    ScanRequest,
    detect_all,
    enrich_with_confidence,
    remap_via_source_map,
)


def _request(text: str, file_path: str, **overrides: bool) -> ScanRequest:
    return ScanRequest(
        text=text,
        lang="ts",
        file_path=file_path,
        is_full_file=overrides.get("is_full_file", True),
        optional_chain=overrides.get("optional_chain", False),
    )


def test_detect_all_keeps_the_detector_order() -> None:
    # Arrange
    request = _request("items.sort();\nitems.push(1);\n", "/repo/src/app.ts")

    # Act
    detectors = [m.detector for m in detect_all(request)]

    # Assert
    assert detectors == ["array.push", "array.sort"]


def test_detect_all_trims_typed_array_overlap_on_hot_paths() -> None:
    # Arrange
    text = "const px = new Uint8Array(4);\npx.fill(0);\n"

    # Act
    cold = [m.detector for m in detect_all(_request(text, "/repo/src/app.ts"))]
    hot = [m.detector for m in detect_all(_request(text, "/repo/src/image/px.ts"))]

    # Assert
    assert cold == ["array.fill", "typed-array.fill"]
    assert hot == []


def test_detect_all_runs_let_check_only_for_full_files() -> None:
    # Arrange
    text = "let a = 1;\n"

    # Act
    full = [m.detector for m in detect_all(_request(text, "/repo/src/a.ts"))]
    partial = [
        m.detector
        for m in detect_all(_request(text, "/repo/src/a.ts", is_full_file=False))
    ]

    # Assert
    assert full == ["let.could-be-const"]
    assert partial == []


def test_detect_all_runs_the_optional_chain_detector_when_enabled() -> None:
    # Arrange
    text = "obj?.prop = 1;\n"

    # Act
    detectors = [
        m.detector
        for m in detect_all(_request(text, "/repo/src/a.ts", optional_chain=True))
    ]

    # Assert
    assert "experimental.optional-chain-assignment" in detectors


def test_enrich_with_confidence_adds_a_digit_score() -> None:
    # Arrange
    match = Match(line=1, col=1, text="a.push(1)", detector="array.push")

    # Act
    enriched = enrich_with_confidence([match], "/repo/src/a.ts")

    # Assert
    assert enriched[0].metadata["confidence"].isdigit()


def test_remap_via_source_map_rewrites_lines_for_a_transpiled_file(
    tmp_path: Path,
) -> None:
    # Arrange
    generated = tmp_path / "dist" / "app.js"
    generated.parent.mkdir()
    generated.write_text("a.push(1);\n", encoding="utf-8")
    source_map = {"version": 3, "sources": ["src/app.ts"], "mappings": "AAEA"}
    (tmp_path / "dist" / "app.js.map").write_text(
        json.dumps(source_map), encoding="utf-8"
    )
    match = Match(line=1, col=0, text="a.push(1);", detector="array.push")

    # Act
    report_path, remapped = remap_via_source_map(str(generated), [match])

    # Assert
    assert report_path == "src/app.ts"
    assert (remapped[0].line, remapped[0].col) == (3, 0)
    assert remapped[0].metadata["generated_file"] == str(generated)
