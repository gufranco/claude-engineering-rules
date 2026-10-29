#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

BLOCKING = ("high", "critical")


def failures(report: dict) -> list[str]:
    return [
        f"{advisory['module_name']}: {advisory['severity']} "
        f"{advisory['github_advisory_id']} {advisory['title']}"
        for advisory in report["advisories"].values()
        if advisory["severity"] in BLOCKING
    ]


def main() -> int:
    try:
        report = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("release toolchain audit: pnpm audit output is not JSON")
        return 1
    if not isinstance(report, dict) or not isinstance(report.get("advisories"), dict):
        print("release toolchain audit: pnpm audit output has no advisories map")
        return 1
    found = failures(report)
    for line in found:
        print(line)
    if not found:
        print("release toolchain audit: no high or critical advisory")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
