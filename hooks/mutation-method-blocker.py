#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from _lib.audit_log import record as _audit
except Exception:  # pragma: no cover

    def _audit(**_fields: Any) -> None:
        return None


from _lib.mutation_allowlists import skip_extension, skip_path
from _lib.mutation_cli import handle_cli_flags
from _lib.mutation_confidence import to_sarif_level
from _lib.mutation_detectors_core import Match, ast_grep_path, detect_lang
from _lib.mutation_match_filter import ESLINT_RULES
from _lib.mutation_match_filter import filter_matches as _filter_matches
from _lib.mutation_pipeline import ScanRequest, detect_all, enrich_with_confidence
from _lib.mutation_pipeline import remap_via_source_map as _remap_via_source_map
from _lib.mutation_scan_totals import FileScan, ScanTotals, aggregate_scans
from _lib.suppression import compute_block_state

from _lib.mutation_version import VERSION as _MUTATION_VERSION

VERSION = _MUTATION_VERSION
__version__ = _MUTATION_VERSION
PERF_BUDGET_MS = 200
HOOK_NAME = "mutation-method-blocker"
DETECTOR_SUMMARY_LIMIT = 12
COMMAND_EXCERPT_LIMIT = 240

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload, tool_input_of  # noqa: E402


def _concise_mode() -> bool:
    return (os.environ.get("MUTATION_METHOD_CONCISE") or "").strip() == "1"


def _profile_mode() -> bool:
    return (os.environ.get("MUTATION_METHOD_PROFILE") or "").strip() == "1"


def _experimental_enabled(name: str) -> bool:
    var = f"MUTATION_METHOD_EXPERIMENTAL_{name}"
    return (os.environ.get(var) or "").strip() == "1"


def _batch_mode_enabled() -> bool:
    if sys.argv[1:2] == [BATCH_FLAG]:
        return True
    return (os.environ.get("MUTATION_METHOD_BATCH_MODE") or "").strip() == "1"


BATCH_FLAG = "--batch"

SAMPLE_LINE_CAP = 100
MAX_HITS_PER_FILE = 8


def _normalize_payload(
    tool: str, tool_input: dict[str, Any]
) -> list[tuple[str, str, str, bool]]:
    out: list[tuple[str, str, str, bool]] = []
    fp = tool_input.get("file_path", "") or ""
    if tool == "Write":
        c = tool_input.get("content", "")
        if isinstance(c, str):
            out.append((fp, "content", c, True))
    elif tool == "Edit":
        c = tool_input.get("new_string", "")
        if isinstance(c, str):
            out.append((fp, "new_string", c, False))
    elif tool == "MultiEdit":
        edits = tool_input.get("edits", []) or []
        for i, edit in enumerate(edits):
            if isinstance(edit, dict):
                c = edit.get("new_string", "")
                if isinstance(c, str):
                    out.append((fp, f"edits[{i}].new_string", c, False))
    return out


def _format_findings(file_path: str, matches: list[Match]) -> list[str]:
    out: list[str] = [f"  - {file_path}:"]
    for m in matches[:MAX_HITS_PER_FILE]:
        excerpt = m.text[:SAMPLE_LINE_CAP]
        out.append(f"      L{m.line}:{m.col} [{m.detector}] {excerpt}")
        if m.fix_hint:
            out.append(f"        fix: {m.fix_hint[:200]}")
    if len(matches) > MAX_HITS_PER_FILE:
        out.append(f"      ... and {len(matches) - MAX_HITS_PER_FILE} more")
    return out


_I18N_CACHE: dict[str, dict[str, Any]] = {}


def _load_i18n(locale: str) -> dict[str, Any]:
    if locale in _I18N_CACHE:
        return _I18N_CACHE[locale]
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [locale]
    if "-" in locale:
        candidates.append(locale.split("-", 1)[0])
    candidates.append("en")
    for cand in candidates:
        path = os.path.join(here, "i18n", f"{cand}.json")
        try:
            with open(path, encoding="utf-8") as fh:
                bundle: dict[str, Any] = json.load(fh)
                _I18N_CACHE[locale] = bundle
                return bundle
        except (OSError, ValueError):
            continue
    _I18N_CACHE[locale] = {}
    return {}


def _build_message(findings: list[str]) -> str:
    locale = os.environ.get("MUTATION_METHOD_LOCALE", "en") or "en"
    bundle = _load_i18n(locale)
    header: str = bundle.get(
        "blocked_header",
        'Blocked: in-place mutation detected. Rule: ~/.claude/rules/code-style.md "Immutability".',
    )
    title = header + "\n" + "\n".join(findings)
    if _concise_mode():
        return title
    fix_header: str = bundle.get("fix_references_header", "Fix references:")
    fix_lines: list[str] = bundle.get("fix_references") or []
    supp_header: str = bundle.get("suppression_header", "Suppression:")
    supp_lines: list[str] = bundle.get("suppression_lines") or []
    byp_header: str = bundle.get("bypass_header", "Bypass envs:")
    byp_lines: list[str] = bundle.get("bypass_lines") or []

    def _format_block(label: str, lines: list[str]) -> str:
        if not lines:
            return ""
        body = "\n".join(f"  - {line}" for line in lines)
        return f"{label}\n{body}"

    sections = [
        _format_block(fix_header, fix_lines),
        _format_block(supp_header, supp_lines),
        _format_block(byp_header, byp_lines),
    ]
    rendered = "\n".join(s for s in sections if s)
    return title + "\n\n" + rendered


def _deny(reason: str) -> int:
    print(reason, file=sys.stderr)
    body = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    try:
        sys.stdout.write(json.dumps(body, ensure_ascii=False))
        sys.stdout.flush()
    except (OSError, TypeError, ValueError) as error:
        sys.stderr.write(f"mutation-method-blocker: decision write failed: {error}\n")
    return 2


def _read_batch_items() -> list[tuple[str, str, str, bool]]:
    items: list[tuple[str, str, str, bool]] = []
    paths: list[str] = []
    if len(sys.argv) > 1:
        paths.extend(arg for arg in sys.argv[1:] if arg and arg != BATCH_FLAG)
    if not paths:
        try:
            raw = sys.stdin.read()
        except Exception:
            raw = ""
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            paths.append(stripped)
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        items.append((path, "content", text, True))
    return items


def _handle_cli_flags() -> int | None:
    return handle_cli_flags(sys.argv[1:], VERSION, os.path.dirname(__file__))


from _lib.hook_profile import should_run  # noqa: E402


def _scan_item(path: str, text: str, is_full_file: bool) -> FileScan | None:
    if skip_extension(path) or skip_path(path):
        return None
    request = ScanRequest(
        text=text,
        lang=detect_lang(path),
        file_path=path,
        is_full_file=is_full_file,
        optional_chain=_experimental_enabled("OPTIONAL_CHAIN_ASSIGN"),
    )
    block_state = compute_block_state(text.splitlines(), rules=ESLINT_RULES)
    survived, reasons = _filter_matches(detect_all(request), text, path, block_state)
    if not survived:
        return FileScan(reasons=reasons, survived=(), findings=())
    enriched = enrich_with_confidence(survived, path)
    report_path, remapped = _remap_via_source_map(path, enriched)
    findings = tuple(_format_findings(report_path, remapped))
    return FileScan(reasons=reasons, survived=tuple(enriched), findings=findings)


def _bypass_requested() -> bool:
    if os.environ.get("MUTATION_METHOD_DISABLE") == "1":
        _audit(
            hook=HOOK_NAME,
            decision="bypass",
            bypass_env="MUTATION_METHOD_DISABLE",
            version=VERSION,
        )
        return True
    return is_bypassed(HOOK_NAME)


def _collect_items() -> tuple[str, list[tuple[str, str, str, bool]]]:
    if _batch_mode_enabled():
        return "Batch", _read_batch_items()
    payload = read_hook_payload(HOOK_NAME)
    tool = str(payload.get("tool_name") or "")
    return tool, _normalize_payload(tool, tool_input_of(payload))


def _audit_perf(duration_ms: float, files_scanned: int) -> None:
    if duration_ms <= PERF_BUDGET_MS:
        return
    _audit(
        hook=HOOK_NAME,
        decision="warn",
        reason="perf-budget-exceeded",
        duration_ms=duration_ms,
        version=VERSION,
        files_scanned=files_scanned,
    )


def _audit_allow(
    tool: str, totals: ScanTotals, duration_ms: float, ast_used: bool
) -> None:
    if totals.files_scanned <= 0:
        return
    _audit(
        hook=HOOK_NAME,
        decision="allow",
        tool=tool,
        version=VERSION,
        duration_ms=duration_ms,
        ast_used=ast_used,
        files_scanned=totals.files_scanned,
        allow_reasons=",".join(
            f"{k}:{v}" for k, v in sorted(totals.allow_counts.items())
        )
        or None,
    )


def _audit_block(
    tool: str, totals: ScanTotals, duration_ms: float, ast_used: bool
) -> None:
    counts = totals.detector_counts
    confidence_max = totals.confidence_max
    _audit(
        hook=HOOK_NAME,
        decision="block",
        tool=tool,
        reason=f"in-place mutation ({sum(counts.values())} hits across {len(counts)} detectors)",
        version=VERSION,
        duration_ms=duration_ms,
        ast_used=ast_used,
        detector=",".join(
            f"{k}:{v}" for k, v in sorted(counts.items())[:DETECTOR_SUMMARY_LIMIT]
        ),
        files_scanned=totals.files_scanned,
        command_excerpt=" | ".join(totals.findings)[:COMMAND_EXCERPT_LIMIT],
        confidence_score=confidence_max if confidence_max > 0 else None,
        sarif_level=to_sarif_level(confidence_max) if confidence_max > 0 else None,
    )


def _finish(tool: str, totals: ScanTotals, duration_ms: float, ast_used: bool) -> int:
    if not totals.findings:
        _audit_allow(tool, totals, duration_ms, ast_used)
        _audit_perf(duration_ms, totals.files_scanned)
        return 0
    message = _build_message(list(totals.findings))
    _audit_block(tool, totals, duration_ms, ast_used)
    _audit_perf(duration_ms, totals.files_scanned)
    return _deny(message)


def main() -> int:
    if not should_run(HOOK_NAME):
        sys.exit(0)
    start_ts = time.perf_counter()
    cli_exit = _handle_cli_flags()
    if cli_exit is not None:
        return cli_exit
    if _bypass_requested():
        return 0
    tool, items = _collect_items()
    if not items:
        return 0
    ast_used = ast_grep_path() is not None
    scans = [_scan_item(path, text, full) for path, _field, text, full in items]
    totals = aggregate_scans([scan for scan in scans if scan is not None])
    duration_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
    return _finish(tool, totals, duration_ms, ast_used)


def _entrypoint() -> int:
    if not _profile_mode():
        return main()
    import cProfile
    import pstats

    profiler = cProfile.Profile()
    code = profiler.runcall(main)
    log_dir = os.path.join(os.path.expanduser("~"), ".claude", "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        with open(
            os.path.join(log_dir, "mutation_blocker_profile.txt"),
            "w",
            encoding="utf-8",
        ) as fh:
            stats = pstats.Stats(profiler, stream=fh).sort_stats("cumulative")
            stats.print_stats(30)
    except OSError as error:
        sys.stderr.write(f"mutation-method-blocker: profile write failed: {error}\n")
    return code


if __name__ == "__main__":
    sys.exit(_entrypoint())
