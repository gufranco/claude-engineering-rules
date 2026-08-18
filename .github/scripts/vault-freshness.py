#!/usr/bin/env python3
"""Report facts in a second brain vault that have gone stale or never had a date.

Implements the freshness policy: every stored fact must be timeless, a dated
snapshot, or a pointer to where truth lives.

    FRESH-1  error    a present-tense claim about a volatile subject, undated
    FRESH-2  warning  a stamp older than the freshness window
    FRESH-3  error    a pointer with no resolvable target
    FRESH-4  exempt   dated containers are immutable history and are skipped

A FRESH-2 warning has three legal answers: re-observe and restamp, convert to a
pointer and drop the number, or retire the claim into a dated note. Nothing here
deletes anything.

Usage:

    python3 .github/scripts/vault-freshness.py [--path DIR] [--window DAYS]
                                               [--today YYYY-MM-DD] [--json] [--strict]

Rule source: ``rules/knowledge-notes.md``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import knowledge_notes as kn  # noqa: E402

POINTER = re.compile(r"where truth lives", re.IGNORECASE)
ERROR_CODES = frozenset({"FRESH-1", "FRESH-3"})

SUMMARIES = {
    "FRESH-1": "undated claim about a subject that moves",
    "FRESH-2": "stamp older than the freshness window",
    "FRESH-3": "pointer with no resolvable target",
}

REMEDIES = {
    "FRESH-1": "stamp it, convert it to a pointer, or move it into a dated note",
    "FRESH-2": "re-observe and restamp, convert to a pointer, or retire into a dated note",
    "FRESH-3": "give the pointer a URL or a typed id such as linear:TICKET-123",
}


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    line: int
    text: str

    @property
    def severity(self) -> str:
        return "error" if self.code in ERROR_CODES else "warning"

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "line": self.line,
            "text": self.text,
            "summary": SUMMARIES[self.code],
            "remedy": REMEDIES[self.code],
        }


def parse_date(value: str) -> date:
    """Return the date named by an ISO string, or exit with a usage error."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise SystemExit(f"vault-freshness: {value} is not an ISO date")


def has_target(line: str) -> bool:
    """Return True when a pointer line names somewhere the truth actually lives."""
    if kn.URL.search(line):
        return True
    tail = line.split(":", 1)[1] if ":" in line else line
    return bool(kn.TYPED_ID.search(tail))


def audit(root: Path, window: int, today: date) -> list[Finding]:
    """Return every freshness finding in the vault, ordered by path."""
    findings: list[Finding] = []
    for rel, text in kn.iter_notes(root):
        if kn.is_dated_container(rel):
            continue
        path = str(rel)
        body = kn.body_after_frontmatter(text)
        for number, line, under_dated_heading in kn.walk_lines(body):
            if under_dated_heading:
                continue
            if POINTER.search(line):
                if not has_target(line):
                    findings.append(Finding("FRESH-3", path, number, line))
                continue
            stamps = kn.stamp_dates(line)
            if stamps:
                if (today - max(stamps)).days > window:
                    findings.append(Finding("FRESH-2", path, number, line))
            elif kn.is_volatile_claim(line):
                findings.append(Finding("FRESH-1", path, number, line))
    return sorted(findings, key=lambda item: (item.path, item.line, item.code))


def render(findings: list[Finding], root: Path, window: int) -> str:
    if not findings:
        return f"clean: every fact in {root} is timeless, dated, or a pointer"
    lines = []
    for finding in findings:
        lines.append(
            f"{finding.path}:{finding.line} {finding.code} {finding.severity}: "
            f"{SUMMARIES[finding.code]}\n    {finding.text}\n    fix: {REMEDIES[finding.code]}"
        )
    errors = sum(1 for finding in findings if finding.severity == "error")
    warnings = len(findings) - errors
    lines.append(f"\n{errors} error(s), {warnings} warning(s), window {window} day(s)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report stale facts in a vault.")
    parser.add_argument("--path", default=None)
    parser.add_argument("--window", type=int, default=kn.DEFAULT_WINDOW_DAYS)
    parser.add_argument("--today", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    today = parse_date(args.today) if args.today else date.today()

    root = kn.vault_root(args.path)
    if root is None:
        target = args.path or "SECOND_BRAIN_VAULT"
        print(f"vault-freshness: {target} is not a directory", file=sys.stderr)
        return 2

    findings = audit(root, window=args.window, today=today)
    errors = sum(1 for finding in findings if finding.severity == "error")
    if args.json:
        print(
            json.dumps(
                {
                    "root": str(root),
                    "window_days": args.window,
                    "today": today.isoformat(),
                    "counts": {"error": errors, "warning": len(findings) - errors},
                    "findings": [finding.as_dict() for finding in findings],
                },
                indent=2,
            )
        )
    else:
        print(render(findings, root, args.window))
    return 1 if args.strict and errors else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
