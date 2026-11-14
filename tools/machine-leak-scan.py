#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))

from _lib.machine_identity import discover  # noqa: E402
from _lib.machine_leak import Finding, Line, scan_lines  # noqa: E402

GIT_TIMEOUT_S = 30
MAX_FILE_BYTES = 512 * 1024
EXIT_CLEAN = 0
EXIT_FOUND = 1
EXIT_ERROR = 2


class RepositoryError(RuntimeError):
    pass


def _tracked(repo: Path) -> list[str]:
    listing = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_S,
        check=False,
    )
    if listing.returncode != 0:
        raise RepositoryError(f"{repo}: not a git repository")
    return [name for name in listing.stdout.split("\0") if name]


def _file_lines(repo: Path, name: str) -> list[Line]:
    path = repo / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        return []
    data = path.read_bytes()
    if b"\0" in data:
        return []
    text = data.decode("utf-8", errors="replace")
    return [(name, number, line) for number, line in enumerate(text.splitlines(), 1)]


def scan_repository(repo: Path) -> list[Finding]:
    lines = [line for name in _tracked(repo) for line in _file_lines(repo, name)]
    return scan_lines(lines, discover(Path.home(), repo.resolve()))


def _render(repo: str, found: list[Finding]) -> str:
    return "".join(
        f"{repo}:{f.path}:{f.line}: {f.kind.value} {f.token!r}\n" for f in found
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Report machine identifiers in tracked files."
    )
    parser.add_argument("repos", nargs="+")
    args = parser.parse_args(argv)
    try:
        results = [(repo, scan_repository(Path(repo))) for repo in args.repos]
    except RepositoryError as error:
        sys.stderr.write(f"{error}\n")
        return EXIT_ERROR
    sys.stdout.write("".join(_render(repo, found) for repo, found in results))
    return EXIT_FOUND if any(found for _repo, found in results) else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
