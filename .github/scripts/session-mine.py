#!/usr/bin/env python3
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


def _absorb_stamp(summary: Summary, stamp: str | None) -> None:
    if not stamp or len(stamp) < 10:
        return
    day = stamp[:10]
    if not summary.first or day < summary.first:
        summary.first = day
    if not summary.last or day > summary.last:
        summary.last = day


def _absorb_entry(summary: Summary, entry: dict[str, str]) -> None:
    title = entry.get("aiTitle")
    if title:
        summary.title_set.add(title.strip())
    cwd = entry.get("cwd")
    if cwd:
        summary.cwds.add(cwd)
    branch = entry.get("gitBranch")
    if branch:
        summary.branch_set.add(branch)
    _absorb_stamp(summary, entry.get("timestamp"))


def _parse_entry(line: str) -> dict[str, str] | None:
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    if not isinstance(entry, dict):  # pragma: no cover
        return None
    return entry


def _absorb_transcript(summary: Summary, transcript: Path) -> None:
    summary.sessions += 1
    try:
        handle = transcript.open(encoding="utf-8", errors="replace")
    except OSError:  # pragma: no cover
        return
    with handle:
        for line in handle:
            entry = _parse_entry(line)
            if entry is not None:
                _absorb_entry(summary, entry)


def _summarize(directory: Path, transcripts: list[Path]) -> Summary:
    summary = Summary(directory=directory.name)
    for transcript in transcripts:
        _absorb_transcript(summary, transcript)
    if summary.cwds:
        summary.name = Path(sorted(summary.cwds)[0]).name
    if not summary.name:
        summary.name = summary.directory.strip("-").split("-")[-1]
    return summary


def scan(projects: Path) -> dict[str, Summary]:
    found: dict[str, Summary] = {}
    for directory in sorted(p for p in projects.iterdir() if p.is_dir()):
        transcripts = sorted(directory.glob("*.jsonl"))
        if transcripts:
            found[directory.name] = _summarize(directory, transcripts)
    return found


def _header_lines(summary: Summary, today: str) -> list[str]:
    return [
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
    ]


def _where_when_lines(summary: Summary, today: str) -> list[str]:
    span = (
        f"{summary.first} to {summary.last}"
        if summary.first and summary.last
        else "dates not recorded"
    )
    return [
        "## Where",
        "",
        *(f"- `{cwd}`" for cwd in sorted(summary.cwds) or ["not recorded"]),
        "",
        "## When",
        "",
        f"- Active {span}",
        f"- {summary.sessions} recorded session(s) (as of {today})",
    ]


def _branch_lines(summary: Summary) -> list[str]:
    if not summary.branches:
        return []
    return ["", "## Branches", "", *(f"- `{b}`" for b in summary.branches)]


def _session_lines(summary: Summary) -> list[str]:
    titles = summary.titles
    if not titles:
        return ["- No session titles were recorded. TBD until one is written by hand."]
    listed = [f"- {title}" for title in titles[:MAX_TITLES]]
    if len(titles) > MAX_TITLES:
        return [*listed, f"- and {len(titles) - MAX_TITLES} more not listed"]
    return listed


def render(summary: Summary) -> str:
    today = date.today().isoformat()
    lines = [
        *_header_lines(summary, today),
        *_where_when_lines(summary, today),
        *_branch_lines(summary),
        "",
        "## Sessions",
        "",
        *_session_lines(summary),
        "",
    ]
    return "\n".join(lines)


def apply(found: dict[str, Summary], root: Path, dry_run: bool) -> list[str]:
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


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mine transcript metadata into vault notes."
    )
    parser.add_argument("--projects", default=str(DEFAULT_PROJECTS))
    parser.add_argument("--path", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _print_json(found: dict[str, Summary], written: list[str], applied: bool) -> None:
    report = {
        "projects": len(found),
        "sessions": sum(s.sessions for s in found.values()),
        "titles": sum(len(s.title_set) for s in found.values()),
        "notes": written,
        "applied": applied,
    }
    print(json.dumps(report, indent=2))


def _print_table(found: dict[str, Summary], written: list[str], applied: bool) -> None:
    for summary in sorted(found.values(), key=lambda s: -s.sessions):
        print(
            f"{summary.sessions:>4} session(s)  {summary.first or '?'}..{summary.last or '?'}  "
            f"{note_name(summary)}"
        )
    verb = "wrote" if applied else "would write"
    print(f"\n{verb} {len(written)} note(s)")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
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
    report = _print_json if args.json else _print_table
    report(found, written, args.apply)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
