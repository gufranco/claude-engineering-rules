#!/usr/bin/env python3
"""LSP 3.17 Diagnostic emitter for mutation-method-blocker.

Emits findings in the Language Server Protocol 3.17 Diagnostic format so
editor extensions (VS Code, Neovim, JetBrains, Sublime LSP) can consume
mutation-method-blocker output through standard tooling.

Spec: https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#diagnostic

Output shape: a JSON array of `PublishDiagnosticsParams`-like records, one
per scanned file with at least one finding. Empty arrays are emitted when
no findings are produced so downstream tooling can distinguish between
"no output" (process crashed) and "no findings" (clean scan).

Plan item 363 (Phase 37 / D37).

Key differences from SARIF:

  - LSP uses 0-based line and character offsets; the hook records 1-based
    positions, so both axes are decremented before emission.
  - LSP severity is numeric (1=Error, 2=Warning, 3=Information, 4=Hint)
    rather than the SARIF string enum.
  - The `uri` field is a `file://` URI; LSP clients reject bare paths.
  - The end position is approximated by adding the matched-text length to
    the start column, capped at the source line length. Editors render the
    underline using this range.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
from typing import Any
from urllib.parse import quote as _urlquote

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
    ),
)

from mutation_detectors_core import Match  # noqa: E402
from mutation_fix_lookup import detector_code_to_mmb  # noqa: E402

LSP_VERSION = "3.17"
TOOL_SOURCE = "mutation-method-blocker"
TOOL_VERSION = "3.0.0"
RULE_DOC_BASE_URI = "https://github.com/onyxodds/dot-claude/blob/main/rules/lang/typescript-immutability.md"

LSP_SEVERITY_ERROR = 1
LSP_SEVERITY_WARNING = 2
LSP_SEVERITY_INFORMATION = 3
LSP_SEVERITY_HINT = 4


@dataclasses.dataclass(frozen=True)
class Finding:
    """LSP input record.

    Mirrors the SARIF `Finding` shape so the dispatch code in
    `mutation-method-blocker.py` can pass the same instances to either
    emitter without conversion.
    """

    file_path: str
    match: Match


def _confidence_severity(match: Match) -> int:
    """Map detector confidence to an LSP severity level.

    Confidence is 0-5 where 5 is a definite mutation and 0 is a
    speculative match. The mapping aligns with the SARIF emitter's
    severity bands so editor diagnostics agree with CI findings.
    """
    confidence_str = match.metadata.get("confidence", "5")
    try:
        confidence = int(confidence_str)
    except (TypeError, ValueError):
        confidence = 5
    if confidence >= 5:
        return LSP_SEVERITY_ERROR
    if confidence >= 3:
        return LSP_SEVERITY_WARNING
    if confidence >= 1:
        return LSP_SEVERITY_INFORMATION
    return LSP_SEVERITY_HINT


def _detector_category(detector: str) -> str:
    """Return the category prefix of a detector tag (e.g., array.push -> array)."""
    if not detector:
        return "unknown"
    return detector.split(".", 1)[0]


def _rule_id(match: Match) -> str:
    """Stable rule ID from match metadata or detector category.

    Resolution order matches the SARIF emitter:
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


def _path_to_uri(path: str) -> str:
    """Convert a filesystem path into an `file://` URI.

    LSP clients normalize URIs before matching them against open
    documents; emitting a bare path causes diagnostics to be silently
    dropped. The encoding mirrors Node's `url.pathToFileURL` rules: keep
    `/`, `:`, and `@` literal, percent-encode everything else.
    """
    if path.startswith("file://"):
        return path
    abspath = path if os.path.isabs(path) else os.path.abspath(path)
    encoded = _urlquote(abspath, safe="/:@")
    return f"file://{encoded}"


def _end_column(match: Match) -> int:
    """Compute the end column for the LSP range.

    The hook records the column where the mutation receiver starts; the
    LSP range needs an end column to render an underline. We pick the
    end of the matched text, clipped to a sane upper bound so an
    unusually long match (e.g., a long template literal) does not paint
    the entire screen.
    """
    text = match.text or ""
    start = max(match.col, 1) - 1
    length = len(text.rstrip("\r\n"))
    if length <= 0:
        return start + 1
    return start + min(length, 200)


def _build_diagnostic(match: Match) -> dict[str, Any]:
    """Construct a single LSP Diagnostic from a Match."""
    line_zero_based = max(match.line - 1, 0)
    col_zero_based = max(max(match.col, 1) - 1, 0)
    end_col_zero_based = max(_end_column(match), col_zero_based + 1)
    rule_id = _rule_id(match)
    return {
        "range": {
            "start": {
                "line": line_zero_based,
                "character": col_zero_based,
            },
            "end": {
                "line": line_zero_based,
                "character": end_col_zero_based,
            },
        },
        "severity": _confidence_severity(match),
        "code": rule_id,
        "codeDescription": {
            "href": f"{RULE_DOC_BASE_URI}#{rule_id.lower()}",
        },
        "source": TOOL_SOURCE,
        "message": match.fix_hint or f"In-place mutation: {match.detector}",
        "data": {
            "detector": match.detector,
            "category": _detector_category(match.detector),
            "snippet": match.text,
            "version": TOOL_VERSION,
            "lspVersion": LSP_VERSION,
        },
    }


def emit_lsp(findings: list[Finding]) -> str:
    """Serialize findings as LSP 3.17 `PublishDiagnosticsParams[]` JSON.

    The result is grouped by file URI so editor clients can iterate
    documents and assign each diagnostic to the correct open buffer in
    one pass. Files with no findings are not emitted; the consumer is
    expected to clear diagnostics for files it scanned but the hook did
    not flag.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for finding in findings:
        uri = _path_to_uri(finding.file_path)
        if uri not in grouped:
            grouped[uri] = []
            order.append(uri)
        grouped[uri].append(_build_diagnostic(finding.match))
    documents = [
        {
            "uri": uri,
            "version": None,
            "diagnostics": grouped[uri],
        }
        for uri in order
    ]
    return json.dumps(documents, indent=2, sort_keys=True)
