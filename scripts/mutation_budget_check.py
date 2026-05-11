#!/usr/bin/env python3
"""Per-project mutation suppression budget checker (plan item 392).

A project can carry a finite amount of suppression debt before the
"immutable by default" rule erodes. This script walks the project,
counts `@claude-allow-mutation` and `claude-allow-mutation` markers,
and exits non-zero when any configured cap is exceeded.

Usage:

    python3 ~/.claude/scripts/mutation_budget_check.py [--root <dir>]
            [--format text|json|sarif] [--strict]

The project root is detected by walking up from the cwd until a
`.git/`, `package.json`, or `pnpm-workspace.yaml` is found, or
overridden via `--root`. Configuration is read from
`<root>/.claude/mutation-budget.yml` (or `.yaml`, `.json`). When no
config exists, the script reports counts and exits zero so first-time
users see the picture before opting in to a cap.

Exit codes:

    0   counts within budget (or no config present)
    1   any cap exceeded; details on stderr
    2   config invalid (syntax error, schema mismatch)
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any

MARKER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"@claude-allow-mutation(?:\s*--\s*(?P<reason>.+))?"),
    re.compile(r"(?<!@)claude-allow-mutation(?:\s*--\s*(?P<reason>.+))?"),
)

DEFAULT_INCLUDE_EXTS: tuple[str, ...] = (
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
)

DEFAULT_EXCLUDES: tuple[str, ...] = (
    "**/node_modules/**",
    "**/dist/**",
    "**/build/**",
    "**/out/**",
    "**/.next/**",
    "**/.nuxt/**",
    "**/coverage/**",
)

DETECTOR_HINTS: dict[str, tuple[re.Pattern[str], ...]] = {
    "array": (
        re.compile(
            r"\.(?:push|pop|shift|unshift|splice|sort|reverse|fill|copyWithin)\b"
        ),
    ),
    "collection": (re.compile(r"\.(?:set|add|delete|clear)\s*\("),),
    "date": (
        re.compile(
            r"\.set(?:Date|FullYear|Hours|Milliseconds|Minutes|Month|Seconds|Time|Year|UTC[A-Z][a-zA-Z]*)\s*\("
        ),
    ),
    "property": (
        re.compile(r"\b[a-zA-Z_$][\w$]*\.[a-zA-Z_$][\w$]*\s*[+\-*/%&|^]?=(?!=)"),
    ),
    "global": (
        re.compile(r"\b(?:globalThis|process\.env)\.[a-zA-Z_$][\w$]*\s*=(?!=)"),
    ),
    "delete": (
        re.compile(r"\bdelete\s+[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*|\[[^\]]+\])"),
    ),
    "typed-array": (
        re.compile(r"\b(?:Int|Uint|Float|BigInt|BigUint)\d+(?:Clamped)?Array\b"),
    ),
}


@dataclass(frozen=True)
class Marker:
    """A single suppression marker found in a file."""

    file_path: str
    line: int
    text: str
    justified: bool
    detector_hint: str


@dataclass
class Report:
    """Per-project marker tally and verdict."""

    total: int = 0
    per_detector: dict[str, int] = field(default_factory=dict)
    unjustified: list[Marker] = field(default_factory=list)
    markers: list[Marker] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)


def _detect_root(start: str) -> str:
    """Walk up from `start` until a project root sentinel is found."""
    cur = os.path.abspath(start)
    while True:
        for sentinel in (".git", "package.json", "pnpm-workspace.yaml"):
            if os.path.exists(os.path.join(cur, sentinel)):
                return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.abspath(start)
        cur = parent


def _load_config(root: str) -> dict[str, Any] | None:
    """Load `.claude/mutation-budget.{yml,yaml,json}` from `root`."""
    base = os.path.join(root, ".claude")
    for name in ("mutation-budget.yml", "mutation-budget.yaml", "mutation-budget.json"):
        path = os.path.join(base, name)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as exc:
            print(f"mutation-budget: cannot read {path}: {exc}", file=sys.stderr)
            return None
        if name.endswith(".json"):
            try:
                parsed_json: object = json.loads(raw)
                return parsed_json if isinstance(parsed_json, dict) else None
            except json.JSONDecodeError as exc:
                print(f"mutation-budget: {path}: {exc}", file=sys.stderr)
                return None
        try:
            import yaml

            parsed_yaml: object = yaml.safe_load(raw)
            return parsed_yaml if isinstance(parsed_yaml, dict) else None
        except ImportError:
            print(
                f"mutation-budget: {path}: PyYAML missing; install pyyaml or use .json",
                file=sys.stderr,
            )
            return None
        except yaml.YAMLError as exc:
            print(f"mutation-budget: {path}: {exc}", file=sys.stderr)
            return None
    return None


def _validate_config(cfg: dict[str, Any]) -> list[str]:
    """Lightweight schema check. Returns a list of error strings."""
    errors: list[str] = []
    if not isinstance(cfg, dict):
        return ["root must be an object"]
    version = cfg.get("version")
    if version != 1:
        errors.append("version must equal 1")
    if "total" not in cfg:
        errors.append("total is required")
    elif not isinstance(cfg["total"], int) or cfg["total"] < 0:
        errors.append("total must be a non-negative integer")
    per_det = cfg.get("per_detector")
    if per_det is not None:
        if not isinstance(per_det, dict):
            errors.append("per_detector must be an object")
        else:
            for key, val in per_det.items():
                if not isinstance(val, int) or val < 0:
                    errors.append(f"per_detector.{key} must be a non-negative integer")
    return errors


def _iter_files(root: str, includes: list[str], excludes: list[str]) -> list[str]:
    """Yield every candidate source file under `root`."""
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if not d.startswith(".") or d in {".next", ".nuxt"}
        ]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if includes and not any(fnmatch.fnmatch(rel, pat) for pat in includes):
                continue
            if any(fnmatch.fnmatch(rel, pat) for pat in excludes):
                continue
            if not includes and not any(
                name.endswith(ext) for ext in DEFAULT_INCLUDE_EXTS
            ):
                continue
            out.append(full)
    return out


def _classify_detector(line_text: str) -> str:
    """Best-effort detector hint from the line a marker sits on."""
    for label, patterns in DETECTOR_HINTS.items():
        for pat in patterns:
            if pat.search(line_text):
                return label
    return "unknown"


def _scan_file(path: str) -> list[Marker]:
    """Find every suppression marker in `path`."""
    markers: list[Marker] = []
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except (OSError, UnicodeDecodeError):
        return markers
    for idx, raw in enumerate(lines):
        for pattern in MARKER_PATTERNS:
            m = pattern.search(raw)
            if not m:
                continue
            reason = (m.group("reason") or "").strip()
            justified = bool(reason)
            target_idx = idx + 1 if idx + 1 < len(lines) else idx
            target_text = lines[target_idx] if target_idx != idx else raw
            detector_hint = _classify_detector(target_text)
            markers.append(Marker(path, idx + 1, raw.strip(), justified, detector_hint))
            break
    return markers


def _build_report(
    markers: list[Marker],
    total_cap: int,
    per_detector_caps: dict[str, int],
    require_justification: bool,
) -> Report:
    rep = Report(markers=markers)
    rep.total = len(markers)
    for m in markers:
        rep.per_detector[m.detector_hint] = rep.per_detector.get(m.detector_hint, 0) + 1
        if require_justification and not m.justified:
            rep.unjustified.append(m)
    if rep.total > total_cap:
        rep.violations.append(f"total markers {rep.total} exceed cap {total_cap}")
    for detector, count in sorted(rep.per_detector.items()):
        cap = per_detector_caps.get(detector, total_cap)
        if count > cap:
            rep.violations.append(
                f"detector {detector!r} count {count} exceeds cap {cap}"
            )
    if require_justification and rep.unjustified:
        rep.violations.append(
            f"{len(rep.unjustified)} markers missing `-- <reason>` justification"
        )
    return rep


def _render_text(report: Report, total_cap: int, per_caps: dict[str, int]) -> str:
    out: list[str] = []
    out.append("mutation-budget report")
    out.append(f"  total markers: {report.total} (cap: {total_cap})")
    if report.per_detector:
        out.append("  per detector:")
        for label, count in sorted(report.per_detector.items()):
            cap = per_caps.get(label, total_cap)
            out.append(f"    {label}: {count} (cap: {cap})")
    if report.unjustified:
        out.append(f"  unjustified: {len(report.unjustified)}")
        for m in report.unjustified[:10]:
            out.append(f"    {m.file_path}:{m.line}")
    if report.violations:
        out.append("violations:")
        for v in report.violations:
            out.append(f"  - {v}")
    return "\n".join(out)


def _render_json(report: Report, total_cap: int, per_caps: dict[str, int]) -> str:
    payload = {
        "total": report.total,
        "total_cap": total_cap,
        "per_detector": [
            {"detector": k, "count": v, "cap": per_caps.get(k, total_cap)}
            for k, v in sorted(report.per_detector.items())
        ],
        "unjustified": [
            {"file": m.file_path, "line": m.line, "text": m.text}
            for m in report.unjustified
        ],
        "violations": report.violations,
    }
    return json.dumps(payload, indent=2)


def _render_sarif(report: Report, root: str) -> str:
    """Emit a minimal SARIF 2.1.0 document for the violations."""
    results = []
    for m in report.unjustified:
        results.append(
            {
                "ruleId": "mutation-budget/unjustified",
                "level": "error",
                "message": {
                    "text": "Suppression marker missing `-- <reason>` justification"
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": os.path.relpath(m.file_path, root)
                            },
                            "region": {"startLine": m.line},
                        },
                    }
                ],
            }
        )
    for violation in report.violations:
        if violation.startswith("total ") or violation.startswith("detector "):
            results.append(
                {
                    "ruleId": "mutation-budget/cap-exceeded",
                    "level": "error",
                    "message": {"text": violation},
                }
            )
    return json.dumps(
        {
            "version": "2.1.0",
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "mutation-budget-check",
                            "version": "1.0.0",
                            "rules": [
                                {"id": "mutation-budget/cap-exceeded"},
                                {"id": "mutation-budget/unjustified"},
                            ],
                        }
                    },
                    "results": results,
                }
            ],
        },
        indent=2,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Project root override.")
    parser.add_argument(
        "--format",
        choices=("text", "json", "sarif"),
        default=None,
        help="Output format override (default reads from config or 'text').",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail with exit code 1 even when no config exists.",
    )
    args = parser.parse_args()

    root = os.path.abspath(args.root) if args.root else _detect_root(os.getcwd())
    cfg = _load_config(root)
    if cfg is None and args.strict:
        print(
            "mutation-budget: no config found and --strict was passed", file=sys.stderr
        )
        return 1
    if cfg is None:
        cfg = {"version": 1, "total": 10**9}

    errors = _validate_config(cfg)
    if errors:
        for err in errors:
            print(f"mutation-budget: config error: {err}", file=sys.stderr)
        return 2

    includes = list(cfg.get("include") or [])
    excludes = list(DEFAULT_EXCLUDES) + list(cfg.get("exclude") or [])
    require_justification = bool(cfg.get("require_justification", True))
    total_cap = int(cfg["total"])
    per_caps: dict[str, int] = {
        str(k): int(v) for k, v in (cfg.get("per_detector") or {}).items()
    }
    fmt = args.format or cfg.get("report_format") or "text"

    files = _iter_files(root, includes, excludes)
    markers: list[Marker] = []
    for path in files:
        markers.extend(_scan_file(path))

    report = _build_report(markers, total_cap, per_caps, require_justification)

    if fmt == "json":
        sys.stdout.write(_render_json(report, total_cap, per_caps))
    elif fmt == "sarif":
        sys.stdout.write(_render_sarif(report, root))
    else:
        sys.stdout.write(_render_text(report, total_cap, per_caps))
    sys.stdout.write("\n")
    return 1 if report.violations else 0


if __name__ == "__main__":
    sys.exit(main())
