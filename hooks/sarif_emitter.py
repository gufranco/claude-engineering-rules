#!/usr/bin/env python3
"""SARIF 2.1.0 emitter for mutation-method-blocker.

Emits findings in the OASIS SARIF 2.1.0 format so CI systems
(GitHub code scanning, GitLab SAST, SonarQube, Codacy) can ingest
mutation-method-blocker output directly.

Schema: https://docs.oasis-open.org/sarif/sarif/v2.1.0/cos02/schemas/sarif-schema-2.1.0.json

Tool driver:
  - name:    mutation-method-blocker
  - version: 2.3.0
  - infoUri: https://github.com/onyxodds/dot-claude (placeholder)

Plan items 219, 224, 225 (D25):

  - Stable `partialFingerprints.primaryLocationLineHash` for cross-run dedup.
  - `helpUri` linking to rule docs per detector code.
  - `defaultConfiguration.level` mapped from confidence (5 -> error,
    3-4 -> warning, <=2 -> note).
  - `properties.tags` listing the relevant categories.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sys
from typing import Any

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
    ),
)

from mutation_detectors_core import Match  # noqa: E402
from mutation_fix_lookup import detector_code_to_mmb  # noqa: E402

SARIF_SCHEMA_URI = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/cos02/schemas/sarif-schema-2.1.0.json"
SARIF_VERSION = "2.1.0"
TOOL_NAME = "mutation-method-blocker"
TOOL_VERSION = "2.3.0"
TOOL_INFO_URI = "https://github.com/onyxodds/dot-claude"
RULE_DOC_BASE_URI = (
    "https://github.com/onyxodds/dot-claude/blob/main/rules/code-style.md#immutability"
)

LEVEL_ERROR = "error"
LEVEL_WARNING = "warning"
LEVEL_NOTE = "note"


@dataclasses.dataclass(frozen=True)
class Finding:
    """SARIF input record."""

    file_path: str
    match: Match


def _confidence_level(match: Match) -> str:
    """Map detector confidence metadata to a SARIF severity level."""
    confidence_str = match.metadata.get("confidence", "5")
    try:
        confidence = int(confidence_str)
    except (TypeError, ValueError):
        confidence = 5
    if confidence >= 5:
        return LEVEL_ERROR
    if confidence >= 3:
        return LEVEL_WARNING
    return LEVEL_NOTE


def _detector_category(detector: str) -> str:
    """Return the category prefix of a detector tag (e.g., array.push -> array)."""
    if not detector:
        return "unknown"
    return detector.split(".", 1)[0]


def _line_hash(file_path: str, match: Match) -> str:
    """SHA-256 of `file:line:detector:line_text` for stable dedup across runs.

    Per plan item 224, this `partialFingerprints.primaryLocationLineHash`
    lets SARIF consumers (GitHub code scanning, etc.) deduplicate the
    same finding across CI runs even when surrounding lines change.
    """
    payload = f"{file_path}:{match.line}:{match.detector}:{match.text.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _rule_id(match: Match) -> str:
    """Stable rule ID from match metadata or detector category.

    Resolution order:
      1. `mmb_code` set explicitly in match metadata.
      2. `detector_code_to_mmb` lookup against the fix-suggestions table.
      3. Uppercased category prefix as a last-resort fallback.
    """
    code = match.metadata.get("mmb_code")
    if code:
        return code
    resolved = detector_code_to_mmb(match.detector)
    if resolved:
        return resolved
    return _detector_category(match.detector).upper()


def _build_rules(matches: list[Match]) -> list[dict[str, Any]]:
    """Emit one rule entry per unique detector code present in matches."""
    seen: dict[str, dict[str, Any]] = {}
    for match in matches:
        rule_id = _rule_id(match)
        if rule_id in seen:
            continue
        category = _detector_category(match.detector)
        seen[rule_id] = {
            "id": rule_id,
            "name": match.detector,
            "shortDescription": {
                "text": f"In-place mutation: {match.detector}",
            },
            "fullDescription": {
                "text": (
                    "Receiver-typed in-place mutation flagged by "
                    "mutation-method-blocker. Replace with a non-mutating "
                    "ES2023+ alternative."
                ),
            },
            "helpUri": RULE_DOC_BASE_URI,
            "defaultConfiguration": {
                "level": _confidence_level(match),
            },
            "properties": {
                "tags": [category, "mutation", "immutability"],
                "category": category,
            },
        }
    return list(seen.values())


def _build_result(file_path: str, match: Match) -> dict[str, Any]:
    """Construct a single SARIF result entry for a match."""
    return {
        "ruleId": _rule_id(match),
        "level": _confidence_level(match),
        "message": {
            "text": match.fix_hint or f"In-place mutation: {match.detector}",
        },
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": file_path,
                    },
                    "region": {
                        "startLine": match.line,
                        "startColumn": max(match.col, 1),
                        "snippet": {
                            "text": match.text,
                        },
                    },
                },
            },
        ],
        "partialFingerprints": {
            "primaryLocationLineHash": _line_hash(file_path, match),
        },
        "properties": {
            "detector": match.detector,
            "category": _detector_category(match.detector),
        },
    }


def emit_sarif(findings: list[Finding]) -> str:
    """Serialize findings as a SARIF 2.1.0 JSON document.

    Plan item 219.
    """
    matches = [f.match for f in findings]
    rules = _build_rules(matches)
    results = [_build_result(f.file_path, f.match) for f in findings]
    document = {
        "$schema": SARIF_SCHEMA_URI,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": TOOL_NAME,
                        "version": TOOL_VERSION,
                        "informationUri": TOOL_INFO_URI,
                        "rules": rules,
                    },
                },
                "results": results,
                "columnKind": "utf16CodeUnits",
            }
        ],
    }
    return json.dumps(document, indent=2, sort_keys=True)
