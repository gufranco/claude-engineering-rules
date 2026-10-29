#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

SHIELDS = "https://img.shields.io"
STYLE = "style=flat-square"
GIT_TIMEOUT_SECONDS = 10
EXCLUDED_WORKFLOWS = frozenset(
    {
        "auto-merge",
        "codeql",
        "codeql-analysis",
        "dependabot",
        "dependency-review",
        "deploy",
        "formula",
        "labeler",
        "pages",
        "release",
        "renovate",
        "scorecard",
        "stale",
    }
)
COVERAGE_FILES = (
    "pyproject.toml",
    ".coveragerc",
    "setup.cfg",
    "tox.ini",
    "pytest.ini",
    "Makefile",
    "package.json",
    ".c8rc.json",
    ".nycrc",
    ".nycrc.json",
)
COVERAGE_GLOBS = (
    "vitest.config.*",
    "jest.config.*",
    "scripts/*.sh",
    ".github/workflows/*.y*ml",
)
COVERAGE_PATTERNS = (
    re.compile(r"fail_under\s*=\s*(\d+)"),
    re.compile(r"--(?:cov-)?fail-under[= ](\d+)"),
    re.compile(r"(?:MIN(?:IMUM)?_COVERAGE|COVERAGE_MIN(?:IMUM)?)\s*=\s*(\d+)"),
    re.compile(r"minimum_coverage\s+(\d+)"),
    re.compile(r'"?(?:lines|statements|branches|functions)"?\s*:\s*(\d+)'),
)
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")
SPDX_RULES = (
    (("MIT License",), "MIT"),
    (("Apache License", "Version 2.0"), "Apache-2.0"),
    (("GNU AFFERO GENERAL PUBLIC LICENSE",), "AGPL-3.0"),
    (("GNU LESSER GENERAL PUBLIC LICENSE",), "LGPL-3.0"),
    (("GNU GENERAL PUBLIC LICENSE", "Version 3"), "GPL-3.0"),
    (("GNU GENERAL PUBLIC LICENSE", "Version 2"), "GPL-2.0"),
    (("Mozilla Public License Version 2.0",), "MPL-2.0"),
    (("ISC License",), "ISC"),
    (("BSD 3-Clause",), "BSD-3-Clause"),
    (("This is free and unencumbered software",), "Unlicense"),
)
SLUG = re.compile(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")
BADGE_LINE = re.compile(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)")
LANGUAGE_LINE = re.compile(r"\]\(README\.[^)]+\.md\)")
README_NAME = re.compile(r"README(?:\.[a-z]{2,3}(?:-[A-Za-z]{2,4})?)?\.md")


@dataclass(frozen=True, slots=True)
class Workflow:
    file: str
    label: str


@dataclass(frozen=True, slots=True)
class Facts:
    slug: str
    branch: str
    private: bool
    has_release: bool
    workflows: tuple[Workflow, ...]
    coverage: int | None
    scorecard: bool
    license: tuple[str, str] | None


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _slug(repo: Path) -> str:
    match = SLUG.search(_git(repo, "remote", "get-url", "origin"))
    if not match:
        raise ValueError(f"{repo}: no GitHub origin remote")
    return f"{match.group(1)}/{match.group(2)}"


def _branch(repo: Path) -> str:
    remote_head = _git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if remote_head:
        return remote_head.split("/", 1)[1]
    return _git(repo, "branch", "--show-current") or "main"


def _on_block(text: str) -> str:
    match = re.search(r"^on:(.*(?:\n[ \t]+.*|\n\s*)*)", text, re.MULTILINE)
    return match.group(1) if match else ""


def _gates(path: Path) -> Workflow | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    name_match = re.search(r"^name:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", text, re.MULTILINE)
    label = (name_match.group(1) if name_match else path.stem).strip().lower()
    trigger = _on_block(text)
    pushes = re.search(r"\bpush\b", trigger) is not None
    excluded = path.stem.lower() in EXCLUDED_WORKFLOWS or label in EXCLUDED_WORKFLOWS
    if not pushes or excluded or "ossf/scorecard-action" in text:
        return None
    return Workflow(path.name, label)


def _workflow_files(repo: Path) -> list[Path]:
    folder = repo / ".github" / "workflows"
    return (
        sorted([*folder.glob("*.yml"), *folder.glob("*.yaml")])
        if folder.is_dir()
        else []
    )


def _workflows(repo: Path) -> tuple[Workflow, ...]:
    return tuple(found for path in _workflow_files(repo) if (found := _gates(path)))


def _coverage(repo: Path) -> int | None:
    files = [repo / name for name in COVERAGE_FILES]
    files = [
        *files,
        *(path for pattern in COVERAGE_GLOBS for path in repo.glob(pattern)),
    ]
    texts = [
        path.read_text(encoding="utf-8", errors="replace")
        for path in files
        if path.is_file()
    ]
    floors = [
        int(m) for text in texts for p in COVERAGE_PATTERNS for m in p.findall(text)
    ]
    enforced = [floor for floor in floors if floor > 0]
    return min(enforced) if enforced else None


def _license(repo: Path) -> tuple[str, str] | None:
    found = next(
        (repo / name for name in LICENSE_NAMES if (repo / name).is_file()), None
    )
    if found is None:
        return None
    text = found.read_text(encoding="utf-8", errors="replace")[:2000]
    spdx = next(
        (spdx for needles, spdx in SPDX_RULES if all(n in text for n in needles)), None
    )
    return (spdx, found.name) if spdx else None


def collect(repo: Path, *, private: bool, has_release: bool) -> Facts:
    return Facts(
        slug=_slug(repo),
        branch=_branch(repo),
        private=private,
        has_release=has_release,
        workflows=_workflows(repo),
        coverage=_coverage(repo),
        scorecard=any(
            "ossf/scorecard-action" in p.read_text(errors="replace")
            for p in _workflow_files(repo)
        ),
        license=_license(repo),
    )


def _ci(facts: Facts, workflow: Workflow) -> str:
    page = f"https://github.com/{facts.slug}/actions/workflows/{workflow.file}"
    if facts.private:
        return f"[![{workflow.label}]({page}/badge.svg?branch={facts.branch})]({page})"
    label = quote(workflow.label)
    image = f"{SHIELDS}/github/actions/workflow/status/{facts.slug}/{workflow.file}"
    return f"[![{workflow.label}]({image}?branch={facts.branch}&{STYLE}&label={label})]({page})"


def _release(facts: Facts) -> list[str]:
    if facts.private or not facts.has_release:
        return []
    image = f"{SHIELDS}/github/v/release/{facts.slug}?{STYLE}&label=release"
    return [f"[![release]({image})](https://github.com/{facts.slug}/releases/latest)"]


def _coverage_badge(facts: Facts) -> list[str]:
    if facts.coverage is None:
        return []
    first = facts.workflows[0].file if facts.workflows else ""
    link = (
        f"https://github.com/{facts.slug}/actions/workflows/{first}"
        if first
        else f"https://github.com/{facts.slug}"
    )
    image = f"{SHIELDS}/badge/coverage-{facts.coverage}%25-brightgreen?{STYLE}"
    return [f"[![coverage]({image})]({link})"]


def _scorecard(facts: Facts) -> list[str]:
    if facts.private or not facts.scorecard:
        return []
    image = f"{SHIELDS}/ossf-scorecard/github.com/{facts.slug}?{STYLE}&label=openssf%20scorecard"
    return [
        f"[![openssf scorecard]({image})](https://scorecard.dev/viewer/?uri=github.com/{facts.slug})"
    ]


def _license_badge(facts: Facts) -> list[str]:
    if facts.license is None:
        return []
    spdx, file = facts.license
    if facts.private:
        return [
            f"[![license]({SHIELDS}/badge/license-{spdx.replace('-', '--')}-blue?{STYLE})]({file})"
        ]
    return [
        f"[![license]({SHIELDS}/github/license/{facts.slug}?{STYLE}&label=license)]({file})"
    ]


def block(facts: Facts) -> list[str]:
    ci = [_ci(facts, workflow) for workflow in facts.workflows]
    return [
        *ci,
        *_release(facts),
        *_coverage_badge(facts),
        *_scorecard(facts),
        *_license_badge(facts),
    ]


def _header_end(lines: list[str]) -> int:
    return next(
        (i for i, line in enumerate(lines) if line.startswith("## ")), len(lines)
    )


def _paragraph_end(lines: list[str], start: int, limit: int) -> int:
    index = start
    while index < limit and lines[index].strip():
        index += 1
    return index


def _anchor(lines: list[str], limit: int) -> int:
    language = next((i for i in range(limit) if LANGUAGE_LINE.search(lines[i])), None)
    if language is not None:
        return language + 1
    title = next(
        (
            i
            for i in range(limit)
            if lines[i].startswith("# ") or "<strong>" in lines[i]
        ),
        None,
    )
    if title is None:
        return 0
    body = next((i for i in range(title + 1, limit) if lines[i].strip()), None)
    return _paragraph_end(lines, body, limit) if body is not None else title + 1


def _collapse(lines: list[str], stop: int) -> list[str]:
    head = [
        line
        for i, line in enumerate(lines[:stop])
        if line.strip() or i == 0 or lines[i - 1].strip()
    ]
    return [*head, *lines[stop:]]


def apply(text: str, badges: list[str]) -> str:
    lines = text.split("\n")
    limit = _header_end(lines)
    old = [i for i in range(limit) if BADGE_LINE.fullmatch(lines[i].strip())]
    anchor = old[0] if old else _anchor(lines, limit)
    kept = [line for i, line in enumerate(lines) if i not in old]
    anchor -= sum(1 for i in old if i < anchor)
    inserted = ["", *badges, ""] if badges else []
    merged = [*kept[:anchor], *inserted, *kept[anchor:]]
    stop = (
        _header_end(merged)
        if any(line.startswith("## ") for line in merged)
        else anchor + len(inserted) + 1
    )
    return "\n".join(_collapse(merged, stop))


def _readmes(repo: Path) -> list[Path]:
    return sorted(
        path for path in repo.glob("README*.md") if README_NAME.fullmatch(path.name)
    )


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute and apply the standard README badge block."
    )
    parser.add_argument("repo", type=Path)
    parser.add_argument("--visibility", choices=("public", "private"), required=True)
    parser.add_argument("--release", choices=("yes", "no"), required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    return parser.parse_args(argv)


def run(argv: list[str]) -> int:
    args = _parse(argv)
    try:
        facts = collect(
            args.repo,
            private=args.visibility == "private",
            has_release=args.release == "yes",
        )
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    badges = block(facts)
    if not (args.check or args.write):
        print("\n".join(badges))
        return 0
    stale = [
        path
        for path in _readmes(args.repo)
        if apply(path.read_text(encoding="utf-8"), badges)
        != path.read_text(encoding="utf-8")
    ]
    if args.write:
        for path in stale:
            path.write_text(
                apply(path.read_text(encoding="utf-8"), badges), encoding="utf-8"
            )
        return 0
    for path in stale:
        print(f"{path.name}: badges differ from the standard block")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
