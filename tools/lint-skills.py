#!/usr/bin/env python3
"""Validate SKILL.md structure across skills/.

Required (errors, exit non-zero):
  - YAML frontmatter delimited by `---` at the top of the file
  - `name` field, non-empty, matches the parent directory name
  - `description` field, non-empty, >= 30 characters
  - At least one body section (`## ` heading) after frontmatter

Recommended (warnings, exit 0 in default mode):
  - `argument-hint` field with example invocations
  - `allowed-tools` or `disallowed-tools` declared
  - 6-section template: Overview, When to Use, Process,
    Common Rationalizations, Red Flags, Verification

Modes:
  default      report errors AND warnings, exit 0 on warnings, exit 1 on errors
  --strict     treat warnings as errors
  --fix-hints  print exact frontmatter and headings to add
  --json       machine-readable output for CI integration

Usage:
  python3 tools/lint-skills.py
  python3 tools/lint-skills.py --strict
  python3 tools/lint-skills.py skills/plan/SKILL.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"

REQUIRED_SECTIONS = (
    "Overview",
    "When to Use",
    "Process",
    "Common Rationalizations",
    "Red Flags",
    "Verification",
)

SECTION_ALIASES = {
    "Overview": ("Overview", "Description", "Summary", "What it does"),
    "When to Use": ("When to Use", "When to use", "Use Cases", "Triggers"),
    "Process": ("Process", "Workflow", "Steps", "How it works", "Procedure"),
    "Common Rationalizations": (
        "Common Rationalizations",
        "Rationalizations",
        "Anti-patterns",
        "Failure modes",
    ),
    "Red Flags": ("Red Flags", "Warning signs", "Smells"),
    "Verification": ("Verification", "Validation", "Self-check", "Done checklist"),
}

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Finding:
    severity: str  # "error" | "warning"
    code: str
    message: str
    fix_hint: str = ""


@dataclass
class Report:
    path: Path
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse minimal YAML frontmatter. Returns (fields, body)."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw = match.group(1)
    body = text[match.end() :]
    fields: dict = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith(" ") and current_key is not None:
            fields[current_key] = (fields[current_key] + " " + line.strip()).strip()
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        fields[key] = value
        current_key = key
    return fields, body


def find_sections(body: str) -> list[str]:
    return [m.group(1).strip() for m in HEADING_RE.finditer(body)]


def matches_canonical(observed: str, canonical: str) -> bool:
    for alias in SECTION_ALIASES.get(canonical, (canonical,)):
        if observed.lower() == alias.lower():
            return True
    return False


def lint_file(path: Path) -> Report:
    report = Report(path=path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.findings.append(Finding("error", "io-error", f"cannot read file: {exc}"))
        return report

    fields, body = parse_frontmatter(text)
    if not fields:
        report.findings.append(
            Finding(
                "error",
                "missing-frontmatter",
                "no YAML frontmatter found at top of file",
                fix_hint="Add at line 1:\n---\nname: <name>\ndescription: <one-line summary>\n---",
            )
        )
        return report

    expected_name = path.parent.name
    name = fields.get("name", "").strip()
    description = fields.get("description", "").strip()

    if not name:
        report.findings.append(
            Finding("error", "missing-name", "frontmatter `name` is required")
        )
    elif name != expected_name:
        report.findings.append(
            Finding(
                "error",
                "name-mismatch",
                f"frontmatter `name: {name}` does not match dir `{expected_name}`",
            )
        )

    if not description:
        report.findings.append(
            Finding(
                "error", "missing-description", "frontmatter `description` is required"
            )
        )
    elif len(description) < 30:
        report.findings.append(
            Finding(
                "warning",
                "short-description",
                f"description is only {len(description)} chars; aim for 50+",
            )
        )

    if "argument-hint" not in fields:
        report.findings.append(
            Finding(
                "warning",
                "missing-argument-hint",
                "no `argument-hint` declared",
                fix_hint='Add: argument-hint: "<example invocation>"',
            )
        )

    if "allowed-tools" not in fields and "disallowed-tools" not in fields:
        report.findings.append(
            Finding(
                "warning",
                "missing-tool-scope",
                "neither `allowed-tools` nor `disallowed-tools` declared",
                fix_hint='Add one of: allowed-tools: "Read, Edit, Bash"  or  disallowed-tools: "Write, Edit"',
            )
        )

    sections = find_sections(body)
    if not sections:
        report.findings.append(
            Finding("error", "no-sections", "no `## ` body sections found")
        )
        return report

    missing_sections: list[str] = []
    for required in REQUIRED_SECTIONS:
        if not any(matches_canonical(obs, required) for obs in sections):
            missing_sections.append(required)

    if missing_sections:
        report.findings.append(
            Finding(
                "warning",
                "missing-sections",
                f"missing recommended sections: {', '.join(missing_sections)}",
                fix_hint="Add `## <name>` headings for each missing section.",
            )
        )

    return report


def discover_skills(targets: list[str]) -> list[Path]:
    if targets:
        out: list[Path] = []
        for t in targets:
            p = Path(t)
            if not p.is_absolute():
                p = ROOT / t
            if p.is_dir():
                candidate = p / "SKILL.md"
                if candidate.is_file():
                    out.append(candidate)
            elif p.is_file():
                out.append(p)
        return out
    return sorted(SKILLS_DIR.rglob("SKILL.md"))


def print_text_report(reports: list[Report], strict: bool, fix_hints: bool) -> int:
    error_count = 0
    warning_count = 0
    for r in reports:
        if not r.findings:
            continue
        try:
            rel = r.path.relative_to(ROOT)
        except ValueError:
            rel = r.path
        print(f"\n{rel}")
        for f in r.findings:
            severity = "ERROR" if f.severity == "error" else "WARN "
            print(f"  [{severity}] {f.code}: {f.message}")
            if fix_hints and f.fix_hint:
                for line in f.fix_hint.splitlines():
                    print(f"           {line}")
            if f.severity == "error":
                error_count += 1
            else:
                warning_count += 1
    print(
        f"\n{len(reports)} files scanned, {error_count} errors, {warning_count} warnings"
    )
    if error_count > 0:
        return 1
    if strict and warning_count > 0:
        return 1
    return 0


def print_json_report(reports: list[Report], strict: bool) -> int:
    payload = {
        "files": [
            {
                "path": str(r.path),
                "findings": [
                    {
                        "severity": f.severity,
                        "code": f.code,
                        "message": f.message,
                        "fix_hint": f.fix_hint,
                    }
                    for f in r.findings
                ],
            }
            for r in reports
        ]
    }
    print(json.dumps(payload, indent=2))
    error_count = sum(len(r.errors) for r in reports)
    warning_count = sum(len(r.warnings) for r in reports)
    if error_count > 0:
        return 1
    if strict and warning_count > 0:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint SKILL.md files.")
    parser.add_argument("targets", nargs="*", help="specific files or skill dirs")
    parser.add_argument(
        "--strict", action="store_true", help="warnings count as errors"
    )
    parser.add_argument(
        "--fix-hints", action="store_true", help="print fix hints inline"
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args(argv)

    files = discover_skills(args.targets)
    if not files:
        print("no SKILL.md files found", file=sys.stderr)
        return 1

    reports = [lint_file(p) for p in files]
    if args.json:
        return print_json_report(reports, args.strict)
    return print_text_report(reports, args.strict, args.fix_hints)


if __name__ == "__main__":
    sys.exit(main())
