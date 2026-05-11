"""Uniform audit-log facade for `~/.claude/hooks/*.py`.

Spec: `specs/2026-05-09-claude-config-state-of-art/plan.md` 1.1.8.

`audit_log.record(**fields)` accepts arbitrary keys, which lets every hook
log a slightly different shape. Aggregating across hooks then becomes a
schema-discovery problem. This facade pins a uniform field schema:

    hook_name        - hook module basename (mandatory)
    decision         - block, allow, modify, defer, ask, bypass, warn (mandatory)
    detector_tag     - per-hook detector or rule name (optional)
    reason           - short human-readable reason (optional)
    file_path        - target file path when relevant (optional)
    latency_ms       - measured latency in milliseconds (optional)
    suppressed       - True when a suppression marker silenced a finding (optional)
    defect_pattern   - matches a tag from rules/ai-guardrails.md (optional)
    confidence_score - 1-10 calibration score (optional)
    extra            - dict of fields outside the schema, kept for forward compatibility

Hooks that do not care about audit emission can ignore this module. Hooks
that adopt it gain a single, queryable schema feeding the rollup script in
`scripts/audit_summarize.py`.
"""

from __future__ import annotations

import os
import sys
from typing import Any

ALLOWED_DECISIONS: frozenset[str] = frozenset(
    {"block", "allow", "modify", "defer", "ask", "bypass", "warn", "budget_exceeded"}
)


def emit(
    event: str,
    *,
    hook_name: str,
    detector_tag: str | None = None,
    reason: str | None = None,
    file_path: str | None = None,
    latency_ms: int | None = None,
    suppressed: bool | None = None,
    defect_pattern: str | None = None,
    confidence_score: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Record a single hook decision with the uniform schema.

    `event` is the decision class. Use one of `ALLOWED_DECISIONS`. Calling
    with an unknown event still records the entry but tags it as `warn` so
    callers do not silently lose decisions during refactors.
    """
    record_fn = _resolve_record()
    if record_fn is None:
        return
    decision = event if event in ALLOWED_DECISIONS else "warn"
    payload: dict[str, Any] = {"hook": hook_name, "decision": decision}
    if event not in ALLOWED_DECISIONS:
        payload["original_decision"] = event
    if detector_tag is not None:
        payload["detector_tag"] = detector_tag
    if reason is not None:
        payload["reason"] = reason
    if file_path is not None:
        payload["file_path"] = file_path
    if latency_ms is not None:
        payload["latency_ms"] = latency_ms
    if suppressed is not None:
        payload["suppressed"] = bool(suppressed)
    if defect_pattern is not None:
        payload["defect_pattern"] = defect_pattern
    if confidence_score is not None:
        payload["confidence_score"] = max(1, min(10, int(confidence_score)))
    if extra:
        for k, v in extra.items():
            if k in payload:
                continue
            payload[k] = v
    try:
        record_fn(**payload)
    except (OSError, TypeError, ValueError):
        return


def _resolve_record():  # type: ignore[no-untyped-def]
    try:
        sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
        from audit_log import record  # type: ignore
    except ImportError:
        return None
    return record
