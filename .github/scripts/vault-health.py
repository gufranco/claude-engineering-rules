#!/usr/bin/env python3
"""Report structural defects across a second brain vault.

Whole-graph checks that a write-time hook cannot make, because they need every
note at once. The note grammar itself comes from ``hooks/_lib/knowledge_notes``
so this linter and the write-time guard can never disagree about what a note is.

    VH001  error    a required frontmatter key is missing
    VH002  error    the fixed preamble is missing
    VH003  error    a wikilink points at a note that does not exist
    VH004  warning  no other note links here
    VH005  warning  two notes share a title, so a wikilink to it is ambiguous
    VH006  warning  the note is absent from the index
    VH007  warning  the note links to nothing

Usage:

    python3 .github/scripts/vault-health.py [--path DIR] [--json] [--strict]

Rule source: ``rules/knowledge-notes.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import knowledge_notes as kn  # noqa: E402

ROOT_FILES = ("index.md", "log.md")
ERROR_CODES = frozenset({"VH001", "VH002", "VH003"})

SUMMARIES = {
    "VH001": "required frontmatter key missing",
    "VH002": "the fixed preamble is missing",
    "VH003": "wikilink target does not exist",
    "VH004": "no inbound links",
    "VH005": "duplicate note title",
    "VH006": "absent from the index",
    "VH007": "no outbound links",
}


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    line: int
    detail: str

    @property
    def severity(self) -> str:
        return "error" if self.code in ERROR_CODES else "warning"

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "line": self.line,
            "detail": self.detail,
            "summary": SUMMARIES[self.code],
        }


def audit(root: Path) -> list[Finding]:
    """Return every structural finding in the vault, ordered by path."""
    notes = list(kn.iter_notes(root))
    titles: dict[str, list[str]] = defaultdict(list)
    for rel, _text in notes:
        titles[rel.stem].append(str(rel))
    known = set(titles)

    inbound: dict[str, set[str]] = defaultdict(set)
    outbound: dict[str, set[str]] = defaultdict(set)
    findings: list[Finding] = []

    for rel, text in notes:
        path = str(rel)
        fields = kn.parse_frontmatter(text)
        if fields is None:
            findings.append(Finding("VH001", path, 1, "no frontmatter block"))
        else:
            missing = [key for key in kn.REQUIRED_KEYS if key not in fields]
            if missing:
                findings.append(Finding("VH001", path, 1, ", ".join(missing)))
        body = kn.body_after_frontmatter(text)
        if kn.PREAMBLE not in body:
            findings.append(Finding("VH002", path, 1, kn.PREAMBLE))
        for number, line, _dated in kn.walk_lines(body):
            for target in kn.wikilink_targets(line):
                outbound[path].add(target)
                if target in known:
                    inbound[target].add(path)
                elif not kn.TBD.search(line):
                    findings.append(Finding("VH003", path, number, target))

    index_links = outbound.get("index.md", set())

    for rel, _text in notes:
        path = str(rel)
        if path in ROOT_FILES:
            continue
        if not kn.is_dated_container(rel):
            if not inbound.get(rel.stem):
                findings.append(Finding("VH004", path, 1, rel.stem))
            if rel.stem not in index_links:
                findings.append(Finding("VH006", path, 1, rel.stem))
        if not outbound.get(path):
            findings.append(Finding("VH007", path, 1, rel.stem))

    for stem, paths in sorted(titles.items()):
        if len(paths) > 1:
            findings.append(
                Finding("VH005", paths[0], 1, f"{stem}: {', '.join(sorted(paths))}")
            )

    return sorted(findings, key=lambda item: (item.path, item.line, item.code))


def render(findings: list[Finding], root: Path) -> str:
    if not findings:
        return f"clean: no structural findings across {root}"
    lines = []
    for finding in findings:
        lines.append(
            f"{finding.path}:{finding.line} {finding.code} {finding.severity}: "
            f"{SUMMARIES[finding.code]} [{finding.detail}]"
        )
    errors = sum(1 for finding in findings if finding.severity == "error")
    warnings = len(findings) - errors
    lines.append(f"\n{errors} error(s), {warnings} warning(s)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report structural defects in a vault."
    )
    parser.add_argument("--path", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    root = kn.vault_root(args.path)
    if root is None:
        target = args.path or "SECOND_BRAIN_VAULT"
        print(f"vault-health: {target} is not a directory", file=sys.stderr)
        return 2

    findings = audit(root)
    errors = sum(1 for finding in findings if finding.severity == "error")
    if args.json:
        print(
            json.dumps(
                {
                    "root": str(root),
                    "counts": {"error": errors, "warning": len(findings) - errors},
                    "findings": [finding.as_dict() for finding in findings],
                },
                indent=2,
            )
        )
    else:
        print(render(findings, root))
    return 1 if args.strict and errors else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
