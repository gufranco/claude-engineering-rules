"""Tests for .github/scripts/audit-release-toolchain.py."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "tests"
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from _helpers.cov_env import apply_coverage_env  # noqa: E402

SCRIPT = REPO_ROOT / ".github" / "scripts" / "audit-release-toolchain.py"
WAIVED_URL = "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm"
OTHER_URL = "https://github.com/advisories/GHSA-aaaa-bbbb-cccc"
BREAKING_FIX = {"name": "x", "version": "1.0.0", "isSemVerMajor": True}


@pytest.fixture
def audit():
    spec = importlib.util.spec_from_file_location("audit_release_toolchain", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report(*entries: tuple[str, str, str, object]) -> dict:
    vulnerabilities = {
        package: {
            "severity": severity,
            "via": [{"url": url, "severity": severity, "title": f"{package} bug"}],
            "fixAvailable": fix,
        }
        for package, url, severity, fix in entries
    }
    vulnerabilities["micromatch"] = {
        "severity": "high",
        "via": ["braces"],
        "fixAvailable": BREAKING_FIX,
    }
    return {"vulnerabilities": vulnerabilities}


def test_waived_advisory_without_a_fix_passes(audit):
    failures = audit.failures(report(("braces", WAIVED_URL, "high", BREAKING_FIX)))

    assert failures == []


def test_waived_advisory_with_a_fix_fails(audit):
    failures = audit.failures(report(("braces", WAIVED_URL, "high", True)))

    assert failures == [
        "braces: GHSA-vfj7-8cjw-p6xm now has a fix; upgrade and drop the waiver"
    ]


@pytest.mark.parametrize("severity", ["high", "critical"])
def test_unwaived_high_or_critical_fails(audit, severity):
    failures = audit.failures(report(("left-pad", OTHER_URL, severity, True)))

    assert failures == [f"left-pad: {severity} GHSA-aaaa-bbbb-cccc left-pad bug"]


@pytest.mark.parametrize("severity", ["low", "moderate"])
def test_lower_severity_is_ignored(audit, severity):
    failures = audit.failures(report(("left-pad", OTHER_URL, severity, True)))

    assert failures == []


def test_empty_report_passes(audit):
    failures = audit.failures({})

    assert failures == []


def run_script(payload: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        env=apply_coverage_env(dict(os.environ)),
        check=False,
    )


def test_cli_exits_zero_for_the_waived_advisory():
    payload = json.dumps(report(("braces", WAIVED_URL, "high", BREAKING_FIX)))

    proc = run_script(payload)

    assert (proc.returncode, proc.stdout.strip()) == (
        0,
        "release toolchain audit: clean apart from 1 waived advisory",
    )


def test_cli_exits_one_and_names_each_failure():
    payload = json.dumps(report(("left-pad", OTHER_URL, "high", True)))

    proc = run_script(payload)

    assert (proc.returncode, proc.stdout.strip()) == (
        1,
        "left-pad: high GHSA-aaaa-bbbb-cccc left-pad bug",
    )


def test_cli_fails_closed_on_unreadable_input():
    proc = run_script("not json")

    assert (proc.returncode, proc.stdout.strip()) == (
        1,
        "release toolchain audit: npm audit output is not JSON",
    )


def test_cli_fails_closed_when_npm_reports_an_error():
    payload = json.dumps({"error": {"code": "ENOAUDIT", "summary": "registry down"}})

    proc = run_script(payload)

    assert (proc.returncode, proc.stdout.strip()) == (
        1,
        "release toolchain audit: npm audit failed: ENOAUDIT registry down",
    )
