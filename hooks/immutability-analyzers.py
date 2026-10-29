#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.analyzer_batch import AnalyzerBatch, cache_dir  # noqa: E402
from _lib.analyzer_parsers import RawFinding  # noqa: E402
from _lib.analyzer_runs import Analyzer, analyzers_for, run  # noqa: E402
from _lib.audit_log import record as audit  # noqa: E402
from _lib.bypass import is_bypassed  # noqa: E402
from _lib.changed_lines import changed_lines  # noqa: E402
from _lib.hook_input import read_hook_payload, tool_input_of  # noqa: E402
from _lib.hook_warning import emit_user_notice, emit_warning  # noqa: E402
from _lib.hook_profile import should_run  # noqa: E402
from _lib.source_scope import in_scope  # noqa: E402

HOOK_ID = "immutability-analyzers"
ENV_DISABLE = "IMMUTABILITY_ANALYZERS_DISABLE"
MAX_FILES_PER_STOP = 40
HEADER = (
    "Immutability analyzers found problems in files edited this turn. Fix every "
    "blocking item, or add the tool's own suppression comment naming why. "
    "See ~/.claude/standards/immutability.md, Enforcement."
)


@dataclass(frozen=True, slots=True)
class Review:
    blocking: tuple[str, ...] = ()
    advisory: tuple[str, ...] = ()


def _skipped() -> bool:
    if not should_run(HOOK_ID):
        return True
    if os.environ.get(ENV_DISABLE) == "1":
        audit(hook=HOOK_ID, decision="bypass", bypass_env=ENV_DISABLE)
        return True
    return is_bypassed(HOOK_ID)


def _record(batch: AnalyzerBatch, payload: dict[str, object]) -> int:
    raw = str(tool_input_of(payload).get("file_path") or "")
    path = Path(raw).resolve() if raw else None
    if (
        path is not None
        and path.is_file()
        and analyzers_for(path)
        and in_scope(str(path))
    ):
        batch.record(path)
    return 0


def _same_file(raw: str, path: Path) -> bool:
    candidate = Path(raw)
    resolved = candidate if candidate.is_absolute() else path.parent / candidate
    return resolved.resolve() == path


def _classify(
    analyzer: Analyzer, finding: RawFinding, changed: frozenset[int] | None
) -> tuple[str, str]:
    label = f"{finding.path}:{finding.line} [{analyzer.name} {finding.rule}] {finding.message}"
    if finding.rule in analyzer.blocking:
        fresh = changed is None or finding.line in changed
        return ("blocking", label) if fresh else ("advisory", f"{label} (pre-existing)")
    return (
        ("advisory", label) if finding.rule in analyzer.advisory else ("ignored", label)
    )


def _review_file(path: Path) -> Review:
    changed = changed_lines(path)
    blocking: list[str] = []
    advisory: list[str] = []
    for analyzer in analyzers_for(path):
        result = run(analyzer, path)
        if result.failure:
            blocking = [*blocking, f"{path}: {result.failure}"]
        verdicts = [
            _classify(analyzer, f, changed)
            for f in result.findings
            if _same_file(f.path, path)
        ]
        blocking = [
            *blocking,
            *(label for kind, label in verdicts if kind == "blocking"),
        ]
        advisory = [
            *advisory,
            *(label for kind, label in verdicts if kind == "advisory"),
        ]
    return Review(blocking=tuple(blocking), advisory=tuple(advisory))


def _merge(reviews: list[Review]) -> Review:
    return Review(
        blocking=tuple(item for review in reviews for item in review.blocking),
        advisory=tuple(item for review in reviews for item in review.advisory),
    )


def _report(review: Review, overflow: int) -> str:
    sections: list[str] = [HEADER] if review.blocking or review.advisory else []
    if review.blocking:
        sections = [
            *sections,
            "Blocking:",
            *(f"  - {item}" for item in review.blocking),
        ]
    if review.advisory:
        sections = [
            *sections,
            "Advisory:",
            *(f"  - {item}" for item in review.advisory),
        ]
    if overflow:
        sections = [
            *sections,
            f"{overflow} more edited files were not analyzed this turn; they stay queued.",
        ]
    return "\n".join(sections)


def _emit(body: dict[str, str]) -> int:
    sys.stdout.write(json.dumps(body))
    return 0


def _settle(
    batch: AnalyzerBatch,
    review: Review,
    report: str,
    repeated: bool,
    queued: tuple[Path, ...],
) -> int:
    if not review.blocking:
        batch.replace(queued)
        if review.advisory or queued:
            emit_warning(report, event="Stop")
        return 0
    digest = hashlib.sha256(report.encode("utf-8")).hexdigest()
    if repeated and digest == batch.remembered():
        batch.replace(queued)
        audit(
            hook=HOOK_ID,
            decision="warn",
            reason="unchanged after block",
            command_excerpt=report[:240],
        )
        emit_user_notice(f"Unresolved after one block:\n{report}")
        return 0
    batch.remember(digest)
    audit(
        hook=HOOK_ID,
        decision="block",
        reason="analyzer findings",
        command_excerpt=report[:240],
    )
    return _emit({"decision": "block", "reason": report})


def _review(batch: AnalyzerBatch, payload: dict[str, object]) -> int:
    pending = batch.pending()
    if not pending:
        return 0
    queued = pending[MAX_FILES_PER_STOP:]
    review = _merge([_review_file(path) for path in pending[:MAX_FILES_PER_STOP]])
    report = _report(review, len(queued))
    return _settle(batch, review, report, bool(payload.get("stop_hook_active")), queued)


def main() -> int:
    if _skipped():
        return 0
    payload = read_hook_payload(HOOK_ID)
    batch = AnalyzerBatch(cache_dir(), str(payload.get("session_id") or "default"))
    event = str(payload.get("hook_event_name") or "")
    if event == "PostToolUse":
        return _record(batch, payload)
    if event == "Stop":
        return _review(batch, payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
