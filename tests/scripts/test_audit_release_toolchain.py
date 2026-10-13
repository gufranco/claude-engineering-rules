from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env

REPO_ROOT = Path(__file__).resolve().parents[2]

SCRIPT = REPO_ROOT / ".github" / "scripts" / "audit-release-toolchain.py"
WAIVED_URL = "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm"
OTHER_URL = "https://github.com/advisories/GHSA-aaaa-bbbb-cccc"
BREAKING_FIX = {"name": "x", "version": "1.0.0", "isSemVerMajor": True}


@pytest.fixture
def audit() -> ModuleType:
    spec = importlib.util.spec_from_file_location("audit_release_toolchain", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report(*entries: tuple[str, str, str, object]) -> dict[str, object]:
    vulnerabilities: dict[str, object] = {
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


def test_waived_advisory_without_a_fix_passes(audit: ModuleType) -> None:
    # Arrange
    argument = report(("braces", WAIVED_URL, "high", BREAKING_FIX))

    # Act
    failures = audit.failures(argument)

    # Assert
    assert failures == []


def test_waived_advisory_with_a_fix_fails(audit: ModuleType) -> None:
    # Arrange
    argument = report(("braces", WAIVED_URL, "high", True))

    # Act
    failures = audit.failures(argument)

    # Assert
    assert failures == [
        "braces: GHSA-vfj7-8cjw-p6xm now has a fix; upgrade and drop the waiver"
    ]


@pytest.mark.parametrize("severity", ["high", "critical"])
def test_unwaived_high_or_critical_fails(
    audit: ModuleType, faker: Faker, severity: str
) -> None:
    # Arrange
    package = faker.slug()
    argument = report((package, OTHER_URL, severity, True))

    # Act
    failures = audit.failures(argument)

    # Assert
    assert failures == [f"{package}: {severity} GHSA-aaaa-bbbb-cccc {package} bug"]


@pytest.mark.parametrize("severity", ["low", "moderate"])
def test_lower_severity_is_ignored(
    audit: ModuleType, faker: Faker, severity: str
) -> None:
    # Arrange
    argument = report((faker.slug(), OTHER_URL, severity, True))

    # Act
    failures = audit.failures(argument)

    # Assert
    assert failures == []


def test_empty_report_passes(audit: ModuleType) -> None:
    # Arrange
    payload: dict[str, object] = {}

    # Act
    failures = audit.failures(payload)

    # Assert
    assert failures == []


def run_script(payload: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        env=apply_coverage_env(dict(os.environ)),
        check=False,
    )


def test_cli_exits_zero_for_the_waived_advisory() -> None:
    # Arrange
    payload = json.dumps(report(("braces", WAIVED_URL, "high", BREAKING_FIX)))

    # Act
    proc = run_script(payload)

    # Assert
    assert (proc.returncode, proc.stdout.strip()) == (
        0,
        "release toolchain audit: clean apart from 1 waived advisory",
    )


def test_cli_exits_one_and_names_each_failure(faker: Faker) -> None:
    # Arrange
    package = faker.slug()
    payload = json.dumps(report((package, OTHER_URL, "high", True)))

    # Act
    proc = run_script(payload)

    # Assert
    assert (proc.returncode, proc.stdout) == (
        1,
        f"{package}: high GHSA-aaaa-bbbb-cccc {package} bug\n",
    )


def test_cli_fails_closed_on_unreadable_input() -> None:
    # Arrange
    payload = "not json"

    # Act
    proc = run_script(payload)

    # Assert
    assert (proc.returncode, proc.stdout.strip()) == (
        1,
        "release toolchain audit: npm audit output is not JSON",
    )


def test_cli_fails_closed_when_npm_reports_an_error() -> None:
    # Arrange
    payload = json.dumps({"error": {"code": "ENOAUDIT", "summary": "registry down"}})

    # Act
    proc = run_script(payload)

    # Assert
    assert (proc.returncode, proc.stdout.strip()) == (
        1,
        "release toolchain audit: npm audit failed: ENOAUDIT registry down",
    )
