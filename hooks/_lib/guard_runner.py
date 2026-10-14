from __future__ import annotations

import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .audit_log import record as audit
from .bypass import is_bypassed
from .hook_input import read_hook_payload, tool_input_of
from .hook_profile import should_run
from .hook_warning import emit_warning
from .output import block, warn

MAX_FINDINGS_PER_FILE = 8
EXCERPT_LIMIT = 240
BLOCK_EXIT = 2


@dataclass(frozen=True, slots=True)
class Finding:
    line: int
    message: str
    blocking: bool = True


@dataclass(frozen=True, slots=True)
class Edit:
    path: str
    text: str
    full_file: bool


@dataclass(frozen=True, slots=True)
class GuardSpec:
    hook_id: str
    env_disable: str
    rule_anchor: str
    intro: str
    why: str
    fix: str
    bypass_when: str
    safety: str
    reason: str
    applies_to: Callable[[str], bool]
    find: Callable[[Edit], Sequence[Finding]]


FileFindings = tuple[str, tuple[Finding, ...]]


def collect_edits(tool: str, tool_input: dict[str, object]) -> list[Edit]:
    path = str(tool_input.get("file_path") or "")
    if tool == "Write":
        return [Edit(path, str(tool_input.get("content") or ""), True)]
    if tool == "Edit":
        return [Edit(path, str(tool_input.get("new_string") or ""), False)]
    if tool != "MultiEdit":
        return []
    edits = tool_input.get("edits") or []
    return [
        Edit(path, str(edit.get("new_string") or ""), False)
        for edit in (edits if isinstance(edits, list) else [])
        if isinstance(edit, dict)
    ]


def _render_hit(finding: Finding) -> str:
    suffix = "" if finding.blocking else " (advisory)"
    return f"  L{finding.line}: {finding.message}{suffix}"


def render_findings(intro: str, findings: Sequence[FileFindings]) -> str:
    lines = [intro]
    for path, hits in findings:
        lines.append(f"{path}:")
        lines.extend(_render_hit(hit) for hit in hits[:MAX_FINDINGS_PER_FILE])
    return "\n".join(lines)


def has_blocking(findings: Sequence[FileFindings]) -> bool:
    return any(hit.blocking for _path, hits in findings for hit in hits)


def scan(
    spec: GuardSpec, tool: str, tool_input: dict[str, object]
) -> list[FileFindings]:
    scanned = [
        (edit.path, tuple(spec.find(edit)))
        for edit in collect_edits(tool, tool_input)
        if edit.path and spec.applies_to(edit.path)
    ]
    return [(path, hits) for path, hits in scanned if hits]


def _skipped(spec: GuardSpec) -> bool:
    if not should_run(spec.hook_id):
        return True
    if os.environ.get(spec.env_disable) == "1":
        audit(hook=spec.hook_id, decision="bypass", bypass_env=spec.env_disable)
        return True
    return is_bypassed(spec.hook_id)


def _advise(spec: GuardSpec, tool: str, detected: str) -> int:
    emit_warning(
        warn(
            hook=spec.hook_id,
            purpose=f"{detected}\n\n{spec.why}\n\n{spec.fix}",
            next_action="Apply the fix, or add a suppression comment naming why the mutation is the contract.",
        )
    )
    audit(
        hook=spec.hook_id,
        decision="warn",
        tool=tool,
        reason=spec.reason,
        command_excerpt=detected[:EXCERPT_LIMIT],
    )
    return 0


def _refuse(spec: GuardSpec, tool: str, detected: str) -> int:
    print(
        block(
            hook=spec.hook_id,
            rule_anchor=spec.rule_anchor,
            detected=detected,
            why=spec.why,
            fix=spec.fix,
            bypass_when=spec.bypass_when,
            decision="FIX-AND-RETRY",
            env_var=spec.env_disable,
            safety=spec.safety,
        ),
        file=sys.stderr,
    )
    audit(
        hook=spec.hook_id,
        decision="block",
        tool=tool,
        reason=spec.reason,
        command_excerpt=detected[:EXCERPT_LIMIT],
    )
    return BLOCK_EXIT


def run_guard(spec: GuardSpec) -> int:
    if _skipped(spec):
        return 0
    payload = read_hook_payload(spec.hook_id)
    tool = str(payload.get("tool_name") or "")
    findings = scan(spec, tool, tool_input_of(payload))
    if not findings:
        return 0
    detected = render_findings(spec.intro, findings)
    if has_blocking(findings):
        return _refuse(spec, tool, detected)
    return _advise(spec, tool, detected)
