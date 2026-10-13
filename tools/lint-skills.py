#!/usr/bin/env python3
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

HARNESS_MANAGED_DIRS = frozenset({"synced"})

TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_-]*):(?:\s+(.*))?$")
DOUBLE_QUOTED_RE = re.compile(r'^"(?:[^"\\]|\\.)*"\s*(?:#.*)?$')
SINGLE_QUOTED_RE = re.compile(r"^'(?:[^']|'')*'\s*(?:#.*)?$")
BLOCK_SCALAR_RE = re.compile(r"^[|>][+-]?[1-9]?[+-]?\s*(?:#.*)?$")
RESERVED_START = frozenset(",@`%*!]}")
INDICATOR_WITH_SPACE = ("- ", "? ", ": ")
LONE_INDICATORS = frozenset({"-", "?", ":"})
USER_INVOKED_TRIGGER_MARKERS = ("Use when", "Do NOT")


@dataclass
class Finding:
    severity: str
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


def plain_scalar_error(text: str) -> str | None:
    content = text.split(" #", 1)[0].rstrip()
    if ": " in content or content.endswith(":"):
        return "plain scalar contains ': ', so strict YAML reads a nested mapping; quote the value"
    return None


def value_error(value: str) -> tuple[str | None, str]:
    if not value or value.startswith("#"):
        return None, "free"
    first = value[0]
    if first == '"' or first == "'":
        pattern = DOUBLE_QUOTED_RE if first == '"' else SINGLE_QUOTED_RE
        if pattern.match(value):
            return None, "free"
        return "text after the closing quote, or the quote never closes", "free"
    if first in "|>":
        if BLOCK_SCALAR_RE.match(value):
            return None, "free"
        return "invalid block scalar header", "free"
    if first in "[{":
        return None, "free"
    if first in RESERVED_START:
        return (
            f"plain scalar starts with reserved indicator '{first}'; quote the value",
            "free",
        )
    if value in LONE_INDICATORS or value.startswith(INDICATOR_WITH_SPACE):
        return f"plain scalar starts with indicator '{first}'; quote the value", "free"
    return plain_scalar_error(value), "plain"


def line_error(line: str, mode: str | None) -> tuple[str | None, str | None]:
    if line.startswith("\t"):
        return "tab in indentation", mode
    if line.startswith(" "):
        if mode is None:
            return "indented line with no parent key", mode
        if mode == "plain":
            return plain_scalar_error(line.strip()), mode
        return None, mode
    match = TOP_LEVEL_KEY_RE.match(line)
    if match is None:
        return "expected a `key: value` line", None
    return value_error((match.group(2) or "").strip())


def find_yaml_errors(raw: str) -> list[str]:
    errors: list[str] = []
    mode: str | None = None
    for number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        error, mode = line_error(line, mode)
        if error:
            errors.append(f"line {number}: {error}")
    return errors


def plain_line_text(line: str, mode: str | None) -> tuple[str | None, str | None]:
    if line.startswith(" "):
        return (line.strip() if mode == "plain" else None), mode
    match = TOP_LEVEL_KEY_RE.match(line)
    if match is None:
        return None, None
    value = (match.group(2) or "").strip()
    _, next_mode = value_error(value)
    return (value if next_mode == "plain" else None), next_mode


def find_truncating_comments(raw: str) -> list[str]:
    errors: list[str] = []
    mode: str | None = None
    for number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        text, mode = plain_line_text(line, mode)
        if text is not None and " #" in text:
            errors.append(
                f"line {number}: ' #' in a plain scalar starts a YAML comment, "
                "so everything after it is dropped; quote the value"
            )
    return errors


def yaml_findings(text: str) -> list[Finding]:
    match = FRONTMATTER_RE.match(text)
    if match is None:
        return []
    raw = match.group(1)
    invalid = [
        Finding("error", "invalid-yaml", shift_line(error))
        for error in find_yaml_errors(raw)
    ]
    truncated = [
        Finding("error", "truncated-by-comment", shift_line(error))
        for error in find_truncating_comments(raw)
    ]
    return invalid + truncated


def shift_line(error: str) -> str:
    number, _, rest = error.partition(": ")
    frontmatter_line = int(number.removeprefix("line "))
    return f"line {frontmatter_line + 1}: {rest}"


def invocation_findings(fields: dict) -> list[Finding]:
    findings: list[Finding] = []
    if fields.get("user-invocable", "").strip().lower() == "true":
        findings.append(
            Finding(
                "warning",
                "noop-user-invocable",
                "`user-invocable: true` is the default and does nothing",
                fix_hint="Delete the `user-invocable: true` line.",
            )
        )
    user_invoked = fields.get("disable-model-invocation", "").strip().lower() == "true"
    description = fields.get("description", "")
    if user_invoked and any(m in description for m in USER_INVOKED_TRIGGER_MARKERS):
        findings.append(
            Finding(
                "warning",
                "trigger-list-on-user-invoked",
                "user-invoked skill carries a trigger list or routing clause the model never reads",
                fix_hint="Replace the description with one human-facing sentence.",
            )
        )
    return findings


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

    report.findings.extend(yaml_findings(text))
    report.findings.extend(invocation_findings(fields))

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


def is_skill_dir(path: Path) -> bool:
    name = path.parent.name
    return not name.startswith(".") and name not in HARNESS_MANAGED_DIRS


def discover_skills(targets: list[str], skills_dir: Path = SKILLS_DIR) -> list[Path]:
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
    return sorted(p for p in skills_dir.glob("*/SKILL.md") if is_skill_dir(p))


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
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=SKILLS_DIR,
        help="root scanned when no targets are given",
    )
    args = parser.parse_args(argv)

    files = discover_skills(args.targets, args.skills_dir)
    if not files:
        print("no SKILL.md files found", file=sys.stderr)
        return 1

    reports = [lint_file(p) for p in files]
    if args.json:
        return print_json_report(reports, args.strict)
    return print_text_report(reports, args.strict, args.fix_hints)


if __name__ == "__main__":
    sys.exit(main())
