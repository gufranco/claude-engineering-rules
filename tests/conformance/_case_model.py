from __future__ import annotations

import os
from dataclasses import dataclass

BASE = os.path.join(os.path.dirname(__file__), "cases")


@dataclass(frozen=True, slots=True)
class Case:
    group: str
    stem: str
    description: str
    verdict: str
    detector: str | None
    payload: str
    file: str | None
    body: str


def block(
    group: str,
    stem: str,
    description: str,
    detector: str,
    payload: str,
    body: str,
    file: str | None = None,
) -> Case:
    return Case(group, stem, description, "block", detector, payload, file, body)


def allow(
    group: str,
    stem: str,
    description: str,
    payload: str,
    body: str,
    file: str | None = None,
) -> Case:
    return Case(group, stem, description, "allow", None, payload, file, body)


def frontmatter(case: Case) -> dict[str, str]:
    detector = {} if case.detector is None else {"detector": case.detector}
    file = {} if case.file is None else {"file": case.file}
    return {
        "description": case.description,
        "verdict": case.verdict,
        **detector,
        "payload": case.payload,
        **file,
    }


def write_case(path: str, fields: dict[str, str], body: str) -> None:
    target = os.path.join(BASE, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    lines = ["---", *(f"{k}: {v}" for k, v in fields.items()), "---", body]
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def write_numbered(cases: tuple[Case, ...]) -> int:
    for n, case in enumerate(cases, start=1):
        path = f"{case.group}{n:03d}-{case.stem}.test.ts"
        write_case(path, frontmatter(case), case.body)
    return len(cases)
