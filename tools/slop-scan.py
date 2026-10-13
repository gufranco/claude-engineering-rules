#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType

HOOK_PATH = Path(__file__).resolve().parent.parent / "hooks" / "ai-slop-blocker.py"
MARKDOWN_SUFFIXES = (".md", ".markdown")
SKIPPED_DIRS = frozenset(
    {
        ".git",
        ".next",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "out",
        "vendor",
        "venv",
    }
)
MAX_FILES = 20_000
MAX_COMMITS = 2_000
GIT_TIMEOUT_S = 30.0
COMMIT_SEPARATOR = "\x1e"
FIELD_SEPARATOR = "\x00"
EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2


class ScanError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Finding:
    source: str
    code: str
    label: str
    location: str


def load_detector() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ai_slop_blocker", HOOK_PATH)
    if spec is None or spec.loader is None:
        raise ScanError(f"cannot load the detector at {HOOK_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def walk_markdown(root: Path) -> Iterator[Path]:
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIPPED_DIRS)
        for name in sorted(files):
            if name.lower().endswith(MARKDOWN_SUFFIXES):
                yield Path(current) / name


def markdown_files(target: Path) -> list[Path]:
    if not target.exists():
        raise ScanError(f"no such path: {target}")
    if target.is_file():
        return [target]
    found: list[Path] = []
    for path in walk_markdown(target):
        if len(found) >= MAX_FILES:
            raise ScanError(f"more than {MAX_FILES} Markdown files under {target}")
        found = [*found, path]
    return found


def to_findings(source: str, raw: list[tuple[str, str, str, str]]) -> list[Finding]:
    return [Finding(source, code, label, location) for code, label, location, _ in raw]


def scan_file(detector: ModuleType, path: Path) -> list[Finding]:
    absolute = str(path.resolve())
    if detector.is_skipped_path(absolute):
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    raw = detector.drop_record_findings(absolute, detector.find(text, True))
    return to_findings(str(path), raw)


def git_log(repo: Path, revision_range: str) -> str:
    command = [
        "git",
        "-C",
        str(repo),
        "log",
        f"--max-count={MAX_COMMITS}",
        "--format=%h%x00%B%x1e",
        revision_range,
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=GIT_TIMEOUT_S, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ScanError(f"git log {revision_range} failed: {error}") from error
    if result.returncode != 0:
        raise ScanError(f"git log {revision_range} failed: {result.stderr.strip()}")
    return result.stdout


def commit_messages(repo: Path, revision_range: str) -> list[tuple[str, str]]:
    entries = git_log(repo, revision_range).split(COMMIT_SEPARATOR)
    pairs = [entry.strip().split(FIELD_SEPARATOR, 1) for entry in entries]
    return [(pair[0], pair[1]) for pair in pairs if len(pair) == 2]


def scan_commits(
    detector: ModuleType, repo: Path, revision_range: str
) -> list[Finding]:
    return [
        finding
        for sha, message in commit_messages(repo, revision_range)
        for finding in to_findings(f"commit {sha}", detector.find(message, False))
    ]


def scan(targets: list[Path], revision_range: str | None) -> list[Finding]:
    detector = load_detector()
    files = [path for target in targets for path in markdown_files(target)]
    found = [finding for path in files for finding in scan_file(detector, path)]
    if revision_range is None:
        return found
    return [*found, *scan_commits(detector, targets[0], revision_range)]


def render_text(findings: list[Finding]) -> str:
    lines = [f"{f.source}: {f.code} {f.label}, {f.location}" for f in findings]
    sources = len({f.source for f in findings})
    return "\n".join([*lines, f"{len(findings)} findings in {sources} sources"])


def render(findings: list[Finding], as_json: bool) -> str:
    if as_json:
        return json.dumps([asdict(f) for f in findings], indent=2)
    return render_text(findings)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan Markdown files and commit messages for AI slop tells."
    )
    parser.add_argument("paths", nargs="*", default=[Path(".")], type=Path)
    parser.add_argument("--commits", metavar="RANGE", default=None)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        findings = scan(args.paths, args.commits)
    except ScanError as error:
        print(f"slop-scan: {error}", file=sys.stderr)
        return EXIT_ERROR
    print(render(findings, args.json))
    return EXIT_FINDINGS if findings else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
