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
CAPTURED_REPORT = (
    Path(__file__).resolve().parent / "fixtures" / "pnpm-audit-report.json"
)
GHSA = "GHSA-xvch-5gv4-984h"
CAPTURED_FAILURES = [
    "minimist: critical GHSA-xvch-5gv4-984h Prototype Pollution in minimist",
    "braces: high GHSA-grv7-fg5c-xmjg Uncontrolled resource consumption in braces",
]


@pytest.fixture
def audit() -> ModuleType:
    spec = importlib.util.spec_from_file_location("audit_release_toolchain", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def advisory(
    package: str, severity: str, patched: str = ">=1.2.6"
) -> dict[str, object]:
    return {
        "id": 1097678,
        "module_name": package,
        "severity": severity,
        "title": f"Prototype Pollution in {package}",
        "url": f"https://github.com/advisories/{GHSA}",
        "github_advisory_id": GHSA,
        "patched_versions": patched,
        "vulnerable_versions": ">=1.0.0 <1.2.6",
        "findings": [{"version": "1.2.5", "paths": [f".>{package}"]}],
        "cwe": "CWE-1321",
    }


def report(*entries: dict[str, object]) -> dict[str, object]:
    return {
        "advisories": {str(index): entry for index, entry in enumerate(entries)},
        "metadata": {"vulnerabilities": {"high": 0, "critical": 0}},
    }


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


@pytest.mark.parametrize("severity", ["high", "critical"])
def test_a_high_or_critical_advisory_fails(
    audit: ModuleType, faker: Faker, severity: str
) -> None:
    # Arrange
    package = faker.slug()
    argument = report(advisory(package, severity))

    # Act
    result = audit.failures(argument)

    # Assert
    assert result == [f"{package}: {severity} {GHSA} Prototype Pollution in {package}"]


@pytest.mark.parametrize("severity", ["low", "moderate", "info"])
def test_a_lower_severity_advisory_is_ignored(
    audit: ModuleType, faker: Faker, severity: str
) -> None:
    # Arrange
    argument = report(advisory(faker.slug(), severity))

    # Act
    result = audit.failures(argument)

    # Assert
    assert result == []


def test_an_advisory_with_no_patched_release_still_blocks(
    audit: ModuleType, faker: Faker
) -> None:
    # Arrange
    package = faker.slug()
    argument = report(advisory(package, "high", patched="<0.0.0"))

    # Act
    result = audit.failures(argument)

    # Assert
    assert result == [f"{package}: high {GHSA} Prototype Pollution in {package}"]


def test_the_advisories_decide_even_when_the_metadata_counts_none(
    audit: ModuleType, faker: Faker
) -> None:
    # Arrange
    package = faker.slug()
    argument = report(advisory(package, "critical"))

    # Act
    result = audit.failures(argument)

    # Assert
    assert result == [f"{package}: critical {GHSA} Prototype Pollution in {package}"]


def test_a_captured_pnpm_report_is_parsed(audit: ModuleType) -> None:
    # Arrange
    captured = json.loads(CAPTURED_REPORT.read_text(encoding="utf-8"))

    # Act
    result = audit.failures(captured)

    # Assert
    assert result == CAPTURED_FAILURES


def test_the_cli_fails_on_a_captured_pnpm_report() -> None:
    # Arrange
    payload = CAPTURED_REPORT.read_text(encoding="utf-8")

    # Act
    proc = run_script(payload)

    # Assert
    assert (proc.returncode, proc.stdout) == (
        1,
        "".join(f"{line}\n" for line in CAPTURED_FAILURES),
    )


def test_a_clean_report_exits_zero() -> None:
    # Arrange
    payload = json.dumps(report())

    # Act
    proc = run_script(payload)

    # Assert
    assert (proc.returncode, proc.stdout) == (
        0,
        "release toolchain audit: no high or critical advisory\n",
    )


def test_each_blocking_advisory_is_named_and_exits_one(faker: Faker) -> None:
    # Arrange
    first, second = faker.slug(), faker.slug()
    entries = (
        advisory(first, "high"),
        advisory(second, "low"),
        advisory(second, "critical"),
    )
    payload = json.dumps(report(*entries))

    # Act
    proc = run_script(payload)

    # Assert
    assert (proc.returncode, proc.stdout) == (
        1,
        f"{first}: high {GHSA} Prototype Pollution in {first}\n"
        f"{second}: critical {GHSA} Prototype Pollution in {second}\n",
    )


def test_output_that_is_not_json_fails_closed() -> None:
    # Arrange
    payload = ""

    # Act
    proc = run_script(payload)

    # Assert
    assert (proc.returncode, proc.stdout) == (
        1,
        "release toolchain audit: pnpm audit output is not JSON\n",
    )


@pytest.mark.parametrize("payload", ["[]", "{}", '{"advisories": []}'])
def test_json_without_an_advisories_map_fails_closed(payload: str) -> None:
    # Arrange
    stdin = payload

    # Act
    proc = run_script(stdin)

    # Assert
    assert (proc.returncode, proc.stdout) == (
        1,
        "release toolchain audit: pnpm audit output has no advisories map\n",
    )
