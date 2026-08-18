#!/usr/bin/env python3
"""Measure whether the vault can actually answer the questions it is asked.

A second brain that nobody can retrieve from is a filing habit, not a system.
This puts a number on it: given a case file of real questions and the notes that
should answer them, report recall at 3 and at 10, and fail against a recorded
baseline when it drops.

The ranking here is lexical, deterministic, and dependency-free. It is a lower
bound on what an agent reading the vault would find, never a simulation of it.
A note the scorer cannot reach on the question's own words is a note whose title
and preamble are not carrying their weight, which is the defect worth catching.

Usage:

    python3 .github/scripts/retrieval-eval.py [--path DIR] --cases FILE
        [--baseline FILE] [--record] [--json] [--strict]

Rule source: ``rules/knowledge-notes.md``.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib import knowledge_notes as kn  # noqa: E402

TOKEN = re.compile(r"[a-z0-9]+")
MIN_TOKEN = 3
TITLE_WEIGHT = 3
PREAMBLE_WEIGHT = 2
BODY_WEIGHT = 1
TOLERANCE = 0.01

STOPWORDS = frozenset(
    """
    the and for are but not you all any can had her was one our out day get has him his how man new
    now old see two way who did its let put say she too use what when where which with this that from
    have does doing done then than them they there their been being about into over under after before
    why whom will would should could must may might make made take taken give given
    """.split()
)


@dataclass(frozen=True)
class Index:
    frequencies: dict[str, Counter]
    document_count: int
    document_frequency: Counter


def tokenize(text: str) -> list[str]:
    """Return meaningful lowercase terms, stopwords and short tokens dropped."""
    return [
        token
        for token in TOKEN.findall(text.lower())
        if len(token) >= MIN_TOKEN and token not in STOPWORDS
    ]


def note_fields(rel: Path, text: str) -> tuple[str, str, str]:
    body = kn.body_after_frontmatter(text)
    preamble = ""
    if kn.PREAMBLE in body:
        after = body.split(kn.PREAMBLE, 1)[1]
        preamble = after.split("\n##", 1)[0]
    return rel.stem, preamble, body


def build_index(root: Path) -> Index:
    """Build a weighted term index over every governed note in the vault."""
    frequencies: dict[str, Counter] = {}
    document_frequency: Counter = Counter()
    for rel, text in kn.iter_notes(root):
        title, preamble, body = note_fields(rel, text)
        counts: Counter = Counter()
        for source, weight in (
            (title, TITLE_WEIGHT),
            (preamble, PREAMBLE_WEIGHT),
            (body, BODY_WEIGHT),
        ):
            for token in tokenize(source):
                counts[token] += weight
        frequencies[rel.stem] = counts
        for token in set(counts):
            document_frequency[token] += 1
    return Index(frequencies, len(frequencies), document_frequency)


def search(index: Index, question: str, limit: int) -> list[str]:
    """Return the highest scoring note titles for a question, best first."""
    terms = tokenize(question)
    scored: list[tuple[float, str]] = []
    for title, counts in index.frequencies.items():
        score = 0.0
        for term in terms:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            idf = math.log(1 + index.document_count / index.document_frequency[term])
            score += (1 + math.log(frequency)) * idf
        if score > 0:
            scored.append((score, title))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [title for _score, title in scored[:limit]]


def load_cases(path: Path) -> list[dict]:
    """Read the case file, one JSON object per line."""
    cases: list[dict] = []
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            cases.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise SystemExit(
                f"retrieval-eval: {path}:{number} is not valid JSON: {error}"
            )
    return cases


def evaluate(root: Path, cases: list[dict]) -> dict:
    """Return recall at 3 and 10 across every case, plus the cases that missed."""
    index = build_index(root)
    totals = {3: 0.0, 10: 0.0}
    misses: list[dict] = []
    for case in cases:
        question = case.get("question", "")
        expected = set(case.get("expect", []))
        if not expected:
            continue
        for depth in totals:
            hits = expected & set(search(index, question, limit=depth))
            totals[depth] += len(hits) / len(expected)
        top = search(index, question, limit=3)
        if not expected & set(top):
            misses.append(
                {"question": question, "expected": sorted(expected), "got": top}
            )
    count = max(len(cases), 1)
    return {
        "date": date.today().isoformat(),
        "cases": len(cases),
        "notes": index.document_count,
        "recall_at_3": round(totals[3] / count, 4),
        "recall_at_10": round(totals[10] / count, 4),
        "misses": misses,
    }


def compare(result: dict, baseline: dict | None) -> dict:
    """Return whether recall dropped against a recorded baseline."""
    if baseline is None:
        return {"regressed": False, "baseline": None, "drops": []}
    drops = [
        key
        for key in ("recall_at_3", "recall_at_10")
        if key in baseline and result.get(key, 0) < baseline[key] - TOLERANCE
    ]
    return {"regressed": bool(drops), "baseline": baseline, "drops": drops}


def render(result: dict, verdict: dict) -> str:
    lines = [
        f"{result['cases']} case(s) over {result['notes']} note(s)",
        f"recall@3  {result['recall_at_3']:.2f}",
        f"recall@10 {result['recall_at_10']:.2f}",
    ]
    if verdict["baseline"]:
        base = verdict["baseline"]
        lines.append(
            f"baseline  recall@3 {base.get('recall_at_3', 0):.2f}, "
            f"recall@10 {base.get('recall_at_10', 0):.2f}"
        )
    if verdict["drops"]:
        lines.append(f"REGRESSION in {', '.join(verdict['drops'])}")
    for miss in result["misses"]:
        lines.append(
            f"miss: {miss['question']}\n    expected {miss['expected']}, got {miss['got']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure vault retrieval recall.")
    parser.add_argument("--path", default=None)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--baseline", default=None)
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    root = kn.vault_root(args.path)
    if root is None:
        target = args.path or "SECOND_BRAIN_VAULT"
        print(f"retrieval-eval: {target} is not a directory", file=sys.stderr)
        return 2

    case_path = Path(args.cases)
    if not case_path.is_file():
        print(f"retrieval-eval: case file {case_path} does not exist", file=sys.stderr)
        return 2

    result = evaluate(root, load_cases(case_path))

    baseline = None
    baseline_path = Path(args.baseline) if args.baseline else None
    if baseline_path and baseline_path.is_file():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    verdict = compare(result, baseline)

    if args.record and baseline_path:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        recorded = {
            key: result[key]
            for key in ("date", "cases", "notes", "recall_at_3", "recall_at_10")
        }
        baseline_path.write_text(
            json.dumps(recorded, indent=2) + "\n", encoding="utf-8"
        )

    if args.json:
        print(json.dumps({**result, "verdict": verdict}, indent=2))
    else:
        print(render(result, verdict))
    return 1 if args.strict and verdict["regressed"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
