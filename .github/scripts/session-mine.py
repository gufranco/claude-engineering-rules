#!/usr/bin/env python3
"""Turn Claude Code transcript metadata into vault project notes.

A record of what was worked on, when, and on which branches, recovered from
transcripts that would otherwise be read by nobody.

What it uses, and the limit that follows. Every field here is observed from the
transcript record: the working directory, the git branch, the timestamps, the
session count, and the per-session title the CLI already generated. It does not
read conversation bodies, so it recovers what a session was about and never what
the session concluded. A note claiming otherwise would be inference dressed as
history, which the specification exists to prevent.

Streams the files rather than loading them, because the corpus runs to hundreds
of megabytes.

Usage:

    python3 .github/scripts/session-mine.py [--projects DIR] [--path VAULT]
        [--apply] [--json]

Never overwrites an existing note.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import knowledge_notes as kn  # noqa: E402

DEFAULT_PROJECTS = REPO_ROOT / "projects"
PROJECTS_SUBPATH = Path("wiki") / "projects"
MAX_TITLES = 40
UNSAFE = str.maketrans({c: " " for c in '/\\:*?"<>|#[]^'})


@dataclass
class Summary:
    directory: str
    name: str = ""
    sessions: int = 0
    cwds: set[str] = field(default_factory=set)
    branch_set: set[str] = field(default_factory=set)
    title_set: set[str] = field(default_factory=set)
    first: str = ""
    last: str = ""

    @property
    def titles(self) -> list[str]:
        return sorted(self.title_set)

    @property
    def branches(self) -> list[str]:
        return sorted(self.branch_set)


def note_name(summary: Summary, taken: set[str] | None = None) -> str:
    """Return a filesystem-safe, unique note title for a project.

    Two checkouts can share a basename, and a name collision would silently
    collapse them into one note. Disambiguation walks up the recorded working
    directory until the name is distinct.
    """
    base = " ".join(summary.name.translate(UNSAFE).split()).lstrip(".").strip()
    base = base or "Unknown project"
    if taken is None or base not in taken:
        return base
    parts = Path(sorted(summary.cwds)[0]).parts if summary.cwds else ()
    for depth in range(2, len(parts) + 1):
        candidate = (
            " ".join(" ".join(parts[-depth:]).translate(UNSAFE).split())
            .lstrip(".")
            .strip()
        )
        if candidate and candidate not in taken:
            return candidate
    suffix = 2
    while f"{base} {suffix}" in taken:
        suffix += 1
    return f"{base} {suffix}"


def scan(projects: Path) -> dict[str, Summary]:
    """Walk every transcript and collect observable facts per project."""
    found: dict[str, Summary] = {}
    for directory in sorted(p for p in projects.iterdir() if p.is_dir()):
        transcripts = sorted(directory.glob("*.jsonl"))
        if not transcripts:
            continue
        summary = Summary(directory=directory.name)
        for transcript in transcripts:
            summary.sessions += 1
            try:
                handle = transcript.open(encoding="utf-8", errors="replace")
            except OSError:  # pragma: no cover
                continue
            with handle:
                for line in handle:
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(entry, dict):  # pragma: no cover
                        continue
                    title = entry.get("aiTitle")
                    if title:
                        summary.title_set.add(title.strip())
                    cwd = entry.get("cwd")
                    if cwd:
                        summary.cwds.add(cwd)
                    branch = entry.get("gitBranch")
                    if branch:
                        summary.branch_set.add(branch)
                    stamp = entry.get("timestamp")
                    if stamp and len(stamp) >= 10:
                        day = stamp[:10]
                        if not summary.first or day < summary.first:
                            summary.first = day
                        if not summary.last or day > summary.last:
                            summary.last = day
        if summary.cwds:
            summary.name = Path(sorted(summary.cwds)[0]).name
        if not summary.name:
            summary.name = summary.directory.strip("-").split("-")[-1]
        found[directory.name] = summary
    return found


def render(summary: Summary) -> str:
    """Render one project note. Every claim is stamped or timeless."""
    today = date.today().isoformat()
    span = (
        f"{summary.first} to {summary.last}"
        if summary.first and summary.last
        else "dates not recorded"
    )
    lines = [
        "---",
        f"date: {today}",
        "type: project",
        "tags: [project, session-history]",
        "ai-first: true",
        "confidence: stated",
        f"first_session: {summary.first or 'TBD'}",
        f"last_session: {summary.last or 'TBD'}",
        f"description: Session history for {note_name(summary)}, from transcript metadata",
        "---",
        "",
        kn.PREAMBLE,
        "",
        f"What was worked on in {note_name(summary)}, recovered from Claude Code transcript "
        "metadata rather than from the conversations themselves. It records what each session "
        "was about and never what any session concluded, so treat it as an index into the work "
        "rather than as the knowledge produced by it. Anything durable here deserves its own note.",
        "",
        "## Where",
        "",
    ]
    for cwd in sorted(summary.cwds) or ["not recorded"]:
        lines.append(f"- `{cwd}`")
    lines += [
        "",
        "## When",
        "",
        f"- Active {span}",
        f"- {summary.sessions} recorded session(s) (as of {today})",
    ]
    if summary.branches:
        lines += ["", "## Branches", ""]
        for branch in summary.branches:
            lines.append(f"- `{branch}`")
    lines += ["", "## Sessions", ""]
    if summary.titles:
        for title in summary.titles[:MAX_TITLES]:
            lines.append(f"- {title}")
        if len(summary.titles) > MAX_TITLES:
            lines.append(f"- and {len(summary.titles) - MAX_TITLES} more not listed")
    else:
        lines.append(
            "- No session titles were recorded. TBD until one is written by hand."
        )
    lines.append("")
    return "\n".join(lines)


def apply(found: dict[str, Summary], root: Path, dry_run: bool) -> list[str]:
    """Write one note per project. Never overwrites an existing note."""
    written: list[str] = []
    taken: set[str] = set()
    for summary in found.values():
        title = note_name(summary, taken)
        taken.add(title)
        rel = PROJECTS_SUBPATH / f"{title}.md"
        target = root / rel
        if target.exists():
            continue
        written.append(rel.as_posix())
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render(summary), encoding="utf-8")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mine transcript metadata into vault notes."
    )
    parser.add_argument("--projects", default=str(DEFAULT_PROJECTS))
    parser.add_argument("--path", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = kn.vault_root(args.path)
    if root is None:
        target = args.path or "SECOND_BRAIN_VAULT"
        print(f"session-mine: {target} is not a directory", file=sys.stderr)
        return 2

    projects = Path(args.projects)
    if not projects.is_dir():
        print(
            f"session-mine: transcript directory {projects} does not exist",
            file=sys.stderr,
        )
        return 2

    found = scan(projects)
    written = apply(found, root, dry_run=not args.apply)

    if args.json:
        print(
            json.dumps(
                {
                    "projects": len(found),
                    "sessions": sum(s.sessions for s in found.values()),
                    "titles": sum(len(s.title_set) for s in found.values()),
                    "notes": written,
                    "applied": args.apply,
                },
                indent=2,
            )
        )
    else:
        for summary in sorted(found.values(), key=lambda s: -s.sessions):
            print(
                f"{summary.sessions:>4} session(s)  {summary.first or '?'}..{summary.last or '?'}  "
                f"{note_name(summary)}"
            )
        verb = "wrote" if args.apply else "would write"
        print(f"\n{verb} {len(written)} note(s)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
