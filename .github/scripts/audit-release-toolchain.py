#!/usr/bin/env python3
"""Gate the release toolchain on `npm audit --json`, with named waivers.

Reads the audit report on stdin. Fails on every high or critical advisory
except a waived one, and fails on a waived one as soon as npm reports a
non-breaking fix, so a waiver ends by itself when upstream ships a patch.

Usage: npm audit --json | python3 .github/scripts/audit-release-toolchain.py
"""

from __future__ import annotations

import json
import sys

BLOCKING = ("high", "critical")
WAIVED = {
    "GHSA-vfj7-8cjw-p6xm": "braces <=3.0.3 has no patched release; reached only "
    "through semantic-release dev dependencies with repository-constant patterns",
}


def advisory_id(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def direct_advisories(report: dict) -> list[tuple[str, dict, object]]:
    """(package, advisory, fixAvailable) for every advisory naming a package."""
    vulnerabilities = report.get("vulnerabilities") or {}
    return [
        (package, via, entry.get("fixAvailable"))
        for package, entry in vulnerabilities.items()
        for via in entry.get("via") or []
        if isinstance(via, dict)
    ]


def failures(report: dict) -> list[str]:
    found: list[str] = []
    for package, via, fix in direct_advisories(report):
        if via.get("severity") not in BLOCKING:
            continue
        ghsa = advisory_id(via.get("url", ""))
        if ghsa in WAIVED and fix is not True:
            continue
        message = (
            f"{package}: {ghsa} now has a fix; upgrade and drop the waiver"
            if ghsa in WAIVED
            else f"{package}: {via['severity']} {ghsa} {via.get('title', '')}".strip()
        )
        found = [*found, message]
    return found


def waived_count(report: dict) -> int:
    ids = {advisory_id(via.get("url", "")) for _, via, _ in direct_advisories(report)}
    return len(ids.intersection(WAIVED))


def main() -> int:
    try:
        report = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("release toolchain audit: npm audit output is not JSON")
        return 1
    error = report.get("error") if isinstance(report, dict) else None
    if error:
        print(
            f"release toolchain audit: npm audit failed: {error.get('code', '')} {error.get('summary', '')}".rstrip()
        )
        return 1
    found = failures(report)
    for line in found:
        print(line)
    if not found:
        print(
            f"release toolchain audit: clean apart from {waived_count(report)} waived advisory"
        )
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
