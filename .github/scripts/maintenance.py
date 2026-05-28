#!/usr/bin/env python3
"""Long-horizon maintenance reminders for the mutation-method-blocker hook.

Plan items 282-283. The script keeps two long-running concerns alive across
sessions:

  1. A TC39 watch list of immutability-relevant proposals that the hook does
     NOT yet recognize. When a proposal advances to Stage 2, the hook should
     evaluate adding recognition. The watch list is the canonical source for
     `~/.claude/docs/guides/mutation-method-blocker-add-detector.md` reviewers.

  2. A quarterly review reminder. On the first Monday of each quarter (Jan,
     Apr, Jul, Oct) the script prints a reminder to stdout when run with the
     `quarterly-check` subcommand. The user wires this into a launchd plist
     or a cron entry; the script itself does not schedule anything.

Usage:

    python3 .github/scripts/maintenance.py watch-list
    python3 .github/scripts/maintenance.py quarterly-check
    python3 .github/scripts/maintenance.py quarterly-check --force

The script never modifies hook state and never produces a non-zero exit code
for routine output. A non-zero exit indicates a CLI usage error.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class WatchListEntry:
    """One TC39 (or equivalent) proposal under observation.

    `stage` follows the TC39 process: 0 (strawperson), 1 (proposal),
    2 (draft), 3 (candidate), 4 (finished). Recognition becomes
    appropriate at Stage 2 because the syntax stabilizes; before that
    the proposal can be reshaped beyond recognition.
    """

    name: str
    stage: int
    last_seen: str
    url: str
    rationale: str
    recognition_target: str


WATCH_LIST: tuple[WatchListEntry, ...] = (
    WatchListEntry(
        name="Composites",
        stage=1,
        last_seen="2026-04",
        url="https://github.com/tc39/proposal-composites",
        rationale=(
            "Adds value-equality composite types similar to Records and Tuples "
            "but with explicit construction. When Stage 2 is reached, evaluate "
            "adding recognition for the Composite() constructor and confirm "
            "that mutation attempts on a Composite produce a runtime error."
        ),
        recognition_target="auto-allowed (Composites are immutable by spec)",
    ),
    WatchListEntry(
        name="Pattern Matching",
        stage=1,
        last_seen="2026-04",
        url="https://github.com/tc39/proposal-pattern-matching",
        rationale=(
            "Introduces a `match` expression that binds destructured values. "
            "If accepted, the hook may need to recognize that the bindings "
            "are const-by-construction and skip param-reassign analysis on "
            "match arms."
        ),
        recognition_target="suppress within match arms",
    ),
    WatchListEntry(
        name="ArrayBuffer.prototype.transfer",
        stage=4,
        last_seen="2026-04",
        url="https://github.com/tc39/proposal-arraybuffer-transfer",
        rationale=(
            "Already shipped in Node 22 / Chrome 114. Transfers ownership "
            "rather than mutating in place. No detector change needed: the "
            "method is non-mutating from the caller's perspective. Listed "
            "for completeness because the name shape resembles array prototype "
            "mutators."
        ),
        recognition_target="explicitly allowed (no flag)",
    ),
    WatchListEntry(
        name="Async Iterator Helpers",
        stage=3,
        last_seen="2026-04",
        url="https://github.com/tc39/proposal-async-iterator-helpers",
        rationale=(
            "Adds `.map`, `.filter`, `.toArray`, etc. to async iterators. "
            "When shipped, evaluate whether the helpers should appear in the "
            "ES2023 fix-suggestion lookup as alternatives to manual `.push` "
            "into an accumulator inside `for await`."
        ),
        recognition_target="fix-suggestion alternative to .push accumulators",
    ),
    WatchListEntry(
        name="Decorators (Stage 3 metadata)",
        stage=3,
        last_seen="2026-04",
        url="https://github.com/tc39/proposal-decorators",
        rationale=(
            "Class decorators may rewrite class fields. The hook currently "
            "treats decorated assignments the same as undecorated ones. When "
            "the proposal reaches Stage 4, audit whether the decorator's "
            "context object exposes a mutating API that should be flagged "
            "(e.g. `context.addInitializer` writes to the constructor)."
        ),
        recognition_target="audit needed at Stage 4",
    ),
)


def _format_watch_list(entries: tuple[WatchListEntry, ...]) -> str:
    parts: list[str] = []
    parts.append("# TC39 Watch List")
    parts.append("")
    parts.append("Tracks proposals that may require new mutation detectors.")
    parts.append("Recognition becomes appropriate at Stage 2.")
    parts.append("")
    for entry in entries:
        parts.append(f"## {entry.name} (Stage {entry.stage})")
        parts.append("")
        parts.append(f"- Last seen: {entry.last_seen}")
        parts.append(f"- URL: {entry.url}")
        parts.append(f"- Recognition target: {entry.recognition_target}")
        parts.append(f"- Rationale: {entry.rationale}")
        parts.append("")
    return "\n".join(parts)


def _quarter_first_monday(today: _dt.date) -> _dt.date:
    """Return the first Monday of the current quarter.

    Quarter boundaries: Jan 1, Apr 1, Jul 1, Oct 1. The first Monday is the
    earliest date >= the quarter start whose `weekday()` equals 0.
    """
    quarter_start_month = ((today.month - 1) // 3) * 3 + 1
    start = _dt.date(today.year, quarter_start_month, 1)
    offset = (7 - start.weekday()) % 7
    return start + _dt.timedelta(days=offset)


def is_quarterly_review_day(today: _dt.date | None = None) -> bool:
    """True when today is the first Monday of a quarter."""
    today = today or _dt.date.today()
    return today == _quarter_first_monday(today)


_TC39_FINISHED_URL = "https://github.com/tc39/proposals/blob/main/finished-proposals.md"


def _quarterly_message(today: _dt.date) -> str:
    return (
        f"[{today.isoformat()}] Quarterly review due. "
        "Review the TC39 finished-proposals list for new shipped features "
        f"that may need fix-suggestion entries: {_TC39_FINISHED_URL}. "
        "On promotion of a Stage 3 proposal to Stage 4, evaluate adding "
        "an entry to hooks/mutation_fix_suggestions.json with the matching "
        'MMB code and a `"stage": 4` field; remove or update any pre-Stage-4 '
        "draft entry that referenced the same feature. "
        "Run: python3 .github/scripts/maintenance.py watch-list"
    )


def _cmd_watch_list(_args: argparse.Namespace) -> int:
    sys.stdout.write(_format_watch_list(WATCH_LIST))
    return 0


def _cmd_quarterly_check(args: argparse.Namespace) -> int:
    today = _dt.date.today()
    if args.force or is_quarterly_review_day(today):
        sys.stdout.write(_quarterly_message(today) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mutation-blocker maintenance")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("watch-list", help="print the TC39 watch list")

    qc = sub.add_parser(
        "quarterly-check",
        help="print the quarterly review reminder when due",
    )
    qc.add_argument(
        "--force",
        action="store_true",
        help="print the reminder regardless of the date",
    )

    args = parser.parse_args(argv)
    if args.cmd == "watch-list":
        return _cmd_watch_list(args)
    if args.cmd == "quarterly-check":
        return _cmd_quarterly_check(args)
    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
