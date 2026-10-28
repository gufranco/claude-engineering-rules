#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bench_hooks import _cli  # noqa: E402

DEFAULT_THRESHOLD_MS = "500"
MISSING_THRESHOLD = "--threshold needs a value in milliseconds"


def threshold_from(argv: list[str]) -> str | None:
    if argv[:1] != ["--threshold"]:
        return DEFAULT_THRESHOLD_MS
    return argv[1] if len(argv) > 1 else None


def bench_argv(threshold_ms: str) -> list[str]:
    return [
        "--hooks-dir",
        str(ROOT / "hooks"),
        "--settings",
        str(ROOT / "settings.json"),
        "--iterations",
        "3",
        "--threshold-ms",
        threshold_ms,
    ]


def main(argv: list[str]) -> int:
    threshold = threshold_from(argv)
    if threshold is None:
        print(MISSING_THRESHOLD, file=sys.stderr)
        return 2
    return _cli(bench_argv(threshold))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
